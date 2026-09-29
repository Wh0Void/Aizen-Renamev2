import os
import re
import time
import asyncio
import logging
from asyncio import sleep

from pyrogram import Client, filters, StopTransmission
from pyrogram.types import ForceReply
from pyrogram.errors import FloodWait

from helper.database import Mythicbotz
from helper.ffmpeg import (
    is_video_file,
    probe_video_dimensions_and_duration,
    extract_auto_thumbnail,
    get_cached_user_thumb,
    get_hd_cover_path,
    add_metadata,
)
from helper.utils import (
    progress_for_pyrogram,
    init_progress_message,
    convert,
    humanbytes,
    clear_transfer_cancellation,
)
from bot.core.cache import ram_workspace
from config import Config

logger = logging.getLogger(__name__)

# State cache mapping user_id -> ongoing process metadata
# {user_id: {"torrent_path": str, "orig_filename": str, "file_size": int, "step": str}}
TORRENT_MERGE_SESSIONS = {}


async def _aria2_download(magnet_or_url: str, output_dir: str, ms) -> str:
    """Download torrent/magnet via aria2c CLI, throttling CPU usage for Koyeb."""
    cmd = [
        "aria2c",
        "--allow-overwrite=true",
        "--auto-file-renaming=false",
        "--file-allocation=none",   # Saves CPU/disk overhead on containerized FS
        "--seed-time=0",            # Stop immediately after download completes
        "--max-connection-per-server=4",
        f"--dir={output_dir}",
        magnet_or_url,
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    last_update = 0
    while process.returncode is None:
        await asyncio.sleep(3.0)  # Gentle interval to prevent Koyeb worker saturation
        if process.stdout:
            line = await process.stdout.readline()
            if not line:
                if process.returncode is not None:
                    break
                continue
            text = line.decode(errors="ignore").strip()
            # Catch Aria2 progress line format (e.g., [#... 12MiB/100MiB(12%) CN:1 ETA:1m])
            if text.startswith("[#") and time.time() - last_update > 4.0:
                try:
                    await ms.edit(
                        f"<blockquote>📥 <b>ᴛᴏʀʀᴇɴᴛ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ...</b></blockquote>\n"
                        f"╰─ <code>{text[:120]}</code>"
                    )
                    last_update = time.time()
                except Exception:
                    pass

    await process.wait()

    # Find the largest media file inside output_dir
    largest_file = None
    max_size = 0
    for root, _, files in os.walk(output_dir):
        for f in files:
            fp = os.path.join(root, f)
            sz = os.path.getsize(fp)
            if sz > max_size:
                max_size = sz
                largest_file = fp

    if not largest_file:
        raise FileNotFoundError("No downloaded file found from torrent.")
    return largest_file


async def _merge_and_set_default_audio(video_in: str, audio_source: str, output_file: str) -> bool:
    """
    Merges audio into video with ZERO re-encoding (-c copy).
    Marks the new track as the default audio track.
    Accepts both audio-only files or existing video files as audio source.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", video_in,           # [0:v] video stream
        "-i", audio_source,       # [1:a] audio stream
        "-map", "0:v:0",          # Retain primary video
        "-map", "1:a:0",          # Add new track as primary audio
        "-map", "0:a?",           # Keep remaining existing audio tracks (optional)
        "-c", "copy",             # No CPU-heavy re-encoding
        "-disposition:a:0", "default",  # Set new audio track as default
        "-disposition:a:1", "0",        # Demote previous default
        output_file
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await proc.communicate()
    return proc.returncode == 0 and os.path.exists(output_file) and os.path.getsize(output_file) > 0


@Client.on_message(filters.private & filters.regex(r"^(magnet:\?xt=urn:btih:|http[s]?://.*\.torrent)"))
async def start_torrent_process(client: Client, message):
    user_id = message.from_user.id

    if await Mythicbotz.is_banned(user_id):
        return await message.reply("<blockquote>🚫 <b>ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ.</b></blockquote>")

    link = message.text.strip()
    status_msg = await message.reply("<blockquote>⚡ <b>ɪɴɪᴛɪᴀʟɪᴢɪɴɢ ᴛᴏʀʀᴇɴᴛ...</b></blockquote>")

    job_dir = os.path.join("/tmp", f"torrent_{user_id}_{int(time.time())}")
    os.makedirs(job_dir, exist_ok=True)

    try:
        downloaded_file = await _aria2_download(link, job_dir, status_msg)
    except Exception as e:
        logger.error(f"Torrent DL error: {e}")
        return await status_msg.edit(f"<blockquote>❌ <b>ᴛᴏʀʀᴇɴᴛ ᴅᴏᴡɴʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ:</b></blockquote>\n<code>{e}</code>")

    file_size = os.path.getsize(downloaded_file)
    orig_name = os.path.basename(downloaded_file)

    if file_size > 2000 * 1024 * 1024:
        ram_workspace.cleanup_files(downloaded_file)
        return await status_msg.edit("<blockquote>⚠️ <b>ꜰɪʟᴇ ᴇxᴄᴇᴇᴅs 2 ɢʙ ʟɪᴍɪᴛ.</b></blockquote>")

    # Save session awaiting the user's audio track
    TORRENT_MERGE_SESSIONS[user_id] = {
        "torrent_path": downloaded_file,
        "orig_filename": orig_name,
        "file_size": file_size,
        "job_dir": job_dir,
        "status_msg_id": status_msg.id,
    }

    # Yield execution so Koyeb worker remains responsive
    await asyncio.sleep(1.0)

    prompt = (
        "<blockquote>🎵 <b>sᴇɴᴅ ᴀᴜᴅɪᴏ ᴏʀ ᴠɪᴅᴇᴏ ꜰɪʟᴇ</b></blockquote>\n\n"
        f"╭─ 📦 <b>ᴛᴏʀʀᴇɴᴛ ꜰɪʟᴇ:</b> <code>{orig_name}</code>\n"
        f"╰─ ⏱️ <i>Send the audio/video whose default track you want to inject. Reply to this prompt.</i>"
    )

    await status_msg.edit(prompt)
    await message.reply_text(
        "╰─ <b>ᴘʟᴇᴀsᴇ ʀᴇᴘʟʏ ʜᴇʀᴇ ᴡɪᴛʜ ᴛʜᴇ ᴀᴜᴅɪᴏ/ᴠɪᴅᴇᴏ ᴍᴇᴅɪᴀ:</b>",
        reply_markup=ForceReply(selective=True),
    )


@Client.on_message(filters.private & (filters.audio | filters.video | filters.document) & filters.reply)
async def receive_audio_and_merge(bot: Client, message):
    user_id = message.from_user.id
    reply_msg = message.reply_to_message

    if not reply_msg or not reply_msg.reply_markup or not isinstance(reply_msg.reply_markup, ForceReply):
        return

    session = TORRENT_MERGE_SESSIONS.pop(user_id, None)
    if not session:
        return await message.reply("<blockquote>⚠️ <b>ɴᴏ ᴀᴄᴛɪᴠᴇ ᴛᴏʀʀᴇɴᴛ sᴇssɪᴏɴ ꜰᴏᴜɴᴅ.</b></blockquote>")

    torrent_path = session["torrent_path"]
    job_dir = session["job_dir"]
    orig_filename = session["orig_filename"]

    # Target output naming
    output_filename = f"Merged_{orig_filename}"
    if not output_filename.endswith(".mkv"):
        output_filename = f"{os.path.splitext(output_filename)[0]}.mkv"

    merged_output = os.path.join(job_dir, output_filename)
    audio_temp_path = os.path.join(job_dir, "incoming_audio")

    ms = await message.reply("<blockquote>📥 <b>ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ᴀᴜᴅɪᴏ sᴏᴜʀᴄᴇ...</b></blockquote>")

    dl_client = getattr(bot, "helper_client", None) or bot
    try:
        # Download incoming audio/video track
        audio_file = await dl_client.download_media(
            message=message,
            file_name=audio_temp_path
        )
        await ms.edit("<blockquote>⚙️ <b>ᴍᴇʀɢɪɴɢ ᴀᴜᴅɪᴏ (sᴛʀᴇᴀᴍ ᴄᴏᴘʏ)...</b></blockquote>")
        await asyncio.sleep(1.0)  # Gentle spacing for Koyeb resources

        # Zero-encoding merge
        success = await _merge_and_set_default_audio(torrent_path, audio_file, merged_output)
        if not success:
            raise RuntimeError("FFmpeg stream-copy muxing failed.")

    except Exception as e:
        logger.error(f"Merge error: {e}")
        ram_workspace.cleanup_files(torrent_path, job_dir)
        return await ms.edit(f"<blockquote>❌ <b>ᴍᴇʀɢᴇ ꜰᴀɪʟᴇᴅ:</b></blockquote>\n<code>{e}</code>")

    # Apply Metadata (Zero-encoding)
    user_data = await Mythicbotz.get_user_data(user_id) or {}
    bool_metadata = bool(user_data.get("metadata", False))
    meta_code = user_data.get("metadata_code") or "By :- @CosmicBotz"
    c_thumb = user_data.get("file_id")

    final_upload_path = merged_output
    metadata_path = None

    if bool_metadata:
        await ms.edit("<blockquote>🏷️ <b>ᴀᴘᴘʟʏɪɴɢ ᴍᴇᴛᴀᴅᴀᴛᴀ...</b></blockquote>")
        meta_dir = os.path.join(job_dir, "meta_out")
        os.makedirs(meta_dir, exist_ok=True)
        metadata_path = os.path.join(meta_dir, output_filename)
        try:
            res_meta = await add_metadata(merged_output, metadata_path, meta_code, ms)
            if res_meta and os.path.exists(metadata_path):
                final_upload_path = metadata_path
        except Exception as err:
            logger.warning(f"Metadata skipping: {err}")

    # Probe duration and dimension
    width, height, duration = 1280, 720, 0
    try:
        p_w, p_h, p_dur = await probe_video_dimensions_and_duration(final_upload_path)
        width = int(p_w) if p_w > 0 else width
        height = int(p_h) if p_h > 0 else height
        duration = int(p_dur) if p_dur > 0 else 0
    except Exception:
        pass

    # Thumbnail extraction / User thumb
    ph_path, video_cover = None, None
    try:
        if c_thumb:
            _, _, ph_path = await get_cached_user_thumb(bot, c_thumb, user_id)
            video_cover = c_thumb or ph_path
        else:
            _, _, ph_path = await extract_auto_thumbnail(
                bot=bot,
                video_path=final_upload_path,
                media=None,
                duration=duration,
                user_id=user_id,
                filename=output_filename,
                media_type="video",
                upload_type="video",
            )
            video_cover = get_hd_cover_path(ph_path) or ph_path
    except Exception as e:
        logger.warning(f"Thumb extraction error: {e}")

    # Upload final video
    ul_header = "<blockquote>💠 <b>ᴜᴘʟᴏᴀᴅɪɴɢ ᴍᴇʀɢᴇᴅ ᴠɪᴅᴇᴏ...</b> ⚡</blockquote>"
    upload_size = os.path.getsize(final_upload_path)
    ms, ul_start = await init_progress_message(ms, ul_header, upload_size)

    try:
        sent_message = await bot.send_video(
            chat_id=user_id,
            video=final_upload_path,
            file_name=output_filename,
            caption=f"<b>{output_filename}</b>\n╰─ ⏱️ <code>{convert(duration)}</code> | 📦 <code>{humanbytes(upload_size)}</code>",
            duration=duration,
            width=width,
            height=height,
            supports_streaming=True,
            thumb=ph_path,
            video_cover=video_cover,
            progress=progress_for_pyrogram,
            progress_args=(ul_header, ms, ul_start),
        )

        await ms.delete()
        await Mythicbotz.increase_rename_count(user_id)

    except FloodWait as e:
        await sleep(e.value)
    except Exception as e:
        logger.error(f"Upload error: {e}")
        await ms.edit(f"<blockquote>❌ <b>ᴜᴘʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ:</b></blockquote>\n<code>{e}</code>")
    finally:
        clear_transfer_cancellation(user_id, ms.id)
        ram_workspace.cleanup_files(job_dir, ph_path, video_cover)