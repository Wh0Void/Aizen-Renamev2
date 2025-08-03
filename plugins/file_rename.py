# file_rename.py

import os
import time
import asyncio
from typing import Dict, List, Optional

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply, CallbackQuery

# Import config and utils properly to avoid circular imports
try:
    from config import Config
except ImportError:
    # Fallback if config import fails
    class Config:
        BIN_CHANNEL = None

try:
    from bot.utils import get_file_name, human_readable_size
except ImportError:
    # Fallback functions if utils import fails
    def get_file_name(message):
        if message.document:
            return message.document.file_name or "unnamed_file"
        elif message.video:
            return message.video.file_name or "unnamed_video.mp4"
        elif message.audio:
            return message.audio.file_name or "unnamed_audio.mp3"
        return "unnamed_file"
    
    def human_readable_size(size_bytes):
        if size_bytes == 0:
            return "0B"
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"

try:
    from bot.database import update_user_token, is_user_premium
except ImportError:
    # Fallback functions if database import fails
    def update_user_token(user_id, token):
        pass
    
    def is_user_premium(user_id):
        return True

# ✅ Simple queue system - just track files, no complex states
user_queues = {}

# ✅ Handle ALL media files (documents, videos, audio, photos)
@Client.on_message(filters.document | filters.video | filters.audio | filters.photo)
async def handle_media(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Initialize user queue if not exists
    if user_id not in user_queues:
        user_queues[user_id] = []
    
    # Get file info
    file_info = {
        "message": message,
        "original_name": get_file_name(message),
        "file_type": get_file_type(message)
    }
    
    # Simple choice: Single rename or add to batch
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Rename Now", callback_data=f"single_{user_id}"),
            InlineKeyboardButton("📦 Add to Batch", callback_data=f"batch_{user_id}")
        ],
        [
            InlineKeyboardButton("📋 View Batch", callback_data=f"view_{user_id}"),
            InlineKeyboardButton("🗑️ Clear Batch", callback_data=f"clear_{user_id}")
        ]
    ])
    
    # Store the current file temporarily
    client.temp_file = {user_id: file_info}
    
    batch_count = len(user_queues[user_id])
    batch_info = f"\n📦 Current Batch: {batch_count} files" if batch_count > 0 else ""
    
    await message.reply_text(
        f"📁 **{file_info['file_type']} Received!**\n"
        f"📄 Name: `{file_info['original_name']}`{batch_info}\n\n"
        f"🤔 **Choose an option:**\n"
        f"• **Rename Now** - Process immediately\n"
        f"• **Add to Batch** - Process multiple files together",
        reply_markup=keyboard
    )


def get_file_type(message):
    """Get file type for display"""
    if message.document:
        return "Document"
    elif message.video:
        return "Video"
    elif message.audio:
        return "Audio"
    elif message.photo:
        return "Photo"
    return "File"


# ✅ Handle callback queries
@Client.on_callback_query()
async def handle_callback(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    try:
        if data.startswith("single_"):
            await handle_single_rename(client, callback_query)
        elif data.startswith("batch_"):
            await add_to_batch(client, callback_query)
        elif data.startswith("view_"):
            await view_batch(client, callback_query)
        elif data.startswith("clear_"):
            await clear_batch(client, callback_query)
        elif data.startswith("process_"):
            await process_batch(client, callback_query)
        elif data.startswith("remove_"):
            await remove_from_batch(client, callback_query)
    except Exception as e:
        await callback_query.answer(f"❌ Error: {str(e)}", show_alert=True)


# ✅ Single file rename (immediate)
async def handle_single_rename(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if not hasattr(client, 'temp_file') or user_id not in client.temp_file:
        await callback_query.answer("❌ No file to rename!", show_alert=True)
        return
    
    file_info = client.temp_file[user_id]
    original_name = file_info["original_name"]
    ext = os.path.splitext(original_name)[1] if original_name else ""
    
    # Mark as single rename mode
    client.rename_mode = {user_id: "single"}
    
    await callback_query.answer("📝 Single rename mode...")
    await callback_query.edit_message_text(
        f"📝 **Single File Rename**\n"
        f"📄 {file_info['file_type']}: `{original_name}`\n\n"
        f"💡 Reply with new filename{f' (without {ext})' if ext else ''}:",
        reply_markup=ForceReply(True)
    )


# ✅ Add file to batch
async def add_to_batch(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if not hasattr(client, 'temp_file') or user_id not in client.temp_file:
        await callback_query.answer("❌ No file to add!", show_alert=True)
        return
    
    file_info = client.temp_file[user_id]
    user_queues[user_id].append(file_info)
    
    # Clear temp file
    del client.temp_file[user_id]
    
    batch_count = len(user_queues[user_id])
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 Process Batch", callback_data=f"process_{user_id}"),
            InlineKeyboardButton("📋 View Batch", callback_data=f"view_{user_id}")
        ],
        [
            InlineKeyboardButton("🗑️ Clear Batch", callback_data=f"clear_{user_id}")
        ]
    ])
    
    await callback_query.answer("✅ Added to batch!")
    await callback_query.edit_message_text(
        f"✅ **Added to Batch!**\n"
        f"📄 File: `{file_info['original_name']}`\n"
        f"📦 Batch Size: **{batch_count}** files\n\n"
        f"📤 Send more files or process the batch:",
        reply_markup=keyboard
    )


# ✅ View batch contents
async def view_batch(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id not in user_queues or not user_queues[user_id]:
        await callback_query.answer("📭 Batch is empty!", show_alert=True)
        return
    
    files = user_queues[user_id]
    
    text = f"📋 **Batch Contents ({len(files)} files):**\n\n"
    for i, file_info in enumerate(files, 1):
        text += f"{i}. {file_info['file_type']}: `{file_info['original_name']}`\n"
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 Process All", callback_data=f"process_{user_id}"),
            InlineKeyboardButton("❌ Remove Last", callback_data=f"remove_{user_id}")
        ],
        [
            InlineKeyboardButton("🗑️ Clear All", callback_data=f"clear_{user_id}")
        ]
    ])
    
    await callback_query.edit_message_text(text, reply_markup=keyboard)


# ✅ Clear batch
async def clear_batch(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id in user_queues:
        user_queues[user_id] = []
    
    await callback_query.answer("🗑️ Batch cleared!")
    await callback_query.edit_message_text("✅ **Batch Cleared!**\nSend files to start a new batch.")


# ✅ Remove last file from batch
async def remove_from_batch(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id not in user_queues or not user_queues[user_id]:
        await callback_query.answer("📭 Batch is empty!", show_alert=True)
        return
    
    removed = user_queues[user_id].pop()
    remaining = len(user_queues[user_id])
    
    await callback_query.answer(f"🗑️ Removed: {removed['original_name']}")
    
    if remaining == 0:
        await callback_query.edit_message_text("✅ **Batch is now empty!**\nSend files to start over.")
    else:
        await callback_query.edit_message_text(f"✅ **File Removed!**\n📦 Remaining: {remaining} files")


# ✅ Process entire batch
async def process_batch(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id not in user_queues or not user_queues[user_id]:
        await callback_query.answer("📭 No files to process!", show_alert=True)
        return
    
    files = user_queues[user_id]
    
    # Mark as batch rename mode
    client.rename_mode = {user_id: "batch"}
    client.batch_index = {user_id: 0}
    
    await callback_query.answer("🚀 Starting batch processing...")
    await process_next_in_batch(client, user_id)


# ✅ Process next file in batch
async def process_next_in_batch(client: Client, user_id: int):
    if user_id not in user_queues or not user_queues[user_id]:
        return
    
    files = user_queues[user_id]
    index = client.batch_index.get(user_id, 0)
    
    if index >= len(files):
        # Batch complete
        await client.send_message(
            user_id,
            f"🎉 **Batch Processing Complete!**\n"
            f"✅ Processed {len(files)} files successfully!\n"
            f"📤 Send more files to start a new batch."
        )
        user_queues[user_id] = []  # Clear batch
        return
    
    current_file = files[index]
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭️ Skip This File", callback_data=f"skip_{user_id}")]
    ])
    
    ext = os.path.splitext(current_file["original_name"])[1] if current_file["original_name"] else ""
    
    await client.send_message(
        user_id,
        f"📝 **File {index + 1}/{len(files)}**\n"
        f"📄 {current_file['file_type']}: `{current_file['original_name']}`\n\n"
        f"💡 Reply with new filename{f' (without {ext})' if ext else ''}:",
        reply_markup=ForceReply(True)
    )


# ✅ Handle text replies (filenames)
@Client.on_message(filters.text & filters.reply)
async def handle_rename_reply(client: Client, message: Message):
    user_id = message.from_user.id
    
    if not hasattr(client, 'rename_mode') or user_id not in client.rename_mode:
        return
    
    mode = client.rename_mode[user_id]
    new_name = message.text.strip()
    
    if mode == "single":
        # Handle single file rename
        if not hasattr(client, 'temp_file') or user_id not in client.temp_file:
            return await message.reply("❌ No file to rename!")
        
        file_info = client.temp_file[user_id]
        await rename_file(client, message, file_info, new_name, 1, 1)
        
        # Clean up
        del client.temp_file[user_id]
        del client.rename_mode[user_id]
        
    elif mode == "batch":
        # Handle batch file rename
        if user_id not in user_queues or not user_queues[user_id]:
            return await message.reply("❌ No files in batch!")
        
        files = user_queues[user_id]
        index = client.batch_index.get(user_id, 0)
        
        if index >= len(files):
            return await message.reply("✅ Batch processing complete!")
        
        current_file = files[index]
        await rename_file(client, message, current_file, new_name, index + 1, len(files))
        
        # Move to next file
        client.batch_index[user_id] = index + 1
        await asyncio.sleep(1)
        await process_next_in_batch(client, user_id)


# ✅ Actual file renaming function
async def rename_file(client: Client, message: Message, file_info: dict, new_name: str, current: int, total: int):
    user_id = message.from_user.id
    file_message = file_info["message"]
    original_name = file_info["original_name"]
    
    # Add extension if not provided
    ext = os.path.splitext(original_name)[1] if original_name else ""
    if ext and not new_name.endswith(ext):
        new_name += ext
    
    progress_msg = await message.reply(f"⏳ **Processing {current}/{total}**\n📁 Renaming to: `{new_name}`...")
    
    try:
        # Download file
        file_path = await file_message.download(file_name=new_name)
        
        # Upload to bin channel if configured
        if hasattr(Config, 'BIN_CHANNEL') and Config.BIN_CHANNEL and Config.BIN_CHANNEL != "None":
            try:
                await client.send_document(
                    chat_id=int(Config.BIN_CHANNEL),
                    document=file_path,
                    caption=f"👤 User: [{message.from_user.first_name}](tg://user?id={user_id})\n📦 File: `{new_name}` ({current}/{total})",
                    file_name=new_name
                )
            except Exception as e:
                print(f"⚠️ Could not upload to bin channel: {e}")
        
        # Send renamed file to user
        file_size = human_readable_size(os.path.getsize(file_path))
        
        if file_info["file_type"] == "Photo":
            await file_message.reply_photo(
                photo=file_path,
                caption=f"✅ **Renamed! ({current}/{total})**\n📁 `{new_name}`\n📦 Size: `{file_size}`"
            )
        elif file_info["file_type"] == "Video":
            await file_message.reply_video(
                video=file_path,
                caption=f"✅ **Renamed! ({current}/{total})**\n📁 `{new_name}`\n📦 Size: `{file_size}`"
            )
        elif file_info["file_type"] == "Audio":
            await file_message.reply_audio(
                audio=file_path,
                caption=f"✅ **Renamed! ({current}/{total})**\n📁 `{new_name}`\n📦 Size: `{file_size}`"
            )
        else:
            await file_message.reply_document(
                document=file_path,
                caption=f"✅ **Renamed! ({current}/{total})**\n📁 `{new_name}`\n📦 Size: `{file_size}`"
            )
        
        await progress_msg.delete()
        
    except Exception as e:
        await progress_msg.edit(f"❌ Error renaming file: {str(e)}")
    
    finally:
        # Clean up downloaded file
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"⚠️ Could not remove temp file: {e}")


# ✅ Initialize plugin
def init(client: Client):
    """Initialize the rename plugin"""
    if not hasattr(client, "temp_file"):
        client.temp_file = {}
    if not hasattr(client, "rename_mode"):
        client.rename_mode = {}
    if not hasattr(client, "batch_index"):
        client.batch_index = {}
    print("✅ File rename plugin initialized successfully!")