from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from helper.ffmpeg import fix_thumb, take_screen_shot, add_metadata
from helper.utils import progress_for_pyrogram, convert, humanbytes, add_prefix_suffix
from helper.database import Mythicbotz
from config import Config
from asyncio import sleep
import os, time, re, random, asyncio
import logging

# Set up logging for better debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def rename_start(client, message):
    file = getattr(message, message.media.value)
    filename = file.file_name

    # Check if user is banned
    if await Mythicbotz.is_banned(int(message.from_user.id)):
        return await message.reply("You are banned from using this bot. Contact @PS_TalkBot to resolve the issue!")

    # Check file size limit
    if file.file_size > 2000 * 1024 * 1024:
        return await message.reply_text("Sorry, this bot doesn't support files larger than 2GB.")

    try:
        await message.reply_text(
            text=f"**Please Enter New Filename...**\n\n**Old File Name**: `{filename}`",
            reply_to_message_id=message.id,
            reply_markup=ForceReply(True)
        )
    except FloodWait as e:
        await sleep(e.value)
        await message.reply_text(
            text=f"**Please Enter New Filename**\n\n**Old File Name**: `{filename}`",
            reply_to_message_id=message.id,
            reply_markup=ForceReply(True)
        )
    except Exception as e:
        logger.error(f"Error in rename_start: {e}")
        await message.reply_text("An error occurred. Please try again or contact @PS_TalkBot.")

    # Auto-delete the prompt after 10 minutes
    await asyncio.sleep(600)
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Failed to delete message: {e}")

@Client.on_message(filters.private & filters.reply)
async def refunc(client, message):
    reply_message = message.reply_to_message
    if not (reply_message.reply_markup and isinstance(reply_message.reply_markup, ForceReply)):
        return

    new_name = message.text.strip()
    if not new_name:
        return await message.reply_text("Please provide a valid filename.")

    # Sanitize new_name to prevent path traversal or invalid characters
    new_name = re.sub(r'[<>:"/\\|?*]', '', new_name)

    await message.delete()
    msg = await client.get_messages(message.chat.id, reply_message.id)
    file = msg.reply_to_message
    media = getattr(file, file.media.value)

    # Add file extension if missing
    if not "." in new_name:
        extn = media.file_name.rsplit('.', 1)[-1] if '.' in media.file_name else "mkv"
        new_name = f"{new_name}.{extn}"

    await reply_message.delete()

    # Create inline buttons for file type selection
    button = [[InlineKeyboardButton("📁 Document", callback_data="upload_document")]]
    if file.media in [MessageMediaType.VIDEO, MessageMediaType.DOCUMENT]:
        button.append([InlineKeyboardButton("🎥 Video", callback_data="upload_video")])
    elif file.media == MessageMediaType.AUDIO:
        button.append([InlineKeyboardButton("🎵 Audio", callback_data="upload_audio")])

    await message.reply(
        text=f"**Select The Output File Type**\n\n**File Name**:- `{new_name}`",
        reply_to_message_id=file.id,
        reply_markup=InlineKeyboardMarkup(button)
    )

@Client.on_callback_query(filters.regex("upload"))
async def doc(bot, update):
    if not os.path.exists("Metadata"):
        os.makedirs("Metadata")

    new_name = update.message.text.strip()
    try:
        new_filename = new_name.split(":-")[1].strip()
    except IndexError:
        new_filename = new_name  # Fallback to full text if ":-" not found
        logger.warning(f"Invalid new_name format, using full text: {new_name}")

    # Add prefix and suffix
    try:
        prefix = await Mythicbotz.get_prefix(int(update.message.chat.id))
        suffix = await Mythicbotz.get_suffix(int(update.message.chat.id))
        new_filename = add_prefix_suffix(new_filename, prefix, suffix)
    except Exception as e:
        return await update.message.edit(f"Error setting prefix/suffix: {e}\nContact @PS_TalkBot.")

    file_path = f"downloads/{int(update.from_user.id)}/{new_filename}"
    file = update.message.reply_to_message
    media = getattr(file, file.media.value)

    # Create downloads directory if it doesn't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Download the file
    ms = await update.message.edit("🚀 Downloading... ⚡")
    try:
        path = await bot.download_media(
            message=file,
            file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=("🚀 Downloading... ⚡", ms, time.time())
        )
    except FloodWait as e:
        await sleep(e.value)
        path = await bot.download_media(
            message=file,
            file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=("🚀 Downloading... ⚡", ms, time.time())
        )
    except Exception as e:
        logger.error(f"Download error: {e}")
        return await ms.edit(f"Download failed: {e}")

    # Handle metadata
    _bool_metadata = await Mythicbotz.get_metadata(int(update.message.chat.id))
    metadata_path = None
    if _bool_metadata:
        metadata = await Mythicbotz.get_metadata_code(int(update.message.chat.id))
        metadata_path = f"Metadata/{new_filename}"
        try:
            await add_metadata(path, metadata_path, metadata, ms)
        except Exception as e:
            logger.error(f"Metadata addition failed: {e}")
            await ms.edit(f"Metadata addition failed: {e}")
            metadata_path = None  # Fallback to original file_path

    # Extract duration
    duration = 0
    try:
        parser = createParser(path)
        if parser:
            metadata = extractMetadata(parser)
            if metadata and metadata.has("duration"):
                duration = metadata.get('duration').seconds
            parser.close()
    except Exception as e:
        logger.warning(f"Metadata extraction failed: {e}")

    # Handle thumbnail
    ph_path = None
    user_id = int(update.message.chat.id)
    user_name = update.message.chat.first_name
    c_caption = await Mythicbotz.get_caption(int(update.message.chat.id))
    c_thumb = await Mythicbotz.get_thumbnail(int(update.message.chat.id))

    if c_caption:
        try:
            caption = c_caption.format(
                filename=f"<b>{new_filename}</b>",
                filesize=humanbytes(media.file_size),
                duration=convert(duration)
            )
        except Exception as e:
            logger.error(f"Caption formatting error: {e}")
            return await ms.edit(f"Caption error: {e}")
    else:
        caption = f"**{new_filename}**\n\n**User:** {user_name}\n**User ID:** {user_id}"

    if media.thumbs or c_thumb:
        try:
            if c_thumb:
                ph_path = await bot.download_media(c_thumb)
                width, height, ph_path = await fix_thumb(ph_path)
            else:
                ph_path_ = await take_screen_shot(file_path, os.path.dirname(os.path.abspath(file_path)), random.randint(0, max(0, duration - 1)))
                width, height, ph_path = await fix_thumb(ph_path_)
        except Exception as e:
            logger.warning(f"Thumbnail processing failed: {e}")
            ph_path = None

    # Upload the file
    try:
        await ms.edit("💠 Uploading... ⚡")
        type_ = update.data.split("_")[1]
        upload_path = metadata_path if _bool_metadata and metadata_path else path

        if not os.path.exists(upload_path):
            raise FileNotFoundError(f"File not found: {upload_path}")

        if type_ == "document":
            sent_message = await bot.send_document(
                chat_id=user_id,
                document=upload_path,
                thumb=ph_path,
                caption=caption,
                progress=progress_for_pyrogram,
                progress_args=("💠 Uploading... ⚡", ms, time.time())
            )
        elif type_ == "video":
            sent_message = await bot.send_video(
                chat_id=user_id,
                video=upload_path,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("💠 Uploading... ⚡", ms, time.time())
            )
        elif type_ == "audio":
            sent_message = await bot.send_audio(
                chat_id=user_id,
                audio=upload_path,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("💠 Uploading... ⚡", ms, time.time())
            )

        # Send to BIN_CHANNEL
        if Config.BIN_CHANNEL:
            try:
                bin_caption = f"📁 {new_filename}\nUser: {user_name} — {user_id}\nFile Size: {humanbytes(media.file_size)}\nDuration: {convert(duration)}"
                await bot.copy_message(
                    chat_id=Config.BIN_CHANNEL,
                    from_chat_id=user_id,
                    message_id=sent_message.id,
                    caption=bin_caption
                )
            except Exception as e:
                logger.error(f"Failed to send to BIN_CHANNEL: {e}")

        # Send to destination channel
        dest_channel = await Mythicbotz.get_destination_channel(user_id)
        if dest_channel:
            try:
                await bot.copy_message(
                    chat_id=dest_channel,
                    from_chat_id=user_id,
                    message_id=sent_message.id
                )
            except Exception as e:
                logger.error(f"Failed to send to destination channel: {e}")

        # Increment rename count
        await Mythicbotz.increase_rename_count(user_id)

        # Notify about auto-deletion
        deletion_msg = await sent_message.reply("🗑 This file will auto-delete in 30 minutes. Save it now!")

    except FloodWait as e:
        await sleep(e.value)
        await ms.edit(f"FloodWait: Retrying after {e.value} seconds")
        return await doc(bot, update)  # Retry the upload
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return await ms.edit(f"Upload failed: {e}")

    finally:
        # Clean up files only after successful upload
        try:
            if ph_path and os.path.exists(ph_path):
                os.remove(ph_path)
            if path and os.path.exists(path):
                os.remove(path)
            if metadata_path and os.path.exists(metadata_path):
                os.remove(metadata_path)
        except Exception as e:
            logger.warning(f"File cleanup failed: {e}")

    await ms.delete()

    # Auto-delete after 30 minutes
    await asyncio.sleep(1800)
    try:
        await sent_message.delete()
        await deletion_msg.delete()
    except Exception as e:
        logger.warning(f"Failed to delete messages: {e}")

# Remove unused init function
# def init(client):
#     pass