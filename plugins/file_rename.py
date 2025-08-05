# ⚙️ Imports
import os
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from helper.utils import progress_for_pyrogram,TimeFormatter,get_file_name
from helper.utils import humanbytes as get_readable_file_size
from helper.database import Database
from pyrogram.enums import ChatAction

# rename.py
# ✅ Automatic rename handler when user sends video/document/photo
InlineKeyboardButton, InlineKeyboardMarkup

from config import Config
from helper.database import add_user, is_premium, increase_rename_count
from helper.database import set_rename_mode, get_rename_mode

import time, os

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_handler(bot: Client, message: Message):
    await add_user(message.from_user.id)

    user_id = message.from_user.id
    rename_mode = await get_rename_mode(user_id)

    media = message.document or message.video or message.audio
    if not media:
        return

    file_name = get_file_name(message)
    file_size = media.file_size
    media_type = media.mime_type or "application/octet-stream"

    # Ask user for new filename
    buttons = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✏️ Rename", callback_data="rename_now"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]]
    )

    caption = f"📂 <b>File Name:</b> <code>{file_name}</code>\n"
    caption += f"📦 <b>Size:</b> <code>{human_readable_size(file_size)}</code>\n"
    caption += f"🧷 <b>Type:</b> <code>{media_type}</code>\n\n"
    caption += "Do you want to rename this file?"

    await message.reply_text(
        text=caption,
        reply_markup=buttons,
        quote=True
    )

    # Save file_id for later use during rename
    bot.user_data = getattr(bot, "user_data", {})
    bot.user_data[user_id] = {
        "file_id": media.file_id,
        "file_type": media.mime_type,
        "original_name": file_name,
        "sent_message_id": message.id
    }

@Client.on_callback_query(filters.regex("rename_now"))
async def prompt_new_filename(bot, callback_query):
    await callback_query.message.edit("✏️ Send me the new file name (with extension):")
    bot.waiting_for_filename = getattr(bot, "waiting_for_filename", {})
    bot.waiting_for_filename[callback_query.from_user.id] = True

@Client.on_message(filters.private & filters.text)
async def receive_new_filename(bot, message: Message):
    user_id = message.from_user.id
    if not getattr(bot, "waiting_for_filename", {}).get(user_id):
        return

    new_filename = message.text.strip()
    file_data = getattr(bot, "user_data", {}).get(user_id)

    if not file_data:
        await message.reply_text("⚠️ No file found to rename. Please send a file again.")
        return

    # Start download
    try:
        file_path = await bot.download_media(
            file_data["file_id"],
            file_name=new_filename,
            progress=progress_for_pyrogram,
            progress_args=("📥 Downloading...", message)
        )

        # Upload renamed file
        await message.reply_chat_action("upload_document")

        await message.reply_document(
            document=file_path,
            caption=f"✅ File renamed to: <code>{new_filename}</code>",
            progress=progress_for_pyrogram,
            progress_args=("📤 Uploading...", message)
        )

        # Increase rename count
        await increase_rename_count(user_id)

        os.remove(file_path)

    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

    # Clean up
    bot.waiting_for_filename[user_id] = False
    bot.user_data[user_id] = None