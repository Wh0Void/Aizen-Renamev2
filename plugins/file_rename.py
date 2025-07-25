from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from helper.ffmpeg import fix_thumb, take_screen_shot, add_metadata
from helper.utils import progress_for_pyrogram, convert, humanbytes, add_prefix_suffix
from helper.database import jishubotz
from config import Config
from PIL import Image
import os, time, random, asyncio


@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def rename_start(client, message):
    file = getattr(message, message.media.value)
    filename = file.file_name

    if file.file_size > 2000 * 1024 * 1024:
        return await message.reply_text("Sorry, this bot doesn't support files larger than 2GB.")

    try:
        await message.reply_text(
            text=f"**Please Enter New Filename...**\n\n**Old File Name** :- `{filename}`",
            reply_to_message_id=message.id,
            reply_markup=ForceReply(True)
        )
        await asyncio.sleep(30)

    except FloodWait as e:
        await asyncio.sleep(e.value)
        await message.reply_text(
            text=f"**Please Enter New Filename...**\n\n**Old File Name** :- `{filename}`",
            reply_to_message_id=message.id,
            reply_markup=ForceReply(True)
        )
    except Exception as e:
        print(f"Error in rename_start: {e}")


@Client.on_message(filters.private & filters.reply)
async def refunc(client, message):
    reply_message = message.reply_to_message
    if reply_message.reply_markup and isinstance(reply_message.reply_markup, ForceReply):
        new_name = message.text
        await message.delete()
        original_file_msg = await client.get_messages(message.chat.id, reply_message.id)
        file = original_file_msg.reply_to_message
        media = getattr(file, file.media.value)

        if "." not in new_name:
            extn = media.file_name.rsplit(".", 1)[-1] if "." in media.file_name else "mkv"
            new_name = new_name + "." + extn

        await reply_message.delete()

        buttons = [[InlineKeyboardButton("📁 Document", callback_data="upload_document")]]
        if file.media in [MessageMediaType.VIDEO, MessageMediaType.DOCUMENT]:
            buttons.append([InlineKeyboardButton("🎥 Video", callback_data="upload_video")])
        elif file.media == MessageMediaType.AUDIO:
            buttons.append([InlineKeyboardButton("🎵 Audio", callback_data="upload_audio")])

        await message.reply(
            text=f"**Select The Output File Type**\n\n**File Name :-** `{new_name}`",
            reply_to_message_id=file.id,
            reply_markup=InlineKeyboardMarkup(buttons)
        )


@Client.on_callback_query(filters.regex("upload"))
async def doc(bot, update):
    if not os.path.isdir("Metadata"):
        os.mkdir("Metadata")

    prefix = await jishubotz.get_prefix(update.message.chat.id)
    suffix = await jishubotz.get_suffix(update.message.chat.id)

    new_name = update.message.text
    new_filename_ = new_name.split(":-")[1]
    try:
        new_filename = add_prefix_suffix(new_filename_, prefix, suffix)
    except Exception as e:
        return await update.message.edit(
            f"Something went wrong while applying prefix/suffix 😓\n\n**Error:** `{e}`"
        )

    file_path = f"downloads/{update.from_user.id}/{new_filename}"
    file = update.message.reply_to_message
    media = getattr(file, file.media.value)

    ms = await update.message.edit("🚀 Downloading... ⚡")
    try:
        path = await bot.download_media(
            message=file,
            file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=("🚀 Downloading... ⚡", ms, time.time())
        )
    except Exception as e:
        return await ms.edit(f"❌ Download failed: `{e}`")

    # 🔧 Add metadata if enabled
    _bool_metadata = await jishubotz.get_metadata(update.message.chat.id)
    if _bool_metadata:
        metadata_code = await jishubotz.get_metadata_code(update.message.chat.id)
        metadata_path = f"Metadata/{new_filename}"
        await add_metadata(path, metadata_path, metadata_code, ms)
    else:
        await ms.edit("⏳ Preparing Upload... ⚡")

    # 🕒 Duration (for video/audio)
    duration = 0
    try:
        parser = createParser(file_path)
        metadata = extractMetadata(parser)
        if metadata.has("duration"):
            duration = metadata.get("duration").seconds
        parser.close()
    except:
        pass

    # 🖼️ Thumbnail
    ph_path = None
    c_thumb = await jishubotz.get_thumbnail(update.message.chat.id)
    if media.thumbs or c_thumb:
        try:
            if c_thumb:
                ph_path = await bot.download_media(c_thumb)
                width, height, ph_path = await fix_thumb(ph_path)
            else:
                ss = await take_screen_shot(file_path, os.path.dirname(os.path.abspath(file_path)), random.randint(0, duration - 1))
                width, height, ph_path = await fix_thumb(ss)
        except:
            ph_path = None

    # 📝 Caption
    c_caption = await jishubotz.get_caption(update.message.chat.id)
    try:
        caption = c_caption.format(
            filename=new_filename,
            filesize=humanbytes(media.file_size),
            duration=convert(duration)
        ) if c_caption else f"**{new_filename}**"
    except Exception as e:
        return await ms.edit(f"❌ Caption format error: `{e}`")

    await ms.edit("💠 Uploading... ⚡")
    type = update.data.split("_")[1]
    sent_message = None

    try:
        if type == "document":
            sent_message = await bot.send_document(
                chat_id=update.message.chat.id,
                document=metadata_path if _bool_metadata else file_path,
                thumb=ph_path,
                caption=caption,
                progress=progress_for_pyrogram,
                progress_args=("📤 Uploading... ⚡", ms, time.time())
            )
        elif type == "video":
            sent_message = await bot.send_video(
                chat_id=update.message.chat.id,
                video=metadata_path if _bool_metadata else file_path,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("📤 Uploading... ⚡", ms, time.time())
            )
        elif type == "audio":
            sent_message = await bot.send_audio(
                chat_id=update.message.chat.id,
                audio=metadata_path if _bool_metadata else file_path,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("📤 Uploading... ⚡", ms, time.time())
            )

        # ✅ Forward to bin
        await bot.forward_messages(
            chat_id=Config.BIN_CHANNEL,
            from_chat_id=update.message.chat.id,
            message_ids=sent_message.id
        )

        deletion_msg = await sent_message.reply(
            "**🗑 This file will auto-delete in 30 minutes. Save it now!**"
        )

    except Exception as e:
        os.remove(file_path)
        if ph_path: os.remove(ph_path)
        return await ms.edit(f"❌ Upload failed: `{e}`")

    await ms.delete()
    if file_path: os.remove(file_path)
    if ph_path: os.remove(ph_path)

    await asyncio.sleep(1800)  # 30 minutes
    try:
        await sent_message.delete()
        await deletion_msg.delete()
    except:
        pass