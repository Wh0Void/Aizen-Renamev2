# rename.py

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from config import Config
from bot.utils import get_file_name, human_readable_size
from bot.database import update_user_token, is_user_premium
import os
import time
import asyncio

# ✅ Handle media files sent
@Client.on_message(filters.document | filters.video | filters.audio)
async def handle_media(client: Client, message: Message):
    user_id = message.from_user.id

    # ✅ Save original message ID to identify it during renaming
    client.user_queues[user_id] = {
        "file_message": message,
        "start_time": time.time(),
    }

    # ✅ Ask for the new filename
    await message.reply_text(
        text="📂 Send me new file name (without extension):",
        reply_markup=ForceReply(True)
    )


# ✅ Handle rename after ForceReply
@Client.on_message(filters.text & filters.reply)
async def handle_rename(client: Client, message: Message):
    user_id = message.from_user.id
    replied = message.reply_to_message

    # ✅ Check if user has pending media
    if user_id not in client.user_queues:
        return await message.reply("⚠️ No active file to rename. Send a video/document first.")

    file_message = client.user_queues[user_id]["file_message"]

    # ✅ Get original file name & extension
    original = get_file_name(file_message)
    ext = os.path.splitext(original)[1]
    new_name = message.text.strip() + ext

    sent_msg = await message.reply(f"⏳ Renaming and uploading `{new_name}`...")

    # ✅ Download file
    file_path = await file_message.download(file_name=new_name)
    
    # ✅ Forward to bin channel
    try:
        await client.send_document(
            chat_id=Config.BIN_CHANNEL,
            document=file_path,
            caption=f"👤 Uploaded by: [{message.from_user.first_name}](tg://user?id={user_id})\n📦 File: `{new_name}`",
            file_name=new_name
        )
    except Exception as e:
        await sent_msg.edit(f"❌ Error uploading to bin: {e}")
        return

    # ✅ Upload to user
    try:
        await file_message.reply_document(
            document=file_path,
            caption=f"✅ **Renamed Successfully!**\n📁 `{new_name}`\n📦 Size: `{human_readable_size(os.path.getsize(file_path))}`"
        )
        await sent_msg.delete()
    except Exception as e:
        await sent_msg.edit(f"❌ Failed to send file to user: {e}")
    finally:
        os.remove(file_path)
        client.user_queues.pop(user_id, None)


# ✅ Initialize client-specific storage
def init(client: Client):
    if not hasattr(client, "user_queues"):
        client.user_queues = {}