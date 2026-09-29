import os
import re
import time
import shutil
import asyncio
import logging
from asyncio import sleep

from pyrogram import Client, filters, StopTransmission
from pyrogram.enums import MessageMediaType
from pyrogram.errors import FloodWait
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ForceReply,
    Message,
)
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser

from helper.ffmpeg import (
    extract_auto_thumbnail,
    get_cached_user_thumb,
    get_hd_cover_path,
    is_video_file,
    probe_video_dimensions_and_duration,
    add_metadata,
)
from helper.utils import (
    progress_for_pyrogram,
    init_progress_message,
    convert,
    humanbytes,
    add_prefix_suffix,
    clear_transfer_cancellation,
)
from helper.database import Mythicbotz
from bot.core.cache import ram_workspace
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User active tasks: user_id -> task_dict
# Format: { "torrent_file": path, "torrent_dir": path, "torrent_name": name, "timestamp": time.time(), "prompt_id": msg_id }
ACTIVE_TORRENT_TASKS = {}

VIDEO_EXTENSIONS = (".mkv", ".mp4", ".avi", ".mov", ".webm", ".ts", ".m4v", ".flv")
AUDIO_EXTENSIONS = (".mp3", ".aac", ".m4a", ".flac", ".wav", ".opus", ".ogg", ".ac3", ".eac3", ".dts")


async def _delayed_delete(*messages, delay: float = 1800.0) -> None:
    """Background task to auto-delete messages after `delay` seconds."""
    await asyncio.sleep(delay)
    for msg in messages:
        if msg is not None:
            try:
                await msg.delete()
            except Exception as e:
                logger.debug(f"Delayed message delete skipped: {e}")


def _find_primary_video(target_dir: str) -> str | None:
    """Finds the largest video file within the downloaded directory."""
    if os.path.isfile(target_dir):
        return target_dir

    candidate = None
    max_size = 0
    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.lower().endswith(VIDEO_EXTENSIONS):
                full_path = os.path.join(root, file)
                sz = os.path.getsize(full_path)
                if sz > max_size:
                    max_size = sz
                    candidate = full_path
    return candidate


async def _download_torrent_aria2(torrent_source: str, download_dir: str, status_msg: Message) -> bool:
    """
    Downloads torrent using aria2c without overwhelming CPU on Koyeb.
    Parses progress every 4-5 seconds to avoid Telegram FloodWait.
    """
    if not shutil.which("aria2c"):
        raise RuntimeError("`aria2c` is not installed on this system.")

    os.makedirs(download_dir, exist_ok=True)

    cmd = [
        "aria2c",
        f"--dir={download_dir}",
        "--seed-time=0",
        "--max-upload-limit=1K",
        "--max-connection-per-server=8",
        "--split=8",
        "--summary-interval=3",
        "--follow-torrent=mem",
        "--auto-file-renaming=false",
        "--allow-overwrite=true",
        torrent_source,
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    last_update = time.time()
    aria_regex = re.compile(r"\((\d+)\%\).*?DL:([0-9.]+[A-Za-z]+).*?ETA:([0-9A-Za-z]+)")

    while True:
        line = await process.stdout.readline()
        if not line:
            break
        decoded_line = line.decode("utf-8", errors="ignore").strip()

        # Throttled progress update to keep Koyeb CPU/RAM calm
        if time.time() - last_update > 4.5:
            match = aria_regex.search(decoded_line)
            if match:
                percent, speed, eta = match.groups()
                try:
                    await status_msg.edit(
                        "<blockquote>⚡ <b>ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ᴛᴏʀʀᴇɴᴛ...</b></blockquote>\n"
                        f"╭─ 📊 <b>ᴘʀᴏɢʀᴇss :</b> <code>{percent}%</code>\n"
                        f"├─ 🚀 <b>sᴘᴇᴇᴅ :</b> <code>{speed}/s</code>\n"
                        f"╰─ ⏱️ <b>ᴇᴛᴀ :</b> <code>{eta}</code>"
                    )
                    last_update = time.time()
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception:
                    pass

        # Give back time to the event loop
        await asyncio.sleep(0.05)

    return_code = await process.wait()
    return return_code == 0


async def _mux_audio_stream_copy(video_input: str, audio_input: str, output_path: str) -> bool:
    """
    Fast stream-copy muxing using FFmpeg with ZERO re-encoding.
    Maps:
      - Torrent video: 0:v:0
      - User's audio: 1:a:0 (placed first)
      - Torrent's original audios: 0:a? (preserved as secondary tracks)
      - Subtitles: 0:s? (all subtitles preserved)
    Sets user audio track as the default audio track.
    """
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
        "-disposition:a", "0",          # Clear default flag on all audio tracks
        "-disposition:a:0", "default",  # Set newly added audio track as default
        output_path,
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    _, stderr = await process.communicate()

    # Small pause to yield CPU on Koyeb
    await asyncio.sleep(0.5)

    if process.returncode != 0:
        logger.error(f"FFmpeg stream copy error: {stderr.decode('utf-8', errors='ignore')}")
        return False
    return os.path.exists(output_path) and os.path.getsize(output_path) > 0


# ==========================================
# STEP 1: INITIATE TORRENT DOWNLOAD
# ==========================================

@Client.on_message(filters.private & (filters.command(["tmux", "torrent", "torrent_audio"]) | filters.regex(r"^(magnet:\?xt=|https?://.*?\.(torrent))")))
async def torrent_start(client: Client, message: Message):
    user_id = int(message.from_user.id)

    # Fast RAM-cached ban check
    if await Mythicbotz.is_banned(user_id):
        return await message.reply(
            "<blockquote>🚫 <b>ᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ</b></blockquote>\n"
            "╰─ <b>ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ ꜰʀᴏᴍ ᴜsɪɴɢ ᴛʜɪs ʙᴏᴛ. ᴄᴏɴᴛᴀᴄᴛ @CosmicBotz.</b>"
        )

    # Extract source link/magnet
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

    # Clean up previous pending task if exists
    old_task = ACTIVE_TORRENT_TASKS.pop(user_id, None)
    if old_task:
        ram_workspace.cleanup_files(old_task.get("torrent_file"))
        if os.path.exists(old_task.get("torrent_dir", "")):
            shutil.rmtree(old_task.get("torrent_dir"), ignore_errors=True)

    status_msg = await message.reply_text(
        "<blockquote>🚀 <b>ɪɴɪᴛɪᴀʟɪᴢɪɴɢ ᴛᴏʀʀᴇɴᴛ ᴅᴏᴡɴʟᴏᴀᴅ...</b></blockquote>",
        reply_to_message_id=message.id,
    )

    # Isolated job directory
    work_dir = os.path.join("/tmp", f"torrent_{user_id}_{int(time.time())}")
    os.makedirs(work_dir, exist_ok=True)

    try:
        success = await _download_torrent_aria2(torrent_source, work_dir, status_msg)
        if not success:
            shutil.rmtree(work_dir, ignore_errors=True)
            return await status_msg.edit("<blockquote>❌ <b>ᴛᴏʀʀᴇɴᴛ ᴅᴏᴡɴʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ. ᴄʜᴇᴄᴋ ᴛʜᴇ ʟɪɴᴋ ᴏʀ sᴇᴇᴅs.</b></blockquote>")
    except Exception as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        logger.error(f"Torrent error: {e}")
        return await status_msg.edit(f"<blockquote>❌ <b>ᴇʀʀᴏʀ :</b> <code>{e}</code></blockquote>")

    video_file = _find_primary_video(work_dir)
    if not video_file:
        shutil.rmtree(work_dir, ignore_errors=True)
        return await status_msg.edit("<blockquote>❌ <b>ɴᴏ ᴠᴀʟɪᴅ ᴠɪᴅᴇᴏ ꜰɪʟᴇ ꜰᴏᴜɴᴅ ɪɴ ᴛᴏʀʀᴇɴᴛ.</b></blockquote>")

    vid_name = os.path.basename(video_file)
    vid_size = humanbytes(os.path.getsize(video_file))

    # Ask user for replacement audio/video
    prompt = await message.reply_text(
        "<blockquote>🎵 <b>sᴇɴᴅ ᴀᴜᴅɪᴏ / ᴠɪᴅᴇᴏ ᴛᴏ sᴇᴛ ᴀs ᴅᴇꜰᴀᴜʟᴛ</b></blockquote>\n\n"
        f"╭─ 🎬 <b>ᴛᴏʀʀᴇɴᴛ ᴠɪᴅᴇᴏ :</b> <code>{vid_name}</code>\n"
        f"├─ 📦 <b>sɪᴢᴇ :</b> <code>{vid_size}</code>\n"
        "╰─ <i>Reply to this message with an Audio or Video file whose audio track you want to inject as default.</i>",
        reply_markup=ForceReply(True),
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

    # Expire pending session after 15 minutes to save storage
    async def _auto_abort():
        await asyncio.sleep(900)
        task = ACTIVE_TORRENT_TASKS.get(user_id)
        if task and task.get("prompt_id") == prompt.id:
            ACTIVE_TORRENT_TASKS.pop(user_id, None)
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)
            try:
                await prompt.edit("<blockquote>⏱️ <b>ᴛᴏʀʀᴇɴᴛ ᴍᴜxɪɴɢ sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ.</b></blockquote>")
            except Exception:
                pass

    asyncio.create_task(_auto_abort())


# ==========================================
# STEP 2: RECEIVE AUDIO/VIDEO & MUX & UPLOAD
# ==========================================

@Client.on_message(filters.private & filters.reply & (filters.audio | filters.video | filters.document))
async def handle_mux_reply(bot: Client, message: Message):
    user_id = int(message.from_user.id)
    reply_msg = message.reply_to_message

    if not (reply_msg and reply_msg.reply_markup and isinstance(reply_msg.reply_markup, ForceReply)):
        return

    task = ACTIVE_TORRENT_TASKS.get(user_id)
    if not task or task.get("prompt_id") != reply_msg.id:
        return

    # Check if replied media is valid audio or video
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

    # Lock session so duplicate messages are ignored
    ACTIVE_TORRENT_TASKS.pop(user_id, None)

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

    # Ensure output has .mkv extension for lossless multi-stream copying
    base_out_name = os.path.splitext(torrent_name)[0] + ".mkv"
    try:
        new_filename = add_prefix_suffix(base_out_name, prefix, suffix)
    except Exception:
        new_filename = base_out_name

    # Prepare temporary paths
    user_media_path = os.path.join(torrent_dir, f"input_audio_{media.file_id[:8]}")
    muxed_output_path = os.path.join(torrent_dir, f"muxed_{new_filename}")
    meta_output_path = None
    ph_path = None
    cover_path = None

    # Step A: Download user's audio/video
    dl_header = "<blockquote>📥 <b>ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ʏᴏᴜʀ ᴀᴜᴅɪᴏ ꜰɪʟᴇ...</b> ⚡</blockquote>"
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
        logger.error(f"Failed downloading user audio: {e}")
        clear_transfer_cancellation(user_id, ms.id)
        shutil.rmtree(torrent_dir, ignore_errors=True)
        return await ms.edit(f"<blockquote>❌ <b>ᴀᴜᴅɪᴏ ᴅᴏᴡɴʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ :</b> <code>{e}</code></blockquote>")

    # Step B: Stream-copy Muxing without re-encoding
    await ms.edit(
        "<blockquote>⚙️ <b>ᴍᴜxɪɴɢ ᴀᴜᴅɪᴏ sᴛʀᴇᴀᴍ...</b> ⚡</blockquote>\n"
        "╰─ <i>Lossless stream-copy in progress (no re-encoding)...</i>"
    )
    # Koyeb pause
    await asyncio.sleep(1.0)

    success_mux = await _mux_audio_stream_copy(torrent_video, user_media_path, muxed_output_path)
    if not success_mux:
        shutil.rmtree(torrent_dir, ignore_errors=True)
        return await ms.edit("<blockquote>❌ <b>ꜰꜰᴍᴘᴇɢ ᴍᴜxɪɴɢ ꜰᴀɪʟᴇᴅ. ᴄʜᴇᴄᴋ ᴀᴜᴅɪᴏ ᴄᴏᴍᴘᴀᴛɪʙɪʟɪᴛʏ.</b></blockquote>")

    final_upload_path = muxed_output_path

    # Step C: Metadata Addition (if enabled)
    if _bool_metadata:
        try:
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
            logger.error(f"Metadata application failed: {e}")
            final_upload_path = muxed_output_path

    # Step D: Probe media information (duration, width, height)
    duration, width, height = 0, 1280, 720
    try:
        p_w, p_h, p_dur = await probe_video_dimensions_and_duration(final_upload_path)
        if p_w > 0:
            width = int(p_w)
        if p_h > 0:
            height = int(p_h)
        if p_dur > 0:
            duration = int(p_dur)
    except Exception as e:
        logger.debug(f"ffprobe extraction fallback: {e}")

    if not duration or not width or not height:
        try:
            parser = createParser(final_upload_path)
            if parser:
                with parser:
                    meta_info = extractMetadata(parser)
                    if meta_info:
                        if not duration and meta_info.has("duration"):
                            duration = meta_info.get("duration").seconds
                        if meta_info.has("width"):
                            width = int(meta_info.get("width") or 1280)
                        if meta_info.has("height"):
                            height = int(meta_info.get("height") or 720)
        except Exception as e:
            logger.debug(f"Hachoir extraction skipped: {e}")

    # Step E: Handle Custom Thumbnail / Auto-thumbnail
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
        logger.warning(f"Thumbnail generation skipped: {e}")

    # Step F: Format Caption
    final_size = os.path.getsize(final_upload_path)
    if c_caption:
        try:
            caption = c_caption.format(
                filename=f"<b>{new_filename}</b>",
                filesize=humanbytes(final_size),
                duration=convert(duration),
            )
        except Exception:
            caption = f"<b>{new_filename}</b>"
    else:
        caption = f"<b>{new_filename}</b>"

    # Step G: Upload Video to Telegram
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

        # Mirror to BIN_CHANNEL
        if Config.BIN_CHANNEL:
            try:
                bin_caption = (
                    f"<blockquote>🎬 <b>{new_filename}</b></blockquote>\n"
                    f"╭─ 👤 <b>ᴜsᴇʀ :</b> {message.chat.first_name} (<code>{user_id}</code>)\n"
                    f"├─ 📦 <b>sɪᴢᴇ :</b> <code>{humanbytes(final_size)}</code>\n"
                    f"╰─ ⏱️ <b>ᴅᴜʀᴀᴛɪᴏɴ :</b> <code>{convert(duration)}</code>"
                )
                await bot.copy_message(
                    chat_id=Config.BIN_CHANNEL,
                    from_chat_id=user_id,
                    message_id=sent_message.id,
                    caption=bin_caption,
                )
            except Exception as e:
                logger.error(f"Failed copying to BIN_CHANNEL: {e}")

        # Mirror to Destination Channel
        if dest_channel:
            try:
                await bot.copy_message(
                    chat_id=int(dest_channel),
                    from_chat_id=user_id,
                    message_id=sent_message.id,
                )
            except Exception as e:
                logger.error(f"Failed copying to dest_channel: {e}")

        # Update stats
        await Mythicbotz.increase_rename_count(user_id)

        deletion_msg = await sent_message.reply(
            "<blockquote>🗑️ <b>ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ɴᴏᴛɪᴄᴇ</b></blockquote>\n"
            "╰─ <b>ᴛʜɪs ꜰɪʟᴇ ᴡɪʟʟ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ɪɴ <code>30 ᴍɪɴᴜᴛᴇs</code>. ꜰᴏʀᴡᴀʀᴅ / sᴀᴠᴇ ɪᴛ ɴᴏᴡ!</b>"
        )
        asyncio.create_task(_delayed_delete(sent_message, deletion_msg, delay=1800.0))

    except StopTransmission:
        clear_transfer_cancellation(user_id, ms.id)
        return
    except FloodWait as e:
        await sleep(e.value)
        return
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        clear_transfer_cancellation(user_id, ms.id)
        return await ms.edit(f"<blockquote>❌ <b>ᴜᴘʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ :</b> <code>{e}</code></blockquote>")
    finally:
        # Full workspace cleanup to maintain Koyeb disk quota
        ram_workspace.cleanup_files(ph_path, cover_path, meta_output_path)
        if os.path.exists(torrent_dir):
            shutil.rmtree(torrent_dir, ignore_errors=True)
        try:
            await ms.delete()
            await reply_msg.delete()
        except Exception:
            pass