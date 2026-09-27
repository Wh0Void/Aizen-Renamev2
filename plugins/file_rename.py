from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from helper.ffmpeg import (
    extract_auto_thumbnail,
    get_cached_user_thumb,
    add_metadata,
)
from helper.utils import progress_for_pyrogram, convert, humanbytes, add_prefix_suffix
from helper.database import Mythicbotz
from bot.core.cache import ram_workspace
from config import Config
from asyncio import sleep
import os
import time
import re
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _delayed_delete(*messages, delay: float = 1800.0) -> None:
    """Background task to auto-delete messages after `delay` seconds without holding a handler worker."""
    await asyncio.sleep(delay)
    for msg in messages:
        if msg is not None:
            try:
                await msg.delete()
            except Exception as e:
                logger.debug(f"Delayed message delete skipped: {e}")


@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def rename_start(client, message):
    file = getattr(message, message.media.value)
    filename = file.file_name or "Unknown_File"
    filesize = humanbytes(getattr(file, "file_size", 0) or 0)

    # Fast RAM-cached ban check
    if await Mythicbotz.is_banned(int(message.from_user.id)):
        return await message.reply(
            "<blockquote>🚫 <b>ᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ</b></blockquote>\n"
            "╰─ <b>ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ ꜰʀᴏᴍ ᴜsɪɴɢ ᴛʜɪs ʙᴏᴛ. ᴄᴏɴᴛᴀᴄᴛ @CosmicBotz.</b>"
        )

    # Check file size limit (2 GB)
    if file.file_size and file.file_size > 2000 * 1024 * 1024:
        return await message.reply_text(
            "<blockquote>⚠️ <b>ꜰɪʟᴇ sɪᴢᴇ ʟɪᴍɪᴛ ᴇxᴄᴇᴇᴅᴇᴅ</b></blockquote>\n"
            "╰─ <b>ᴛʜɪs ʙᴏᴛ sᴜᴘᴘᴏʀᴛs ꜰɪʟᴇs ᴜᴘ ᴛᴏ <code>2.0 GB</code>.</b>"
        )

    prompt_text = (
        "<blockquote>✏️ <b>ᴇɴᴛᴇʀ ɴᴇᴡ ꜰɪʟᴇ ɴᴀᴍᴇ</b></blockquote>\n\n"
        f"╭─ 📄 <b>ᴏʟᴅ ɴᴀᴍᴇ :</b> <code>{filename}</code>\n"
        f"╰─ 📦 <b>sɪᴢᴇ :</b> <code>{filesize}</code>"
    )

    try:
        prompt_msg = await message.reply_text(
            text=prompt_text,
            reply_to_message_id=message.id,
            reply_markup=ForceReply(True),
        )
    except FloodWait as e:
        await sleep(e.value)
        prompt_msg = await message.reply_text(
            text=prompt_text,
            reply_to_message_id=message.id,
            reply_markup=ForceReply(True),
        )
    except Exception as e:
        logger.error(f"Error in rename_start: {e}")
        return await message.reply_text(
            "<blockquote>⚠️ <b>ᴇʀʀᴏʀ</b></blockquote>\n"
            "╰─ <b>ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ᴏʀ ᴄᴏɴᴛᴀᴄᴛ @CosmicBotz.</b>"
        )

    # Schedule non-blocking auto-delete after 10 minutes
    asyncio.create_task(_delayed_delete(prompt_msg, delay=600.0))


@Client.on_message(filters.private & filters.reply)
async def refunc(client, message):
    reply_message = message.reply_to_message
    if not (reply_message and reply_message.reply_markup and isinstance(reply_message.reply_markup, ForceReply)):
        return

    new_name = (message.text or "").strip()
    if not new_name:
        return await message.reply_text("<blockquote>⚠️ <b>ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ꜰɪʟᴇ ɴᴀᴍᴇ.</b></blockquote>")

    # Sanitize new_name to prevent path traversal or invalid characters
    new_name = re.sub(r'[<>:"/\\|?*]', "", new_name)

    try:
        await message.delete()
    except Exception:
        pass

    # Use already-populated reply_to_message when available to save an extra RPC round-trip
    file = getattr(reply_message, "reply_to_message", None)
    if file is None or getattr(file, "media", None) is None:
        msg = await client.get_messages(message.chat.id, reply_message.id)
        file = msg.reply_to_message

    if file is None or getattr(file, "media", None) is None:
        return await message.reply_text("<blockquote>⚠️ <b>ᴏʀɪɢɪɴᴀʟ ᴍᴇᴅɪᴀ ᴍᴇssᴀɢᴇ ᴄᴏᴜʟᴅ ɴᴏᴛ ʙᴇ ꜰᴏᴜɴᴅ.</b></blockquote>")

    media = getattr(file, file.media.value)
    orig_filename = getattr(media, "file_name", None) or "video.mkv"

    # Add file extension if missing
    if "." not in new_name:
        extn = orig_filename.rsplit(".", 1)[-1] if "." in orig_filename else "mkv"
        new_name = f"{new_name}.{extn}"

    try:
        await reply_message.delete()
    except Exception:
        pass

    # Create inline buttons for file type selection
    button = [[InlineKeyboardButton("📁 ᴅᴏᴄᴜᴍᴇɴᴛ", callback_data="upload_document")]]
    if file.media in [MessageMediaType.VIDEO, MessageMediaType.DOCUMENT]:
        button.append([InlineKeyboardButton("🎥 ᴠɪᴅᴇᴏ", callback_data="upload_video")])
    elif file.media == MessageMediaType.AUDIO:
        button.append([InlineKeyboardButton("🎵 ᴀᴜᴅɪᴏ", callback_data="upload_audio")])

    await message.reply(
        text=(
            "<blockquote>📤 <b>sᴇʟᴇᴄᴛ ᴏᴜᴛᴘᴜᴛ ꜰɪʟᴇ ᴛʏᴘᴇ</b></blockquote>\n\n"
            f"╰─ 📄 <b>ꜰɪʟᴇ ɴᴀᴍᴇ</b> :- <code>{new_name}</code>"
        ),
        reply_to_message_id=file.id,
        reply_markup=InlineKeyboardMarkup(button),
    )


@Client.on_callback_query(filters.regex("^upload_"))
async def doc(bot, update):
    user_id = int(update.message.chat.id)
    user_name = update.message.chat.first_name
    type_ = update.data.split("_")[1]

    # Fetch all user settings in a single RAM-cached lookup (0 MongoDB network queries on hit)
    user_data = await Mythicbotz.get_user_data(user_id) or {}
    prefix = user_data.get("prefix")
    suffix = user_data.get("suffix")
    _bool_metadata = bool(user_data.get("metadata", False))
    user_metadata_code = user_data.get("metadata_code") or "By :- @CosmicBotz"
    c_caption = user_data.get("caption")
    c_thumb = user_data.get("file_id")
    dest_channel = user_data.get("destination_channel")

    raw_text = re.sub(r"<[^>]+>", "", (update.message.text or update.message.caption or "")).strip()
    if ":-" in raw_text:
        new_filename = raw_text.split(":-", 1)[1].strip().strip("`").strip()
    elif ":" in raw_text:
        new_filename = raw_text.rsplit(":", 1)[1].strip().strip("`").strip()
    else:
        new_filename = raw_text.strip("`").strip()
        logger.warning(f"Invalid new_name format, using full text: {raw_text}")

    # Add prefix and suffix
    try:
        new_filename = add_prefix_suffix(new_filename, prefix, suffix)
    except Exception as e:
        return await update.message.edit(
            f"<blockquote>⚠️ <b>ᴘʀᴇꜰɪx / sᴜꜰꜰɪx ᴇʀʀᴏʀ</b></blockquote>\n╰─ <code>{e}</code>"
        )

    file = update.message.reply_to_message
    if file is None or getattr(file, "media", None) is None:
        return await update.message.edit("<blockquote>⚠️ <b>ᴄᴏᴜʟᴅ ɴᴏᴛ ꜰɪɴᴅ ᴛʜᴇ ᴏʀɪɢɪɴᴀʟ ᴍᴇᴅɪᴀ ᴍᴇssᴀɢᴇ.</b></blockquote>")

    media = getattr(file, file.media.value)
    file_size = getattr(media, "file_size", 0) or 0

    # Smart RAM-Disk (/dev/shm) routing for small files & disk fallback for large (up to 2GB) files
    file_path = ram_workspace.resolve_transfer_path(f"{user_id}_{new_filename}", file_size)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    path = None
    metadata_path = None
    ph_path = None

    # Download the file using Multi-Session Connection Pool
    dl_header = "<blockquote>🚀 <b>ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ᴍᴇᴅɪᴀ...</b> ⚡</blockquote>"
    ms = await update.message.edit(dl_header)
    try:
        path = await bot.download_media(
            message=file,
            file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=(dl_header, ms, time.time()),
        )
    except FloodWait as e:
        await sleep(e.value)
        path = await bot.download_media(
            message=file,
            file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=(dl_header, ms, time.time()),
        )
    except Exception as e:
        logger.error(f"Download error: {e}")
        ram_workspace.cleanup_files(file_path)
        return await ms.edit(f"<blockquote>❌ <b>ᴅᴏᴡɴʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ</b></blockquote>\n╰─ <code>{e}</code>")

    # Handle metadata (only when enabled)
    if _bool_metadata:
        metadata_dir = ram_workspace.shm_dir if ram_workspace.should_use_ram_disk(file_size) else "Metadata"
        os.makedirs(metadata_dir, exist_ok=True)
        metadata_path = os.path.join(metadata_dir, f"meta_{user_id}_{new_filename}")
        try:
            res_meta = await add_metadata(path, metadata_path, user_metadata_code, ms)
            if not res_meta:
                metadata_path = None
        except Exception as e:
            logger.error(f"Metadata addition failed: {e}")
            metadata_path = None

    # Extract duration (works regardless of whether user metadata is ON or OFF)
    duration = getattr(media, "duration", 0) or 0
    if not duration:
        try:
            parser = createParser(path)
            if parser:
                with parser:
                    meta_info = extractMetadata(parser)
                    if meta_info and meta_info.has("duration"):
                        duration = meta_info.get("duration").seconds
        except Exception as e:
            logger.debug(f"Duration extraction skipped: {e}")

    if c_caption:
        try:
            caption = c_caption.format(
                filename=f"<b>{new_filename}</b>",
                filesize=humanbytes(file_size),
                duration=convert(duration),
            )
        except Exception as e:
            logger.error(f"Caption formatting error: {e}")
            ram_workspace.cleanup_files(path, metadata_path)
            return await ms.edit(f"<blockquote>⚠️ <b>ᴄᴀᴘᴛɪᴏɴ ᴇʀʀᴏʀ</b></blockquote>\n╰─ <code>{e}</code>")
    else:
        caption = (
            f"<blockquote>📄 <b>{new_filename}</b></blockquote>\n"
            f"╭─ 📦 <b>sɪᴢᴇ :</b> <code>{humanbytes(file_size)}</code>\n"
            f"├─ 👤 <b>ᴜsᴇʀ :</b> {user_name} (<code>{user_id}</code>)\n"
            f"╰─ ⚡ <b>ᴘᴏᴡᴇʀᴇᴅ ʙʏ :</b> @CosmicBotz"
        )

    # Thumbnail handling:
    # 1. If user set a custom thumbnail (`c_thumb`), fetch from RAM cache or download once.
    # 2. If user did NOT set a custom thumbnail (even if metadata is OFF and `media.thumbs` is None),
    #    automatically extract a frame from the video file via FFmpeg (with fallback to `media.thumbs`).
    try:
        if c_thumb:
            _, _, ph_path = await get_cached_user_thumb(bot, c_thumb, user_id)
        else:
            _, _, ph_path = await extract_auto_thumbnail(
                bot=bot,
                video_path=path,
                media=media,
                duration=duration,
                user_id=user_id,
                filename=new_filename,
                media_type=file.media,
                upload_type=type_,
            )
    except Exception as e:
        logger.warning(f"Thumbnail processing failed: {e}")
        ph_path = None

    # Upload the file using Multi-Session Connection Pool (6-8 parallel TCP sockets)
    ul_header = "<blockquote>💠 <b>ᴜᴘʟᴏᴀᴅɪɴɢ ᴍᴇᴅɪᴀ...</b> ⚡</blockquote>"
    try:
        await ms.edit(ul_header)
        upload_path = metadata_path if (_bool_metadata and metadata_path) else path

        if not upload_path or not os.path.exists(upload_path):
            raise FileNotFoundError(f"File not found: {upload_path}")

        if type_ == "document":
            sent_message = await bot.send_document(
                chat_id=user_id,
                document=upload_path,
                thumb=ph_path,
                caption=caption,
                progress=progress_for_pyrogram,
                progress_args=(ul_header, ms, time.time()),
            )
        elif type_ == "video":
            sent_message = await bot.send_video(
                chat_id=user_id,
                video=upload_path,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=(ul_header, ms, time.time()),
            )
        elif type_ == "audio":
            sent_message = await bot.send_audio(
                chat_id=user_id,
                audio=upload_path,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=(ul_header, ms, time.time()),
            )
        else:
            raise ValueError(f"Unsupported upload type: {type_}")

        # Send to BIN_CHANNEL
        if Config.BIN_CHANNEL:
            try:
                bin_caption = (
                    f"<blockquote>📁 <b>{new_filename}</b></blockquote>\n"
                    f"╭─ 👤 <b>ᴜsᴇʀ :</b> {user_name} (<code>{user_id}</code>)\n"
                    f"├─ 📦 <b>sɪᴢᴇ :</b> <code>{humanbytes(file_size)}</code>\n"
                    f"╰─ ⏱️ <b>ᴅᴜʀᴀᴛɪᴏɴ :</b> <code>{convert(duration)}</code>"
                )
                await bot.copy_message(
                    chat_id=Config.BIN_CHANNEL,
                    from_chat_id=user_id,
                    message_id=sent_message.id,
                    caption=bin_caption,
                )
            except Exception as e:
                logger.error(f"Failed to send to BIN_CHANNEL: {e}")

        # Send to destination channel (already retrieved from RAM cache)
        if dest_channel:
            try:
                await bot.copy_message(
                    chat_id=int(dest_channel),
                    from_chat_id=user_id,
                    message_id=sent_message.id,
                )
            except Exception as e:
                logger.error(f"Failed to send to destination channel: {e}")

        # Increment rename count (updates RAM cache & MongoDB)
        await Mythicbotz.increase_rename_count(user_id)

        # Notify about auto-deletion
        deletion_msg = await sent_message.reply(
            "<blockquote>🗑️ <b>ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ɴᴏᴛɪᴄᴇ</b></blockquote>\n"
            "╰─ <b>ᴛʜɪs ꜰɪʟᴇ ᴡɪʟʟ ᴀᴜᴛᴏ-ᴅᴇʟᴇᴛᴇ ɪɴ <code>30 ᴍɪɴᴜᴛᴇs</code>. ꜰᴏʀᴡᴀʀᴅ / sᴀᴠᴇ ɪᴛ ɴᴏᴡ!</b>"
        )

    except FloodWait as e:
        await sleep(e.value)
        await ms.edit(f"<blockquote>⏳ <b>ꜰʟᴏᴏᴅᴡᴀɪᴛ :</b> <code>ʀᴇᴛʀʏɪɴɢ ɪɴ {e.value}s...</code></blockquote>")
        return await doc(bot, update)
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return await ms.edit(f"<blockquote>❌ <b>ᴜᴘʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ</b></blockquote>\n╰─ <code>{e}</code>")

    finally:
        # Remove temporary files and immediately release freed heap pages back to OS
        ram_workspace.cleanup_files(ph_path, path, metadata_path)

    try:
        await ms.delete()
    except Exception:
        pass

    # Schedule non-blocking auto-delete after 30 minutes
    asyncio.create_task(_delayed_delete(sent_message, deletion_msg, delay=1800.0))