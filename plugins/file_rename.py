# ⚙️ Imports
import os
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from config import Config
from helper.utils import get_readable_file_size, progress_for_pyrogram, time_formatter, get_file_name
from bot.database import increase_rename_count
from pyrogram.enums import ChatAction

# 🛠 Rename command (manual)
@Client.on_message(filters.command("rename") & filters.private)
async def manual_rename(bot, message: Message):
    reply = message.reply_to_message

    # 🧾 Validation
    if not reply or not (reply.document or reply.video or reply.audio):
        return await message.reply("❌ Please reply to a media file to rename it.")

    # 📥 Ask for new file name
    await message.reply("✏️ Send me the new file name (with extension)")
    
    try:
        response = await bot.listen(message.chat.id, timeout=60)
    except asyncio.TimeoutError:
        return await message.reply("⌛ Timed out. Please try again.")

    new_filename = response.text
    if not "." in new_filename:
        return await message.reply("❌ Please include a file extension in the filename.")

    await response.delete()  # 🧹 Clean up user message
    await message.reply("🔄 Rename started...")

    # 🪄 Run in parallel task
    asyncio.create_task(process_rename(bot, message, reply, new_filename))


# 📦 Main renaming process
async def process_rename(bot, message: Message, reply: Message, new_filename: str):
    user_id = message.from_user.id
    download_start = time.time()
    download_path = f"./downloads/{user_id}/"

    try:
        # ⬇️ Download
        os.makedirs(download_path, exist_ok=True)
        sent_dl = await message.reply("📥 Downloading file...")
        media = reply.document or reply.video or reply.audio
        file_path = await reply.download(
            file_name=os.path.join(download_path, new_filename),
            progress=progress_for_pyrogram,
            progress_args=("📥 Downloading...", sent_dl, download_start)
        )
        await sent_dl.edit("✅ Download complete!")

        # 📤 Upload
        await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_DOCUMENT)
        sent_up = await message.reply("📤 Uploading file...")
        upload_start = time.time()

        caption = f"📦 File: `{new_filename}`\n🗂 Size: {get_readable_file_size(media.file_size)}"

        await message.reply_document(
            document=file_path,
            caption=caption,
            progress=progress_for_pyrogram,
            progress_args=("📤 Uploading...", sent_up, upload_start)
        )

        await sent_up.edit("✅ Upload complete!")

        # 🧮 Update rename count
        await increase_rename_count(user_id)

    except Exception as e:
        await message.reply(f"❌ Error: {e}")
    finally:
        # 🧹 Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)