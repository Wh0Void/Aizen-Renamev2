from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from pyrogram.errors import FloodWait
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from helper.ffmpeg import fix_thumb, take_screen_shot, add_metadata
from helper.utils import progress_for_pyrogram, convert, humanbytes, add_prefix_suffix
from helper.database import jishubotz
from config import Config
from asyncio import sleep
from PIL import Image
import os, time, random, asyncio

# ---------------------- Rename Start ---------------------- #
@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def rename_start(client, message):
    file = getattr(message, message.media.value)
    filename = file.file_name

    # Check if banned
    if await jishubotz.is_banned(message.from_user.id):
        return await message.reply(
            "**You are banned from using this bot. Contact @PS_TalkBot to resolve!**"
        )

    if file.file_size > 2000 * 1024 * 1024:
        return await message.reply_text("Sorry, this bot doesn't support files larger than 2GB.")

    try:
        await message.reply_text(
            text=f"**Please Enter New Filename...**\n\n**Old File Name** :- `{filename}`",
            reply_to_message_id=message.id,
            reply_markup=ForceReply(True)
        )
        await sleep(30)
    except FloodWait as e:
        await sleep(e.value)
        await message.reply_text(
            text=f"**Please Enter New Filename**\n\n**Old File Name** :- `{filename}`",
            reply_to_message_id=message.id,
            reply_markup=ForceReply(True)
        )
    except Exception as e:
        print(f"Error in rename_start: {e}")

    await asyncio.sleep(600)
    await message.delete()

# ---------------------- Reply Handler ---------------------- #
@Client.on_message(filters.private & filters.reply)
async def refunc(client, message):
    reply_message = message.reply_to_message
    if reply_message.reply_markup and isinstance(reply_message.reply_markup, ForceReply):
        new_name = message.text
        await message.delete()
        msg = await client.get_messages(message.chat.id, reply_message.id)
        file = msg.reply_to_message
        media = getattr(file, file.media.value)

        if "." not in new_name:
            extn = media.file_name.rsplit(".", 1)[-1] if "." in media.file_name else "mkv"
            new_name = f"{new_name}.{extn}"

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

# ---------------------- Callback Query ---------------------- #
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
        return await update.message.edit(f"Failed to set Prefix/Suffix: `{e}`")

    file_path = f"downloads/{update.from_user.id}/{new_filename}"
    file = update.message.reply_to_message

    try:
        ms = await update.message.edit("🚀 Downloading... ⚡")
    except Exception as e:
        print(f"Edit error: {e}")

    try:
        path = await bot.download_media(
            message=file,
            file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=("🚀 Downloading... ⚡", ms, time.time())
        )
    except Exception as e:
        return await ms.edit(f"Download Error: {e}")

    # ---------------- Metadata ---------------- #
    _bool_metadata = await jishubotz.get_metadata(update.message.chat.id)
    if _bool_metadata:
        metadata = await jishubotz.get_metadata_code(update.message.chat.id)
        metadata_path = f"Metadata/{new_filename}"
        await add_metadata(path, metadata_path, metadata, ms)
    else:
        await ms.edit("⏳ Processing... ⚡")

    # ---------------- Duration ---------------- #
    duration = 0
    try:
        parser = createParser(file_path)
        meta = extractMetadata(parser)
        if meta.has("duration"):
            duration = meta.get("duration").seconds
        parser.close()
    except:
        pass

    # ---------------- Thumbnail ---------------- #
    ph_path = None
    c_thumb = await jishubotz.get_thumbnail(update.message.chat.id)
    if file.media.thumbs or c_thumb:
        if c_thumb:
            ph_path = await bot.download_media(c_thumb)
            width, height, ph_path = await fix_thumb(ph_path)
        else:
            try:
                ph_path_ = await take_screen_shot(file_path, os.path.dirname(file_path), random.randint(0, duration-1))
                width, height, ph_path = await fix_thumb(ph_path_)
            except:
                ph_path = None

    # ---------------- Caption ---------------- #
    c_caption = await jishubotz.get_caption(update.message.chat.id)
    if c_caption:
        try:
            caption = c_caption.format(filename=new_filename, filesize=humanbytes(file.file_size), duration=convert(duration))
        except:
            caption = f"**{new_filename}**"
    else:
        caption = f"**{new_filename}**\n**User:** {update.message.chat.first_name}\n**User ID:** {update.from_user.id}"

    # ---------------- Upload ---------------- #
    type_ = update.data.split("_")[1]
    try:
        if type_ == "document":
            sent_message = await bot.send_document(
                update.message.chat.id,
                document=metadata_path if _bool_metadata else file_path,
                thumb=ph_path,
                caption=caption,
                progress=progress_for_pyrogram,
                progress_args=("💠 Uploading... ⚡", ms, time.time())
            )
        elif type_ == "video":
            sent_message = await bot.send_video(
                update.message.chat.id,
                video=metadata_path if _bool_metadata else file_path,
                thumb=ph_path,
                caption=caption,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("💠 Uploading... ⚡", ms, time.time())
            )
        elif type_ == "audio":
            sent_message = await bot.send_audio(
                update.message.chat.id,
                audio=metadata_path if _bool_metadata else file_path,
                thumb=ph_path,
                caption=caption,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("💠 Uploading... ⚡", ms, time.time())
            )

        # ---------------- Forward to BIN_CHANNEL ---------------- #
        await bot.forward_messages(Config.BIN_CHANNEL, update.message.chat.id, sent_message.id)

        # ---------------- Forward to Destination ---------------- #
        dest_channel = await jishubotz.get_destination_channel(update.from_user.id)
        if dest_channel:
            try:
                await bot.copy_message(
                    chat_id=dest_channel,
                    from_chat_id=update.message.chat.id,
                    message_id=sent_message.id
                )
            except Exception as e:
                print(f"Destination forward failed: {e}")

        deletion_msg = await sent_message.reply("🗑 This file will auto-delete in 30 minutes. Save it now!")

    except Exception as e:
        os.remove(file_path)
        if ph_path: os.remove(ph_path)
        return await ms.edit(f"Upload Error: {e}")

    await ms.delete()
    if ph_path: os.remove(ph_path)
    if file_path: os.remove(file_path)

    await asyncio.sleep(1800)
    try:
        await sent_message.delete()
        await deletion_msg.delete()
    except Exception as e:
        print(f"Delete after 30 mins error: {e}")