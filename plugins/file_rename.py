from pyrogram import Client, filters, StopTransmission
from pyrogram.enums import MessageMediaType
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
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
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("✖️ Cancel", callback_data="cancel_rename_prompt")]]
            ),
        )
    except FloodWait as e:
        await sleep(e.value)
        prompt_msg = await message.reply_text(
            text=prompt_text,
            reply_to_message_id=message.id,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("✖️ Cancel", callback_data="cancel_rename_prompt")]]
            ),
        )
    except Exception as e:
        logger.error(f"Error in rename_start: {e}")
        return await message.reply_text(
            "<blockquote>⚠️ <b>ᴇʀʀᴏʀ</b></blockquote>\n"
            "╰─ <b>ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ᴏʀ ᴄᴏɴᴛᴀᴄᴛ @CosmicBotz.</b>"
        )

    # Schedule non-blocking auto-delete after 10 minutes
    asyncio.create_task(_delayed_delete(prompt_msg, delay=600.0))


@Client.on_callback_query(filters.regex(r"^cancel_rename_prompt$"))
async def cancel_rename_prompt_cb(client, query):
    try:
        await query.message.delete()
    except Exception:
        pass
    try:
        await query.answer("✖️ Rename prompt cancelled.", show_alert=False)
    except Exception:
        pass


@Client.on_message(filters.private & filters.reply)
async def refunc(client, message):
    reply_message = message.reply_to_message
    if not (reply_message and reply_message.from_user and reply_message.from_user.is_self):
        return
    reply_txt = (reply_message.text or "") + (reply_message.caption or "")
    if "ᴇɴᴛᴇʀ ɴᴇᴡ ꜰɪʟᴇ ɴᴀᴍᴇ" not in reply_txt and "ENTER NEW FILE NAME" not in reply_txt:
        if not (reply_message.reply_markup and isinstance(reply_message.reply_markup, ForceReply)):
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
    # Uses an isolated per-job directory so the file's basename on disk is strictly `new_filename`
    file_path = ram_workspace.resolve_transfer_path(new_filename, file_size)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    path = None
    metadata_path = None
    ph_path = None
    cover_path = None

    # Download the file using Multi-Session Connection Pool (24 parallel TCP sockets)
    # Uses helper/premium user session if available for higher MTProto bandwidth priority
    dl_client = getattr(bot, "helper_client", None) or getattr(bot, "premium_client", None) or bot
    dl_header = "<blockquote>🚀 <b>ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ᴍᴇᴅɪᴀ...</b> ⚡</blockquote>"
    ms, dl_start = await init_progress_message(update.message, dl_header, file_size)
    try:
        path = await dl_client.download_media(
            message=file,
            file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=(dl_header, ms, dl_start),
        )
    except StopTransmission:
        ram_workspace.cleanup_files(file_path)
        clear_transfer_cancellation(user_id, ms.id)
        return
    except FloodWait as e:
        await sleep(e.value)
        try:
            path = await dl_client.download_media(
                message=file,
                file_name=file_path,
                progress=progress_for_pyrogram,
                progress_args=(dl_header, ms, time.time()),
            )
        except StopTransmission:
            ram_workspace.cleanup_files(file_path)
            clear_transfer_cancellation(user_id, ms.id)
            return
    except Exception as e:
        logger.warning(f"Download initial attempt encountered error: {e}. Retrying with fresh session...")
        try:
            await sleep(2.0)
            path = await dl_client.download_media(
                message=file,
                file_name=file_path,
                progress=progress_for_pyrogram,
                progress_args=(dl_header, ms, time.time()),
            )
        except StopTransmission:
            ram_workspace.cleanup_files(file_path)
            clear_transfer_cancellation(user_id, ms.id)
            return
        except Exception as e2:
            logger.error(f"Download retry failed: {e2}")
            ram_workspace.cleanup_files(file_path)
            clear_transfer_cancellation(user_id, ms.id)
            return await ms.edit(f"<blockquote>❌ <b>ᴅᴏᴡɴʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ</b></blockquote>\n╰─ <code>{e2}</code>")

    if not path or not os.path.exists(path):
        ram_workspace.cleanup_files(file_path)
        clear_transfer_cancellation(user_id, ms.id)
        return

    # Extract duration, width, and height upfront to display duration during processing
    raw_dur = getattr(media, "duration", 0)
    duration = int(raw_dur) if isinstance(raw_dur, (int, float)) and raw_dur > 0 else 0
    raw_w = getattr(media, "width", 0)
    width = int(raw_w) if isinstance(raw_w, (int, float)) and raw_w > 0 else 0
    raw_h = getattr(media, "height", 0)
    height = int(raw_h) if isinstance(raw_h, (int, float)) and raw_h > 0 else 0

    if not duration and path and os.path.exists(path):
        try:
            _, _, p_dur = await probe_video_dimensions_and_duration(path)
            if p_dur > 0:
                duration = int(p_dur)
        except Exception:
            pass

    # Display clean processing status card between Download and Upload
    try:
        await ms.edit(
            "<blockquote>⚙️ <b>ᴘʀᴏᴄᴇssɪɴɢ ᴍᴇᴅɪᴀ...</b> ⚡</blockquote>\n"
            "╰─ <i>Applying metadata & preparing upload...</i>"
        )
    except Exception:
        pass

    # Handle metadata (only when enabled) — output inside isolated `meta_out/` sub-folder
    # so the file's basename remains strictly `new_filename`
    if _bool_metadata:
        metadata_dir = os.path.join(os.path.dirname(file_path), "meta_out")
        os.makedirs(metadata_dir, exist_ok=True)
        metadata_path = os.path.join(metadata_dir, new_filename)
        try:
            res_meta = await add_metadata(path, metadata_path, user_metadata_code, ms)
            if not res_meta:
                metadata_path = None
        except Exception as e:
            logger.error(f"Metadata addition failed: {e}")
            metadata_path = None

    # Extract duration, width, and height (works regardless of whether user metadata is ON or OFF)
    raw_dur = getattr(media, "duration", 0)
    duration = int(raw_dur) if isinstance(raw_dur, (int, float)) and raw_dur > 0 else 0
    raw_w = getattr(media, "width", 0)
    width = int(raw_w) if isinstance(raw_w, (int, float)) and raw_w > 0 else 0
    raw_h = getattr(media, "height", 0)
    height = int(raw_h) if isinstance(raw_h, (int, float)) and raw_h > 0 else 0

    probe_target = metadata_path if (_bool_metadata and metadata_path and os.path.exists(metadata_path)) else path
    if (not width or not height or not duration) and is_video_file(new_filename, file.media, type_):
        try:
            p_w, p_h, p_dur = await probe_video_dimensions_and_duration(probe_target)
            if not width and p_w > 0:
                width = int(p_w)
            if not height and p_h > 0:
                height = int(p_h)
            if not duration and p_dur > 0:
                duration = int(p_dur)
        except Exception as e:
            logger.debug(f"ffprobe/ffmpeg dimension probe skipped: {e}")

    if not duration or not width or not height:
        try:
            parser = createParser(probe_target)
            if parser:
                with parser:
                    meta_info = extractMetadata(parser)
                    if meta_info:
                        if not duration and meta_info.has("duration"):
                            duration = meta_info.get("duration").seconds
                        if not width and meta_info.has("width"):
                            width = int(meta_info.get("width") or 0)
                        if not height and meta_info.has("height"):
                            height = int(meta_info.get("height") or 0)
        except Exception as e:
            logger.debug(f"Media dimension/duration extraction skipped: {e}")

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
        caption = f"<b>{new_filename}</b>"

    # Thumbnail & HD video_cover handling (NEVER uses source media.thumbs):
    # 1. If user saved a custom thumbnail (`c_thumb`), fetch from RAM cache or download once,
    #    and pass `c_thumb` (or `ph_path`) as `video_cover` for HD video preview.
    #    Note: Custom thumbnail dimensions are NEVER used for video stream width/height.
    # 2. Otherwise, automatically extract a non-blank frame at ~30s via FFmpeg (`extract_auto_thumbnail`),
    #    preserving both the 320p `thumb` (`ph_path`) and the full-resolution HD `cover_path`,
    #    and using the extracted video frame's native resolution if `width`/`height` are still unknown.
    video_cover = None
    try:
        if c_thumb:
            _, _, ph_path = await get_cached_user_thumb(bot, c_thumb, user_id)
            video_cover = c_thumb or ph_path
        else:
            frame_w, frame_h, ph_path = await extract_auto_thumbnail(
                bot=bot,
                video_path=probe_target,
                media=media,
                duration=duration,
                user_id=user_id,
                filename=new_filename,
                media_type=file.media,
                upload_type=type_,
            )
            cover_path = get_hd_cover_path(ph_path)
            video_cover = cover_path or ph_path
            if not width and frame_w:
                width = int(frame_w)
            if not height and frame_h:
                height = int(frame_h)
    except Exception as e:
        logger.warning(f"Thumbnail processing failed: {e}")
        ph_path = None
        video_cover = None

    # Guarantee non-zero landscape dimensions (1280x720 fallback) when uploading as video
    # so Telegram's video player always renders the rotate / fullscreen orientation button.
    if type_ == "video":
        if width <= 0 or height <= 0:
            width = 1280
            height = 720

    # Upload the file using Multi-Session Connection Pool (16 parallel TCP sockets)
    ul_header = "<blockquote>💠 <b>ᴜᴘʟᴏᴀᴅɪɴɢ ᴍᴇᴅɪᴀ...</b> ⚡</blockquote>"
    try:
        upload_path = metadata_path if (_bool_metadata and metadata_path) else path

        if not upload_path or not os.path.exists(upload_path):
            raise FileNotFoundError(f"File not found: {upload_path}")

        upload_size = os.path.getsize(upload_path) if os.path.exists(upload_path) else file_size
        ms, ul_start = await init_progress_message(ms, ul_header, upload_size)

        if type_ == "document":
            sent_message = await bot.send_document(
                chat_id=user_id,
                document=upload_path,
                file_name=new_filename,
                thumb=ph_path,
                caption=caption,
                progress=progress_for_pyrogram,
                progress_args=(ul_header, ms, ul_start),
            )
        elif type_ == "video":
            sent_message = await bot.send_video(
                chat_id=user_id,
                video=upload_path,
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
        elif type_ == "audio":
            sent_message = await bot.send_audio(
                chat_id=user_id,
                audio=upload_path,
                file_name=new_filename,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=(ul_header, ms, ul_start),
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

    except StopTransmission:
        clear_transfer_cancellation(user_id, ms.id)
        return
    except FloodWait as e:
        await sleep(e.value)
        await ms.edit(f"<blockquote>⏳ <b>ꜰʟᴏᴏᴅᴡᴀɪᴛ :</b> <code>ʀᴇᴛʀʏɪɴɢ ɪɴ {e.value}s...</code></blockquote>")
        return await doc(bot, update)
    except Exception as e:
        clear_transfer_cancellation(user_id, ms.id)
        logger.error(f"Upload error: {e}")
        return await ms.edit(f"<blockquote>❌ <b>ᴜᴘʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ</b></blockquote>\n╰─ <code>{e}</code>")

    finally:
        # Remove temporary files and immediately release freed heap pages back to OS
        ram_workspace.cleanup_files(ph_path, cover_path, path, metadata_path)

    try:
        await ms.delete()
    except Exception:
        pass

    # Schedule non-blocking auto-delete after 30 minutes
    asyncio.create_task(_delayed_delete(sent_message, deletion_msg, delay=1800.0))