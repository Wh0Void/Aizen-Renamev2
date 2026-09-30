import asyncio
import ctypes
import functools
import gc
import inspect
import io
import logging
import math
import os
import re
import shutil
import socket
import sys
import tempfile
import time
from hashlib import md5, sha256
from pathlib import PurePath
from typing import Any, Callable, Dict, List, Optional, Tuple

from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from pyrogram import Client, StopPropagation, StopTransmission, filters, raw, utils
from pyrogram.connection.transport.tcp import TCP
from pyrogram.enums import MessageMediaType
from pyrogram.errors import CDNFileHashMismatch, FloodPremiumWait, FloodWait, VolumeLocNotFound
from pyrogram.file_id import FileId, FileType, ThumbnailSource
from pyrogram.session.session import Session
from pyrogram.types import ForceReply, Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from bot.core.cache import ram_workspace
from config import Config
from helper.database import Mythicbotz
from helper.ffmpeg import (
    add_metadata,
    extract_auto_thumbnail,
    get_cached_user_thumb,
    get_hd_cover_path,
    probe_video_dimensions_and_duration,
)
from helper.utils import (
    add_prefix_suffix,
    clear_transfer_cancellation,
    convert,
    humanbytes,
    init_progress_message,
    progress_for_pyrogram,
)

logger = logging.getLogger(__name__)

# =========================================================================
# SECTION 1: CONCURRENCY CONFIGURE UTILS
# =========================================================================

def auto_boost_client(client: Any = None) -> None:
    """Safe no-op: Concurrency gates are managed by fast_crypto."""
    pass


# =========================================================================
# SECTION 2: ANIMATED PROGRESS BAR & TELEMETRY PARSER
# =========================================================================

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def render_animated_bar(percentage: float, length: int = 10, frame_idx: int = 0) -> str:
    """Renders a smooth animated progress bar with rotating indicator pulses."""
    clamped_pct = max(0.0, min(100.0, percentage))
    filled_len = int(round((clamped_pct / 100.0) * length))
    spinner = SPINNER_FRAMES[frame_idx % len(SPINNER_FRAMES)]

    if filled_len >= length:
        bar = "▰" * length
    elif filled_len > 0:
        bar = ("▰" * (filled_len - 1)) + spinner + ("▱" * (length - filled_len))
    else:
        bar = spinner + ("▱" * (length - 1))
    return f"[{bar}]"


# =========================================================================
# SECTION 3: RE-ENCODING-FREE TORRENT AUDIO MUX ENGINE
# =========================================================================

ACTIVE_TORRENT_TASKS: Dict[int, Dict[str, Any]] = {}
VIDEO_EXTENSIONS = (".mkv", ".mp4", ".avi", ".mov", ".webm", ".ts", ".m4v", ".flv")
AUDIO_EXTENSIONS = (".mp3", ".aac", ".m4a", ".flac", ".wav", ".opus", ".ogg", ".ac3", ".eac3", ".dts")


async def _delayed_delete(*messages, delay: float = 1800.0) -> None:
    await asyncio.sleep(delay)
    for msg in messages:
        if msg is not None:
            try:
                await msg.delete()
            except Exception:
                pass


def _find_primary_video(target_dir: str) -> Optional[str]:
    if os.path.isfile(target_dir):
        return target_dir
    candidate, max_size = None, 0
    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.lower().endswith(VIDEO_EXTENSIONS):
                full_path = os.path.join(root, file)
                sz = os.path.getsize(full_path)
                if sz > max_size:
                    max_size, candidate = sz, full_path
    return candidate


async def _download_torrent_aria2(torrent_source: str, download_dir: str, status_msg: Message) -> bool:
    """
    Downloads torrent with aria2c configured for maximum peer saturation.
    Displays dynamic speed, animated progress bar, seeds, and leechers.
    Enforces a 300s seeder inactivity timeout and an overall 1800s execution timeout.
    """
    if not shutil.which("aria2c"):
        raise RuntimeError("`aria2c` binary not found in PATH.")

    os.makedirs(download_dir, exist_ok=True)

    cmd = [
        "aria2c",
        f"--dir={download_dir}",
        "--seed-time=0",
        "--max-upload-limit=1K",
        "--max-connection-per-server=16",
        "--split=16",
        "--min-split-size=1M",
        "--summary-interval=1",
        "--follow-torrent=mem",
        "--enable-dht=true",
        "--enable-peer-exchange=true",
        "--bt-enable-lpd=true",
        "--bt-max-peers=128",
        "--bt-request-peer-speed-limit=100M",
        "--bt-stop-timeout=300",
        "--auto-file-renaming=false",
        "--allow-overwrite=true",
        torrent_source,
    ]

    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        async def _stream_output() -> int:
            last_update = time.time()
            frame_idx = 0
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="ignore").strip()

                now = time.time()
                # Throttled to 4.0s to completely avoid Telegram FloodWait
                if now - last_update >= 4.0:
                    pct_m = re.search(r"\((\d+(?:\.\d+)?)\%\)", decoded)
                    dl_m = re.search(r"DL:([0-9.]+[A-Za-z]+)", decoded)
                    eta_m = re.search(r"ETA:([0-9A-Za-z]+)", decoded)
                    cn_m = re.search(r"CN:(\d+)", decoded)
                    sd_m = re.search(r"SD:(\d+)", decoded)

                    if pct_m and dl_m:
                        pct = float(pct_m.group(1))
                        speed = dl_m.group(1)
                        eta = eta_m.group(1) if eta_m else "N/A"
                        leechers = cn_m.group(1) if cn_m else "0"
                        seeds = sd_m.group(1) if sd_m else "0"

                        bar = render_animated_bar(pct, length=10, frame_idx=frame_idx)
                        frame_idx += 1

                        progress_text = (
                            "<blockquote>⚡ <b>ᴛᴏʀʀᴇɴᴛ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ...</b></blockquote>\n"
                            f"╭─ 📊 <b>ᴘʀᴏɢʀᴇss :</b> <code>{bar} {pct:.1f}%</code>\n"
                            f"├─ 🚀 <b>sᴘᴇᴇᴅ :</b> <code>{speed}/s</code>\n"
                            f"├─ ⏱️ <b>ᴇᴛᴀ :</b> <code>{eta}</code>\n"
                            f"╰─ 👥 <b>sᴇᴇᴅs :</b> <code>{seeds}</code> | <b>ʟᴇᴇᴄʜᴇʀs :</b> <code>{leechers}</code>"
                        )
                        try:
                            await status_msg.edit(progress_text)
                            last_update = now
                        except FloodWait as fw:
                            await asyncio.sleep(fw.value)
                        except Exception:
                            pass

                await asyncio.sleep(0.02)
            return await process.wait()

        return_code = await asyncio.wait_for(_stream_output(), timeout=1800.0)
        return return_code == 0

    except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
        if isinstance(exc, asyncio.TimeoutError):
            logger.error("Aria2 download timed out after 1800.0s")
        else:
            logger.warning("Aria2 download was cancelled")
        if process and process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            except Exception:
                pass
            await process.wait()
        if isinstance(exc, asyncio.CancelledError):
            raise
        return False
    finally:
        if process and process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            except Exception:
                pass
            await process.wait()


async def _mux_audio_stream_copy(
    video_input: str,
    audio_input: str,
    output_path: str,
    max_duration: int = 0,
) -> bool:
    """
    Stream-copy muxing with FFmpeg using ZERO re-encoding to preserve CPU.
    Trims audio at video duration if audio is longer than video.
    Enforces a 300.0s execution timeout and robust child process cleanup.
    """
    dur_args = ["-t", str(max_duration)] if max_duration > 0 else []
    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_input,
        "-i", audio_input,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-map", "0:a?",
        "-map", "0:s?",
        "-c", "copy",
        "-shortest",
        *dur_args,
        "-disposition:a", "0",
        "-disposition:a:0", "default",
        output_path,
    ]

    process = None
    stderr = b""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=300.0)
    except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
        if isinstance(exc, asyncio.TimeoutError):
            logger.error("FFmpeg stream-copy timed out after 300.0s")
        else:
            logger.warning("FFmpeg stream-copy was cancelled")
        if process and process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            except Exception:
                pass
            await process.wait()
        if isinstance(exc, asyncio.CancelledError):
            raise
        return False
    finally:
        if process and process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            except Exception:
                pass
            await process.wait()

    await asyncio.sleep(0.5)

    if process.returncode != 0:
        logger.error("FFmpeg stream-copy error: %s", stderr.decode("utf-8", errors="ignore"))
        return False
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0


# =========================================================================
# SECTION 4: PYROGRAM BOT HANDLERS
# =========================================================================

@Client.on_message(
    filters.private
    & (
        filters.command(["tmux", "torrent", "torrent_audio"])
        | filters.regex(r"^(magnet:\?xt=|https?://.*?\.(torrent))")
    )
)
async def torrent_start(client: Client, message: Message):
    user_id = int(message.from_user.id)

    if await Mythicbotz.is_banned(user_id):
        return await message.reply(
            "<blockquote>🚫 <b>ᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ</b></blockquote>\n"
            "╰─ <b>ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ ꜰʀᴏᴍ ᴜsɪɴɢ ᴛʜɪs ʙᴏᴛ. ᴄᴏɴᴛᴀᴄᴛ @CosmicBotz.</b>"
        )

    torrent_source = None
    if message.matches:
        torrent_source = message.text.strip()
    elif len(message.command) > 1:
        torrent_source = message.text.split(None, 1)[1].strip()
    elif message.reply_to_message and message.reply_to_message.text:
        reply_txt = message.reply_to_message.text.strip()
        if reply_txt.startswith("magnet:?xt=") or ".torrent" in reply_txt:
            torrent_source = reply_txt

    if not torrent_source:
        return await message.reply_text(
            "<blockquote>⚠️ <b>ᴍɪssɪɴɢ ᴛᴏʀʀᴇɴᴛ sᴏᴜʀᴄᴇ</b></blockquote>\n\n"
            "╰─ <i>Send the command along with a magnet link or .torrent URL:</i>\n"
            "<code>/tmux magnet:?xt=urn:btih:...</code>",
            reply_to_message_id=message.id,
        )

    old_task = ACTIVE_TORRENT_TASKS.pop(user_id, None)
    if old_task:
        old_abort_task = old_task.get("auto_abort_task")
        if old_abort_task and not old_abort_task.done():
            old_abort_task.cancel()
        ram_workspace.cleanup_files(old_task.get("torrent_video"))
        if os.path.exists(old_task.get("torrent_dir", "")):
            shutil.rmtree(old_task.get("torrent_dir"), ignore_errors=True)

    status_msg = await message.reply_text(
        "<blockquote>🚀 <b>ɪɴɪᴛɪᴀʟɪᴢɪɴɢ ᴛᴏʀʀᴇɴᴛ ᴇɴɢɪɴᴇ...</b></blockquote>",
        reply_to_message_id=message.id,
    )

    work_dir = tempfile.mkdtemp(prefix=f"torrent_{user_id}_{int(time.time())}_")

    try:
        success = await _download_torrent_aria2(torrent_source, work_dir, status_msg)
        if not success:
            shutil.rmtree(work_dir, ignore_errors=True)
            return await status_msg.edit("<blockquote>❌ <b>ᴛᴏʀʀᴇɴᴛ ᴅᴏᴡɴʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ. ᴄʜᴇᴄᴋ sᴇᴇᴅs.</b></blockquote>")
    except Exception as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        return await status_msg.edit(f"<blockquote>❌ <b>ᴇʀʀᴏʀ :</b> <code>{e}</code></blockquote>")

    video_file = _find_primary_video(work_dir)
    if not video_file:
        shutil.rmtree(work_dir, ignore_errors=True)
        return await status_msg.edit("<blockquote>❌ <b>ɴᴏ ᴠᴀʟɪᴅ ᴠɪᴅᴇᴏ ꜰɪʟᴇ ꜰᴏᴜɴᴅ ɪɴ ᴛᴏʀʀᴇɴᴛ.</b></blockquote>")

    vid_name = os.path.basename(video_file)
    vid_size = humanbytes(os.path.getsize(video_file))

    prompt = await message.reply_text(
        "<blockquote>🎵 <b>sᴇɴᴅ ᴀᴜᴅɪᴏ / ᴠɪᴅᴇᴏ ᴛᴏ sᴇᴛ ᴀs ᴅᴇꜰᴀᴜʟᴛ</b></blockquote>\n\n"
        f"╭─ 🎬 <b>ᴛᴏʀʀᴇɴᴛ ᴠɪᴅᴇᴏ :</b> <code>{vid_name}</code>\n"
        f"├─ 📦 <b>sɪᴢᴇ :</b> <code>{vid_size}</code>\n"
        "╰─ <i>Reply to this message with an Audio or Video file whose audio track you want to inject as default.</i>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("✖️ Cancel Task & Clean Workspace", callback_data=f"cancel_tmux_{user_id}")]]
        ),
    )

    ACTIVE_TORRENT_TASKS[user_id] = {
        "torrent_video": video_file,
        "torrent_dir": work_dir,
        "torrent_name": vid_name,
        "prompt_id": prompt.id,
        "timestamp": time.time(),
    }

    try:
        await status_msg.delete()
    except Exception:
        pass

    async def _auto_abort():
        try:
            await asyncio.sleep(900)
        except asyncio.CancelledError:
            return
        task = ACTIVE_TORRENT_TASKS.get(user_id)
        if task and task.get("prompt_id") == prompt.id:
            ACTIVE_TORRENT_TASKS.pop(user_id, None)
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)
            try:
                await prompt.edit("<blockquote>⏱️ <b>ᴛᴏʀʀᴇɴᴛ ᴍᴜxɪɴɢ sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ.</b></blockquote>")
            except Exception:
                pass

    abort_task = asyncio.create_task(_auto_abort())
    ACTIVE_TORRENT_TASKS[user_id]["auto_abort_task"] = abort_task


@Client.on_callback_query(filters.regex(r"^cancel_tmux_(\d+)$"))
async def cancel_tmux_callback(bot: Client, query: CallbackQuery):
    target_user_id = int(query.matches[0].group(1))
    if query.from_user.id != target_user_id:
        return await query.answer("⚠️ This is not your task!", show_alert=True)

    task = ACTIVE_TORRENT_TASKS.pop(target_user_id, None)
    if task:
        abort_task = task.get("auto_abort_task")
        if abort_task and not abort_task.done():
            abort_task.cancel()
        torrent_dir = task.get("torrent_dir")
        if torrent_dir and os.path.exists(torrent_dir):
            shutil.rmtree(torrent_dir, ignore_errors=True)

    try:
        await query.message.edit("<blockquote>❌ <b>ᴛᴏʀʀᴇɴᴛ ᴍᴜxɪɴɢ ᴛᴀsᴋ ᴄᴀɴᴄᴇʟʟᴇᴅ & ᴄʟᴇᴀɴᴇᴅ ᴜᴘ.</b></blockquote>")
    except Exception:
        pass
    try:
        await query.answer("Task cancelled & workspace cleaned up.", show_alert=False)
    except Exception:
        pass


@Client.on_message(filters.private & (filters.audio | filters.video | filters.document), group=-2)
async def handle_mux_incoming_file(bot: Client, message: Message):
    # Fast-path check: immediately return if update is not from a user with an active torrent mux task
    if not message.from_user:
        return
    user_id = int(message.from_user.id)
    if user_id not in ACTIVE_TORRENT_TASKS:
        return

    task = ACTIVE_TORRENT_TASKS.get(user_id)
    if not task:
        return

    media = getattr(message, message.media.value) if message.media else None
    if not media:
        return await message.reply_text("<blockquote>⚠️ <b>ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴀ ᴠᴀʟɪᴅ ᴍᴇᴅɪᴀ ꜰɪʟᴇ.</b></blockquote>")

    fname = getattr(media, "file_name", "") or ""
    is_valid_media = (
        message.media in (MessageMediaType.AUDIO, MessageMediaType.VIDEO)
        or fname.lower().endswith(AUDIO_EXTENSIONS + VIDEO_EXTENSIONS)
        or (getattr(media, "mime_type", "") or "").startswith(("audio/", "video/"))
    )

    if not is_valid_media:
        return await message.reply_text("<blockquote>⚠️ <b>ᴛʜɪs ꜰɪʟᴇ ᴅᴏᴇs ɴᴏᴛ ᴄᴏɴᴛᴀɪɴ ᴀ ʀᴇᴄᴏɢɴɪᴢᴇᴅ ᴀᴜᴅɪᴏ/ᴠɪᴅᴇᴏ sᴛʀᴇᴀᴍ.</b></blockquote>")

    # User provided valid media matching active task: claim task and cancel background auto_abort timer
    task = ACTIVE_TORRENT_TASKS.pop(user_id, None)
    if not task:
        return

    abort_task = task.get("auto_abort_task")
    if abort_task and not abort_task.done():
        abort_task.cancel()

    prompt_id = task.get("prompt_id")
    if prompt_id:
        try:
            await bot.delete_messages(chat_id=user_id, message_ids=prompt_id)
        except Exception:
            pass

    try:
        message.stop_propagation()
    except (StopPropagation, Exception):
        pass

    torrent_video = task["torrent_video"]
    torrent_dir = task["torrent_dir"]
    torrent_name = task["torrent_name"]

    user_data = await Mythicbotz.get_user_data(user_id) or {}
    prefix = user_data.get("prefix")
    suffix = user_data.get("suffix")
    _bool_metadata = bool(user_data.get("metadata", False))
    user_metadata_code = user_data.get("metadata_code") or "By :- @CosmicBotz"
    c_caption = user_data.get("caption")
    c_thumb = user_data.get("file_id")
    dest_channel = user_data.get("destination_channel")

    base_out_name = os.path.splitext(torrent_name)[0] + ".mkv"
    try:
        new_filename = add_prefix_suffix(base_out_name, prefix, suffix)
    except Exception:
        new_filename = base_out_name

    user_media_path = os.path.join(torrent_dir, f"input_audio_{media.file_id[:8]}")
    muxed_output_path = os.path.join(torrent_dir, f"muxed_{new_filename}")
    meta_output_path, ph_path, cover_path = None, None, None
    ms = None
    is_success = False

    # Top-level try...finally wraps the entire processing workflow (download, mux, metadata, thumb, upload)
    # to guarantee temp workspace cleanup on success, error, or cancellation.
    try:
        # Step A: Download Audio/Video Replacement Track
        dl_header = "<blockquote>📥 <b>ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ʏᴏᴜʀ ᴀᴜᴅɪᴏ...</b> ⚡</blockquote>"
        ms, dl_start = await init_progress_message(message, dl_header, getattr(media, "file_size", 0) or 0)

        dl_client = getattr(bot, "helper_client", None) or getattr(bot, "premium_client", None) or bot
        try:
            user_media_path = await dl_client.download_media(
                message=message,
                file_name=user_media_path,
                progress=progress_for_pyrogram,
                progress_args=(dl_header, ms, dl_start),
            )
        except Exception as e:
            if ms:
                clear_transfer_cancellation(user_id, ms.id)
                await ms.edit(f"<blockquote>❌ <b>ᴀᴜᴅɪᴏ ᴅᴏᴡɴʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ :</b> <code>{e}</code></blockquote>")
            raise StopPropagation

        # Step B: Zero-encoding Stream Copy Muxing & Audio Trimming
        _, _, video_dur = await probe_video_dimensions_and_duration(torrent_video)
        _, _, audio_dur = await probe_video_dimensions_and_duration(user_media_path)
        target_dur = video_dur or audio_dur
        dur_str = convert(target_dur) if target_dur > 0 else "N/A"
        trim_notice = " (audio trimmed to video length)" if (video_dur > 0 and audio_dur > video_dur) else ""

        if ms:
            await ms.edit(
                "<blockquote>⚙️ <b>ᴍᴜxɪɴɢ ᴀᴜᴅɪᴏ sᴛʀᴇᴀᴍ...</b> ⚡</blockquote>\n"
                f"╭─ ⏱️ <b>ᴅᴜʀᴀᴛɪᴏɴ :</b> <code>{dur_str}</code>{trim_notice}\n"
                "╰─ <i>Lossless stream-copy in progress (zero re-encoding)...</i>"
            )
        await asyncio.sleep(0.5)

        success_mux = await _mux_audio_stream_copy(
            torrent_video, user_media_path, muxed_output_path, max_duration=video_dur
        )
        if not success_mux:
            if ms:
                await ms.edit("<blockquote>❌ <b>ꜰꜰᴍᴘᴇɢ ᴍᴜxɪɴɢ ꜰᴀɪʟᴇᴅ. ᴄʜᴇᴄᴋ ᴀᴜᴅɪᴏ ᴄᴏᴍᴘᴀᴛɪʙɪʟɪᴛʏ.</b></blockquote>")
            raise StopPropagation

        final_upload_path = muxed_output_path

        # Step C: Metadata Application
        if _bool_metadata:
            try:
                if ms:
                    await ms.edit(
                        "<blockquote>🏷️ <b>ᴀᴘᴘʟʏɪɴɢ ᴍᴇᴛᴀᴅᴀᴛᴀ...</b> ⚡</blockquote>\n"
                        "╰─ <i>Writing metadata tags...</i>"
                    )
                meta_dir = os.path.join(torrent_dir, "meta_out")
                os.makedirs(meta_dir, exist_ok=True)
                meta_output_path = os.path.join(meta_dir, new_filename)

                res_meta = await add_metadata(muxed_output_path, meta_output_path, user_metadata_code, ms)
                if res_meta and os.path.exists(meta_output_path):
                    final_upload_path = meta_output_path
            except Exception as e:
                logger.error("Metadata application failed: %s", e)
                final_upload_path = muxed_output_path

        # Step D: Media Probing (Duration, Width, Height)
        duration, width, height = 0, 1280, 720
        try:
            p_w, p_h, p_dur = await probe_video_dimensions_and_duration(final_upload_path)
            if p_w > 0:
                width = int(p_w)
            if p_h > 0:
                height = int(p_h)
            if p_dur > 0:
                duration = int(p_dur)
        except Exception:
            pass

        if not duration or not width or not height:
            def _parse_hachoir_merge_metadata(probe_target_path: str) -> Tuple[int, int, int]:
                dur, w, h = 0, 0, 0
                try:
                    parser = createParser(probe_target_path)
                    if parser:
                        with parser:
                            meta_info = extractMetadata(parser)
                            if meta_info:
                                if meta_info.has("duration"):
                                    dur = meta_info.get("duration").seconds
                                if meta_info.has("width"):
                                    w = int(meta_info.get("width") or 1280)
                                if meta_info.has("height"):
                                    h = int(meta_info.get("height") or 720)
                except Exception:
                    pass
                return dur, w, h

            h_dur, h_w, h_h = await asyncio.to_thread(_parse_hachoir_merge_metadata, final_upload_path)
            if not duration and h_dur:
                duration = h_dur
            if h_w > 0:
                width = h_w
            if h_h > 0:
                height = h_h

        # Step E: Thumbnail Generation
        video_cover = None
        try:
            if c_thumb:
                _, _, ph_path = await get_cached_user_thumb(bot, c_thumb, user_id)
                video_cover = c_thumb or ph_path
            else:
                frame_w, frame_h, ph_path = await extract_auto_thumbnail(
                    bot=bot,
                    video_path=final_upload_path,
                    media=media,
                    duration=duration,
                    user_id=user_id,
                    filename=new_filename,
                    media_type=MessageMediaType.VIDEO,
                    upload_type="video",
                )
                cover_path = get_hd_cover_path(ph_path)
                video_cover = cover_path or ph_path
                if not width and frame_w:
                    width = int(frame_w)
                if not height and frame_h:
                    height = int(frame_h)
        except Exception as e:
            logger.warning("Thumbnail extraction skipped: %s", e)

        # Step F: Caption Construction
        final_size = os.path.getsize(final_upload_path)
        auto_delete_notice = "\n\n<blockquote>🗑️ <b>ᴛʜɪs ꜰɪʟᴇ ᴡɪʟʟ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ɪɴ <code>30 ᴍɪɴᴜᴛᴇs</code>. ꜰᴏʀᴡᴀʀᴅ / sᴀᴠᴇ ɪᴛ ɴᴏᴡ!</b></blockquote>"
        if c_caption:
            try:
                caption = c_caption.format(
                    filename=f"<b>{new_filename}</b>",
                    filesize=humanbytes(final_size),
                    duration=convert(duration),
                ) + auto_delete_notice
            except Exception:
                caption = f"<b>{new_filename}</b>" + auto_delete_notice
        else:
            caption = f"<b>{new_filename}</b>" + auto_delete_notice

        # Step G: Multi-Socket Turbo Upload
        ul_header = "<blockquote>💠 <b>ᴜᴘʟᴏᴀᴅɪɴɢ ᴍᴜxᴇᴅ ᴍᴇᴅɪᴀ...</b> ⚡</blockquote>"
        ms, ul_start = await init_progress_message(ms, ul_header, final_size)

        try:
            sent_message = await bot.send_video(
                chat_id=user_id,
                video=final_upload_path,
                file_name=new_filename,
                caption=caption,
                duration=duration,
                width=width,
                height=height,
                supports_streaming=True,
                thumb=ph_path,
                video_cover=video_cover,
                progress=progress_for_pyrogram,
                progress_args=(ul_header, ms, ul_start),
            )

            if Config.BIN_CHANNEL:
                try:
                    bin_caption = (
                        f"<blockquote>🎬 <b>{new_filename}</b></blockquote>\n"
                        f"╭─ 👤 <b>ᴜsᴇʀ :</b> {message.chat.first_name} (<code>{user_id}</code>)\n"
                        f"├─ 📦 <b>sɪZsᴇ :</b> <code>{humanbytes(final_size)}</code>\n"
                        f"╰─ ⏱️ <b>ᴅᴜʀᴀᴛɪᴏɴ :</b> <code>{convert(duration)}</code>"
                    )
                    await bot.copy_message(
                        chat_id=Config.BIN_CHANNEL,
                        from_chat_id=user_id,
                        message_id=sent_message.id,
                        caption=bin_caption,
                    )
                except Exception as e:
                    logger.error("Failed copying to BIN_CHANNEL: %s", e)

            if dest_channel:
                try:
                    await bot.copy_message(
                        chat_id=int(dest_channel),
                        from_chat_id=user_id,
                        message_id=sent_message.id,
                    )
                except Exception as e:
                    logger.error("Failed copying to dest_channel: %s", e)

            await Mythicbotz.increase_rename_count(user_id)
            asyncio.create_task(_delayed_delete(sent_message, delay=1800.0))
            is_success = True

        except StopTransmission:
            if ms:
                clear_transfer_cancellation(user_id, ms.id)
            raise StopPropagation
        except FloodWait as e:
            await asyncio.sleep(e.value)
            raise StopPropagation
        except Exception as e:
            logger.error("Upload failed: %s", e)
            if ms:
                clear_transfer_cancellation(user_id, ms.id)
                await ms.edit(f"<blockquote>❌ <b>ᴜᴘʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ :</b> <code>{e}</code></blockquote>")
            raise StopPropagation

    except StopPropagation:
        raise
    except Exception as e:
        logger.error("Torrent mux processing unexpected failure: %s", e)
        if ms:
            try:
                await ms.edit(f"<blockquote>❌ <b>ᴘʀᴏᴄᴇssɪɴɢ ꜰᴀɪʟᴇᴅ :</b> <code>{e}</code></blockquote>")
            except Exception:
                pass
        raise StopPropagation
    finally:
        ram_workspace.cleanup_files(ph_path, cover_path, meta_output_path)
        if torrent_dir and os.path.exists(torrent_dir):
            shutil.rmtree(torrent_dir, ignore_errors=True)
        if is_success and ms:
            try:
                await ms.delete()
            except Exception:
                pass

    raise StopPropagation