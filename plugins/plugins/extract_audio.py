import os
import sys
import time
import shutil
import asyncio
import logging
import re
from typing import Optional, Dict, Any

from pyrogram import Client, filters, StopTransmission
from pyrogram.enums import MessageMediaType
from pyrogram.errors import FloodWait
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from config import Config
from helper.database import Mythicbotz
from helper.ffmpeg import probe_video_dimensions_and_duration, get_cached_user_thumb
from helper.utils import (
    humanbytes,
    convert,
    init_progress_message,
    progress_for_pyrogram,
    add_prefix_suffix,
    clear_transfer_cancellation,
)
from bot.core.cache import ram_workspace
from bot.core.fast_crypto import MultiSessionMediaPool

logger = logging.getLogger(__name__)

ACTIVE_EXTRACT_AUDIO_TASKS: Dict[int, Dict[str, Any]] = {}


async def _delayed_delete(*messages, delay: float = 1800.0) -> None:
    await asyncio.sleep(delay)
    for msg in messages:
        if msg is not None:
            try:
                await msg.delete()
            except Exception:
                pass


async def extract_audio_from_video(
    input_path: str,
    output_path: str,
    codec_option: str = "copy",
) -> bool:
    """
    Extracts audio stream from input video file using FFmpeg.
    Supports lossless stream copy ('copy') or re-encoding ('mp3', 'aac', 'opus').
    """
    if codec_option == "copy":
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", input_path,
            "-vn",
            "-c:a", "copy",
            output_path,
        ]
    elif codec_option == "mp3":
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", input_path,
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", "320k",
            output_path,
        ]
    elif codec_option == "aac":
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", input_path,
            "-vn",
            "-c:a", "aac",
            "-b:a", "256k",
            output_path,
        ]
    elif codec_option == "opus":
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", input_path,
            "-vn",
            "-c:a", "libopus",
            "-b:a", "192k",
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", input_path,
            "-vn",
            "-c:a", "copy",
            output_path,
        ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()

    if process.returncode != 0:
        logger.error("FFmpeg audio extraction error: %s", stderr.decode("utf-8", errors="ignore"))
        # Fallback to copy if encoding failed
        if codec_option != "copy":
            fallback_cmd = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel", "error",
                "-i", input_path,
                "-vn",
                "-c:a", "copy",
                output_path,
            ]
            fb_proc = await asyncio.create_subprocess_exec(
                *fallback_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await fb_proc.communicate()
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0

    return os.path.exists(output_path) and os.path.getsize(output_path) > 0


@Client.on_message(
    filters.private
    & (
        filters.command(["extract_audio", "extract", "ea", "audio_extract"])
    )
)
async def extract_audio_command(client: Client, message: Message):
    user_id = int(message.from_user.id)

    if await Mythicbotz.is_banned(user_id):
        return await message.reply(
            "<blockquote>🚫 <b>ᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ</b></blockquote>\n"
            "╰─ <b>ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ ꜰᴏᴍ ᴜsɪɴɢ ᴛʜɪs ʙᴏᴛ. ᴄᴏɴᴛᴀᴄᴛ @CosmicBotz.</b>"
        )

    target_msg = message.reply_to_message
    if not target_msg or not getattr(target_msg, "media", None):
        return await message.reply_text(
            "<blockquote>🎧 <b>ᴀᴜᴅɪᴏ ᴇxᴛʀᴀᴄᴛɪᴏɴ ᴇɴɢɪɴᴇ</b></blockquote>\n\n"
            "╰─ <i>Reply to any Video or Document message with <code>/extract_audio</code> or <code>/ea</code> to extract its audio track instantly!</i>",
            reply_to_message_id=message.id,
        )

    media = getattr(target_msg, target_msg.media.value)
    filename = getattr(media, "file_name", None) or "video.mkv"
    file_size = getattr(media, "file_size", 0) or 0

    # Inline format selection keyboard
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⚡ Stream Copy (Lossless)", callback_data=f"extaudio_{target_msg.id}_copy"),
                InlineKeyboardButton("🎵 MP3 (320 kbps)", callback_data=f"extaudio_{target_msg.id}_mp3"),
            ],
            [
                InlineKeyboardButton("🎧 AAC / M4A", callback_data=f"extaudio_{target_msg.id}_aac"),
                InlineKeyboardButton("🔊 Opus / OGG", callback_data=f"extaudio_{target_msg.id}_opus"),
            ],
            [
                InlineKeyboardButton("✖️ Cancel", callback_data=f"cancel_extaudio_{user_id}"),
            ],
        ]
    )

    await message.reply_text(
        "<blockquote>🎧 <b>sᴇʟᴇᴄᴛ ᴀᴜᴅɪᴏ ᴇxᴛʀᴀᴄᴛɪᴏɴ ꜰᴏʀᴍᴀᴛ</b></blockquote>\n\n"
        f"╭─ 🎬 <b>ꜰɪʟᴇ :</b> <code>{filename}</code>\n"
        f"├─ 📦 <b>sɪᴢᴇ :</b> <code>{humanbytes(file_size)}</code>\n"
        "╰─ <i>Choose your preferred audio output format below:</i>",
        reply_to_message_id=message.id,
        reply_markup=keyboard,
    )


@Client.on_callback_query(filters.regex(r"^extaudio_(\d+)_(copy|mp3|aac|opus)$"))
async def extract_audio_format_select(bot: Client, query: CallbackQuery):
    user_id = int(query.from_user.id)
    msg_id = int(query.matches[0].group(1))
    codec = query.matches[0].group(2)

    try:
        file_msg = await bot.get_messages(query.message.chat.id, msg_id)
    except Exception:
        return await query.message.edit("<blockquote>❌ <b>ᴏʀɪɢɪɴᴀʟ ᴍᴇssᴀɢᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ.</b></blockquote>")

    if not file_msg or not getattr(file_msg, "media", None):
        return await query.message.edit("<blockquote>❌ <b>ᴏʀɪɢɪɴᴀʟ ᴍᴇᴅɪᴀ ɴᴏᴛ ꜰᴏᴜɴᴅ.</b></blockquote>")

    media = getattr(file_msg, file_msg.media.value)
    orig_name = getattr(media, "file_name", None) or "video.mkv"
    base_name = os.path.splitext(orig_name)[0]

    ext_map = {"copy": "mka", "mp3": "mp3", "aac": "m4a", "opus": "opus"}
    out_ext = ext_map.get(codec, "mka")
    default_name = f"{base_name}.{out_ext}"

    user_data = await Mythicbotz.get_user_data(user_id) or {}
    prefix = user_data.get("prefix")
    suffix = user_data.get("suffix")

    try:
        final_default_name = add_prefix_suffix(default_name, prefix, suffix)
    except Exception:
        final_default_name = default_name

    prompt_text = (
        "<blockquote>🎵 <b>ᴇɴᴛᴇʀ ᴀᴜᴅɪᴏ ꜰɪʟᴇ ɴᴀᴍᴇ (ᴏᴘᴛɪᴏɴᴀʟ)</b></blockquote>\n\n"
        f"╭─ 📄 <b>ᴅᴇꜰᴀᴜʟᴛ ɴᴀᴍᴇ :</b> <code>{final_default_name}</code>\n"
        "╰─ <i>Reply to this message with your new audio filename, or click <b>Skip</b> to use the default name.</i>"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⏩ Skip (Use Default Name)", callback_data=f"extaudiorun_{msg_id}_{codec}_default"),
            ],
            [
                InlineKeyboardButton("✖️ Cancel", callback_data=f"cancel_extaudio_{user_id}"),
            ],
        ]
    )

    prompt_msg = await query.message.edit(prompt_text, reply_markup=keyboard)

    ACTIVE_EXTRACT_AUDIO_TASKS[user_id] = {
        "msg_id": msg_id,
        "codec": codec,
        "default_name": final_default_name,
        "prompt_id": prompt_msg.id,
        "timestamp": time.time(),
    }


@Client.on_callback_query(filters.regex(r"^extaudiorun_(\d+)_(copy|mp3|aac|opus)_default$"))
async def extract_audio_skip_cb(bot: Client, query: CallbackQuery):
    user_id = int(query.from_user.id)
    msg_id = int(query.matches[0].group(1))
    codec = query.matches[0].group(2)

    task = ACTIVE_EXTRACT_AUDIO_TASKS.pop(user_id, None)
    default_name = task.get("default_name") if task else None

    await run_audio_extraction_task(
        bot=bot,
        status_msg=query.message,
        user_id=user_id,
        user_name=query.from_user.first_name,
        msg_id=msg_id,
        codec=codec,
        custom_filename=default_name,
    )


@Client.on_message(filters.private & filters.reply & filters.text)
async def handle_audio_name_reply(bot: Client, message: Message):
    user_id = int(message.from_user.id)
    task = ACTIVE_EXTRACT_AUDIO_TASKS.get(user_id)

    if not task:
        return

    reply_msg = message.reply_to_message
    if not reply_msg or reply_msg.id != task.get("prompt_id"):
        return

    ACTIVE_EXTRACT_AUDIO_TASKS.pop(user_id, None)

    codec = task["codec"]
    msg_id = task["msg_id"]
    new_name = (message.text or "").strip()

    if not new_name:
        new_name = task["default_name"]
    else:
        new_name = re.sub(r'[<>:"/\\|?*]', "", new_name)
        ext_map = {"copy": "mka", "mp3": "mp3", "aac": "m4a", "opus": "opus"}
        req_ext = ext_map.get(codec, "mka")
        if "." not in new_name:
            new_name = f"{new_name}.{req_ext}"

        user_data = await Mythicbotz.get_user_data(user_id) or {}
        prefix = user_data.get("prefix")
        suffix = user_data.get("suffix")
        try:
            new_name = add_prefix_suffix(new_name, prefix, suffix)
        except Exception:
            pass

    try:
        await message.delete()
    except Exception:
        pass

    try:
        await reply_msg.delete()
    except Exception:
        pass

    status_msg = await message.reply_text("<blockquote>⚡ <b>ɪɴɪᴛɪᴀʟɪᴢɪɴɢ ᴀᴜᴅɪᴏ ᴇxᴛʀᴀᴄᴛɪᴏɴ...</b></blockquote>")

    await run_audio_extraction_task(
        bot=bot,
        status_msg=status_msg,
        user_id=user_id,
        user_name=message.from_user.first_name,
        msg_id=msg_id,
        codec=codec,
        custom_filename=new_name,
    )


@Client.on_callback_query(filters.regex(r"^cancel_extaudio_(\d+)$"))
async def cancel_extaudio_callback(bot: Client, query: CallbackQuery):
    target_user_id = int(query.matches[0].group(1))
    if query.from_user.id != target_user_id:
        return await query.answer("⚠️ This is not your task!", show_alert=True)

    ACTIVE_EXTRACT_AUDIO_TASKS.pop(target_user_id, None)

    try:
        await query.message.edit("<blockquote>❌ <b>ᴀᴜᴅɪᴏ ᴇxᴛʀᴀᴄᴛɪᴏɴ ᴛᴀsᴋ ᴄᴀɴᴄᴇʟʟᴇᴅ.</b></blockquote>")
    except Exception:
        pass
    try:
        await query.answer("Audio extraction cancelled.", show_alert=False)
    except Exception:
        pass


async def run_audio_extraction_task(
    bot: Client,
    status_msg: Message,
    user_id: int,
    user_name: str,
    msg_id: int,
    codec: str,
    custom_filename: Optional[str] = None,
):
    try:
        file_msg = await bot.get_messages(status_msg.chat.id, msg_id)
    except Exception:
        return await status_msg.edit("<blockquote>❌ <b>ᴏʀɪɢɪɴᴀʟ ᴍᴇssᴀɢᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ.</b></blockquote>")

    if not file_msg or not getattr(file_msg, "media", None):
        return await status_msg.edit("<blockquote>❌ <b>ᴏʀɪɢɪɴᴀʟ ᴍᴇᴅɪᴀ ɴᴏᴛ ꜰᴏᴜɴᴅ.</b></blockquote>")

    media = getattr(file_msg, file_msg.media.value)
    file_size = getattr(media, "file_size", 0) or 0
    orig_name = getattr(media, "file_name", None) or "video.mkv"
    base_name = os.path.splitext(orig_name)[0]

    ext_map = {"copy": "mka", "mp3": "mp3", "aac": "m4a", "opus": "opus"}
    out_ext = ext_map.get(codec, "mka")

    if custom_filename:
        final_filename = custom_filename
    else:
        user_data = await Mythicbotz.get_user_data(user_id) or {}
        prefix = user_data.get("prefix")
        suffix = user_data.get("suffix")
        out_filename = f"{base_name}.{out_ext}"
        try:
            final_filename = add_prefix_suffix(out_filename, prefix, suffix)
        except Exception:
            final_filename = out_filename

    user_data = await Mythicbotz.get_user_data(user_id) or {}
    c_caption = user_data.get("caption")
    c_thumb = user_data.get("file_id")
    dest_channel = user_data.get("destination_channel")

    work_dir = os.path.join("/tmp", f"extaudio_{user_id}_{int(time.time())}")
    os.makedirs(work_dir, exist_ok=True)

    input_video_path = os.path.join(work_dir, orig_name)
    extracted_audio_path = os.path.join(work_dir, final_filename)

    # Step 1: High-Speed Multi-Socket Download
    dl_header = "<blockquote>📥 <b>ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ᴠɪᴅᴇᴏ...</b> ⚡</blockquote>"
    ms, dl_start = await init_progress_message(status_msg, dl_header, file_size)

    dl_client = getattr(bot, "helper_client", None) or getattr(bot, "premium_client", None) or bot
    try:
        input_video_path = await dl_client.download_media(
            message=file_msg,
            file_name=input_video_path,
            progress=progress_for_pyrogram,
            progress_args=(dl_header, ms, dl_start),
        )
    except StopTransmission:
        clear_transfer_cancellation(user_id, ms.id)
        shutil.rmtree(work_dir, ignore_errors=True)
        return
    except Exception as e:
        clear_transfer_cancellation(user_id, ms.id)
        shutil.rmtree(work_dir, ignore_errors=True)
        return await ms.edit(f"<blockquote>❌ <b>ᴅᴏᴡɴʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ :</b> <code>{e}</code></blockquote>")

    # Step 2: Duration Probe
    duration = 0
    try:
        _, _, p_dur = await probe_video_dimensions_and_duration(input_video_path)
        duration = int(p_dur)
    except Exception:
        pass

    # Step 3: FFmpeg Audio Extraction with duration line in status card
    dur_str = convert(duration) if duration > 0 else "N/A"
    await ms.edit(
        "<blockquote>⚙️ <b>ᴇxᴛʀᴀᴄᴛɪɴɢ ᴀᴜᴅɪᴏ sᴛʀᴇᴀᴍ...</b> ⚡</blockquote>\n"
        f"╭─ ⏱️ <b>ᴅᴜʀᴀᴛɪᴏɴ :</b> <code>{dur_str}</code>\n"
        f"╰─ <i>Processing {codec.upper()} audio extraction...</i>"
    )

    success = await extract_audio_from_video(input_video_path, extracted_audio_path, codec_option=codec)
    if not success or not os.path.exists(extracted_audio_path):
        shutil.rmtree(work_dir, ignore_errors=True)
        return await ms.edit("<blockquote>❌ <b>ꜰꜰᴍᴘᴇɢ ᴀᴜᴅɪᴏ ᴇxᴛʀᴀᴄᴛɪᴏɴ ꜰᴀɪʟᴇᴅ.</b></blockquote>")

    extracted_size = os.path.getsize(extracted_audio_path)

    # Step 4: Thumbnail & Caption Formatting
    ph_path = None
    if c_thumb:
        try:
            _, _, ph_path = await get_cached_user_thumb(bot, c_thumb, user_id)
        except Exception:
            ph_path = None

    if c_caption:
        try:
            caption = c_caption.format(
                filename=f"<b>{final_filename}</b>",
                filesize=humanbytes(extracted_size),
                duration=convert(duration),
            )
        except Exception:
            caption = f"<b>{final_filename}</b>"
    else:
        caption = f"🎵 <b>{final_filename}</b>\n📦 <b>sɪᴢᴇ :</b> <code>{humanbytes(extracted_size)}</code>"

    # Step 5: Multi-Socket Upload Audio
    ul_header = "<blockquote>💠 <b>ᴜᴘʟᴏᴀᴅɪɴɢ ᴇxᴛʀᴀᴄᴛᴇᴅ ᴀᴜᴅɪᴏ...</b> ⚡</blockquote>"
    ms, ul_start = await init_progress_message(ms, ul_header, extracted_size)

    try:
        sent_message = await bot.send_audio(
            chat_id=user_id,
            audio=extracted_audio_path,
            file_name=final_filename,
            caption=caption,
            duration=duration,
            thumb=ph_path,
            progress=progress_for_pyrogram,
            progress_args=(ul_header, ms, ul_start),
        )

        if Config.BIN_CHANNEL:
            try:
                bin_caption = (
                    f"<blockquote>🎵 <b>{final_filename}</b></blockquote>\n"
                    f"╭─ 👤 <b>ᴜsᴇʀ :</b> {user_name} (<code>{user_id}</code>)\n"
                    f"├─ 📦 <b>sɪᴢᴇ :</b> <code>{humanbytes(extracted_size)}</code>\n"
                    f"╰─ ⏱️ <b>ᴅᴜʀᴀᴛɪᴏɴ :</b> <code>{convert(duration)}</code>"
                )
                await bot.copy_message(
                    chat_id=Config.BIN_CHANNEL,
                    from_chat_id=user_id,
                    message_id=sent_message.id,
                    caption=bin_caption,
                )
            except Exception as e:
                logger.error("Failed sending audio to BIN_CHANNEL: %s", e)

        if dest_channel:
            try:
                await bot.copy_message(
                    chat_id=int(dest_channel),
                    from_chat_id=user_id,
                    message_id=sent_message.id,
                )
            except Exception as e:
                logger.error("Failed sending audio to dest_channel: %s", e)

        await Mythicbotz.increase_rename_count(user_id)

        deletion_msg = await sent_message.reply(
            "<blockquote>🗑️ <b>ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ɴᴏᴛɪᴄᴇ</b></blockquote>\n"
            "╰─ <b>ᴛʜɪs ꜰɪʟᴇ ᴡɪʟʟ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ɪɴ <code>30 ᴍɪɴᴜᴛᴇs</code>. ꜰᴏʀᴡᴀʀᴅ / sᴀᴠᴇ ɪᴛ ɴᴏᴡ!</b>"
        )
        asyncio.create_task(_delayed_delete(sent_message, deletion_msg, delay=1800.0))

    except StopTransmission:
        clear_transfer_cancellation(user_id, ms.id)
        return
    except FloodWait as fw:
        await asyncio.sleep(fw.value)
        return
    except Exception as e:
        logger.error("Audio upload failed: %s", e)
        clear_transfer_cancellation(user_id, ms.id)
        return await ms.edit(f"<blockquote>❌ <b>ᴜᴘʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ :</b> <code>{e}</code></blockquote>")
    finally:
        ram_workspace.cleanup_files(ph_path)
        shutil.rmtree(work_dir, ignore_errors=True)
        try:
            await ms.delete()
        except Exception:
            pass
