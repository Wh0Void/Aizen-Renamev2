from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from config import Config
from helper.database import increase_rename_count, get_user_settings
from helper.utils import get_file_name, progress_for_pyrogram, TimeFormatter
import os
import time

@Client.on_message(filters.document | filters.video & filters.private)
async def auto_rename_handler(c: Client, m: Message):
    user_id = m.from_user.id
    settings = await get_user_settings(user_id)
    
    # Extract original file name
    file_name = get_file_name(m)
    file_size = m.document.file_size if m.document else m.video.file_size
    mime_type = m.document.mime_type if m.document else m.video.mime_type

    # Ask user for new file name (if rename_mode is manual)
    if settings.get("rename_mode") == "manual":
        await m.reply_text(
            f"📂 File Name: `{file_name}`\n💾 Size: `{file_size}`\n\nPlease reply with the new file name.",
            quote=True
        )
        return

    # Auto rename mode - ask user output format
    buttons = [
        [
            InlineKeyboardButton("🎞️ Video", callback_data=f"rename|video|{file_name}"),
            InlineKeyboardButton("📁 Document", callback_data=f"rename|document|{file_name}")
        ]
    ]
    await m.reply_text(
        f"📝 Choose output format for `{file_name}`:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@Client.on_callback_query(filters.regex(r"^rename\|"))
async def rename_callback_handler(c: Client, cb: CallbackQuery):
    _, mode, original_file_name = cb.data.split("|")
    m = cb.message.reply_to_message
    user_id = cb.from_user.id

    media = m.document or m.video
    if not media:
        await cb.message.edit("❌ File not found.")
        return

    new_file_name = f"Renamed_{original_file_name}"
    download_path = f"./downloads/{user_id}/{new_file_name}"
    os.makedirs(os.path.dirname(download_path), exist_ok=True)

    # Download with progress
    start = time.time()
    try:
        await cb.message.edit("⬇️ Downloading file...")
        path = await c.download_media(media, file_name=download_path, progress=progress_for_pyrogram, progress_args=("📥 Downloading", cb.message, start))
    except Exception as e:
        return await cb.message.edit(f"❌ Error in download: `{e}`")

    # Send back based on type
    try:
        await cb.message.edit("⬆️ Uploading file...")
        caption = f"**Renamed File:** `{new_file_name}`"
        if mode == "video":
            await c.send_video(
                chat_id=user_id,
                video=path,
                caption=caption,
                supports_streaming=True
            )
        else:
            await c.send_document(
                chat_id=user_id,
                document=path,
                caption=caption
            )
        await cb.message.delete()
        await increase_rename_count(user_id)
    except Exception as e:
        await cb.message.edit(f"❌ Error in upload: `{e}`")
    finally:
        os.remove(path)