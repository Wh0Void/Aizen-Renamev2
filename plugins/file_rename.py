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

# ✅ Queue status constants
QUEUE_IDLE = "idle"
QUEUE_WAITING_NAME = "waiting_name"
QUEUE_PROCESSING = "processing"

# ✅ Handle media files sent (Give user choice)
@Client.on_message(filters.document | filters.video | filters.audio)
async def handle_media(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Initialize user queue if not exists
    if not hasattr(client, 'user_queues'):
        client.user_queues = {}
    
    if user_id not in client.user_queues:
        client.user_queues[user_id] = {
            "files": [],
            "status": QUEUE_IDLE,
            "current_index": 0,
            "start_time": time.time(),
            "temp_file": None  # Store file temporarily
        }
    
    # Store file temporarily (don't add to queue yet)
    file_info = {
        "message": message,
        "original_name": get_file_name(message),
        "new_name": None,
        "processed": False
    }
    
    client.user_queues[user_id]["temp_file"] = file_info
    current_queue_size = len(client.user_queues[user_id]["files"])
    
    # Create choice keyboard
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Rename Now", callback_data=f"rename_now_{user_id}"),
            InlineKeyboardButton("➕ Add to Queue", callback_data=f"add_to_queue_{user_id}")
        ]
    ])
    
    queue_info = f"\n📊 Current Queue: **{current_queue_size}** files" if current_queue_size > 0 else ""
    
    await message.reply_text(
        f"📁 **File Received!**\n"
        f"📄 File: `{file_info['original_name']}`\n"
        f"{queue_info}\n\n"
        f"🤔 **What would you like to do?**\n"
        f"• **Rename Now** - Process this file immediately\n"
        f"• **Add to Queue** - Add to batch processing queue",
        reply_markup=keyboard
    )


# ✅ Handle callback queries for queue management
@Client.on_callback_query()
async def handle_callback(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    # Initialize user_queues if not exists
    if not hasattr(client, 'user_queues'):
        client.user_queues = {}
    
    try:
        if data.startswith("rename_now_"):
            await rename_single_file(client, callback_query)
        elif data.startswith("add_to_queue_"):
            await add_file_to_queue(client, callback_query)
        elif data.startswith("start_rename_"):
            await start_renaming_process(client, callback_query)
        elif data.startswith("view_queue_"):
            await show_queue_status(client, callback_query)
        elif data.startswith("clear_queue_"):
            await clear_user_queue(client, callback_query)
        elif data.startswith("remove_last_"):
            await remove_last_file(client, callback_query)
        elif data.startswith("skip_file_"):
            await skip_current_file(client, callback_query)
        elif data.startswith("stop_queue_"):
            await stop_queue_processing(client, callback_query)
    except Exception as e:
        await callback_query.answer(f"❌ Error: {str(e)}", show_alert=True)


# ✅ Rename single file immediately
async def rename_single_file(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id not in client.user_queues or not client.user_queues[user_id]["temp_file"]:
        await callback_query.answer("❌ No file to rename!", show_alert=True)
        return
    
    file_info = client.user_queues[user_id]["temp_file"]
    original_name = file_info["original_name"]
    ext = os.path.splitext(original_name)[1]
    
    # Set status to waiting for single rename
    client.user_queues[user_id]["status"] = "single_rename"
    
    await callback_query.answer("📝 Starting single file rename...")
    await callback_query.edit_message_text(
        f"📝 **Single File Rename**\n"
        f"📄 File: `{original_name}`\n"
        f"💡 Send new filename (without `{ext}` extension):",
        reply_markup=ForceReply(True)
    )


# ✅ Add file to queue
async def add_file_to_queue(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id not in client.user_queues or not client.user_queues[user_id]["temp_file"]:
        await callback_query.answer("❌ No file to add!", show_alert=True)
        return
    
    # Move file from temp to queue
    file_info = client.user_queues[user_id]["temp_file"]
    client.user_queues[user_id]["files"].append(file_info)
    client.user_queues[user_id]["temp_file"] = None
    
    queue_length = len(client.user_queues[user_id]["files"])
    
    # Create queue management keyboard
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Start Renaming", callback_data=f"start_rename_{user_id}"),
            InlineKeyboardButton("📋 View Queue", callback_data=f"view_queue_{user_id}")
        ],
        [
            InlineKeyboardButton("🗑️ Clear Queue", callback_data=f"clear_queue_{user_id}"),
            InlineKeyboardButton("❌ Remove Last", callback_data=f"remove_last_{user_id}")
        ]
    ])
    
    await callback_query.answer("✅ File added to queue!")
    await callback_query.edit_message_text(
        f"✅ **File Added to Queue!**\n"
        f"📄 File: `{file_info['original_name']}`\n"
        f"📊 Queue Position: **{queue_length}**\n"
        f"📈 Total Files: **{queue_length}**\n\n"
        f"➕ Send more files to add them to queue, or start renaming process below:",
        reply_markup=keyboard
    )


# ✅ Start the renaming process
async def start_renaming_process(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id not in client.user_queues or not client.user_queues[user_id]["files"]:
        await callback_query.answer("❌ No files in queue!", show_alert=True)
        return
    
    queue = client.user_queues[user_id]
    
    if queue["status"] == QUEUE_PROCESSING:
        await callback_query.answer("⚠️ Queue is already being processed!", show_alert=True)
        return
    
    queue["status"] = QUEUE_WAITING_NAME
    queue["current_index"] = 0
    
    await callback_query.answer("🚀 Starting rename process...")
    await process_next_file(client, user_id)


# ✅ Process the next file in queue
async def process_next_file(client: Client, user_id: int):
    if user_id not in client.user_queues:
        return
    
    queue = client.user_queues[user_id]
    files = queue["files"]
    current_index = queue["current_index"]
    
    # Check if all files are processed
    if current_index >= len(files):
        await send_completion_message(client, user_id)
        return
    
    current_file = files[current_index]
    
    # Skip if already processed
    if current_file["processed"]:
        queue["current_index"] += 1
        await process_next_file(client, user_id)
        return
    
    # Ask for new filename
    original_name = current_file["original_name"]
    ext = os.path.splitext(original_name)[1]
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭️ Skip This File", callback_data=f"skip_file_{user_id}"),
            InlineKeyboardButton("⏹️ Stop Queue", callback_data=f"stop_queue_{user_id}")
        ]
    ])
    
    await client.send_message(
        user_id,
        f"📝 **File {current_index + 1}/{len(files)}**\n"
        f"📄 Current: `{original_name}`\n"
        f"📝 Send new filename (without `{ext}` extension):",
        reply_markup=ForceReply(True)
    )
    
    # Also send the file preview with controls
    await current_file["message"].reply_text(
        f"📁 **Renaming this file ({current_index + 1}/{len(files)})**\n"
        f"📄 Original: `{original_name}`\n"
        f"💡 Reply to the message above with new name",
        reply_markup=keyboard
    )


# ✅ Handle rename after ForceReply
@Client.on_message(filters.text & filters.reply)
async def handle_rename(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Initialize user_queues if not exists
    if not hasattr(client, 'user_queues'):
        client.user_queues = {}
    
    # Check if user has active queue
    if user_id not in client.user_queues:
        return await message.reply("⚠️ No active rename process. Send a file first.")
    
    queue = client.user_queues[user_id]
    
    try:
        # Handle single file rename
        if queue["status"] == "single_rename":
            if not queue["temp_file"]:
                return await message.reply("❌ No file to rename!")
            
            file_info = queue["temp_file"]
            original_name = file_info["original_name"]
            ext = os.path.splitext(original_name)[1]
            new_name = message.text.strip() + ext
            
            file_info["new_name"] = new_name
            
            # Process single file
            await process_file_rename(client, message, file_info, 1, 1)
            
            # Clear temp file and reset status
            queue["temp_file"] = None
            queue["status"] = QUEUE_IDLE
            return
        
        # Handle queue rename
        if queue["status"] != QUEUE_WAITING_NAME:
            return
        
        files = queue["files"]
        current_index = queue["current_index"]
        
        if current_index >= len(files):
            return await message.reply("✅ All files processed!")
        
        current_file = files[current_index]
        original_name = current_file["original_name"]
        ext = os.path.splitext(original_name)[1]
        new_name = message.text.strip() + ext
        
        current_file["new_name"] = new_name
        queue["status"] = QUEUE_PROCESSING
        
        # Process the file
        await process_file_rename(client, message, current_file, current_index + 1, len(files))
        
        # Mark as processed and move to next
        current_file["processed"] = True
        queue["current_index"] += 1
        queue["status"] = QUEUE_WAITING_NAME
        
        # Process next file after a short delay
        await asyncio.sleep(1)
        await process_next_file(client, user_id)
        
    except Exception as e:
        await message.reply(f"❌ Error processing rename: {str(e)}")


# ✅ Process individual file rename
async def process_file_rename(client: Client, message: Message, file_info: dict, current: int, total: int):
    user_id = message.from_user.id
    file_message = file_info["message"]
    new_name = file_info["new_name"]
    
    sent_msg = await message.reply(f"⏳ **Processing {current}/{total}**\n📁 Renaming to: `{new_name}`...")
    
    try:
        # Download file
        file_path = await file_message.download(file_name=new_name)
        
        # Forward to bin channel (if configured)
        if hasattr(Config, 'BIN_CHANNEL') and Config.BIN_CHANNEL and Config.BIN_CHANNEL != "None":
            try:
                await client.send_document(
                    chat_id=int(Config.BIN_CHANNEL),  # Ensure it's an integer
                    document=file_path,
                    caption=f"👤 Uploaded by: [{message.from_user.first_name}](tg://user?id={user_id})\n📦 File: `{new_name}` ({current}/{total})",
                    file_name=new_name
                )
                print(f"✅ File backed up to bin channel: {new_name}")
            except Exception as e:
                print(f"⚠️ Warning: Could not upload to bin channel: {e}")
        
        # Upload to user
        try:
            file_size = human_readable_size(os.path.getsize(file_path))
            await file_message.reply_document(
                document=file_path,
                caption=f"✅ **Renamed Successfully! ({current}/{total})**\n📁 `{new_name}`\n📦 Size: `{file_size}`"
            )
            await sent_msg.delete()
        except Exception as e:
            await sent_msg.edit(f"❌ Failed to send file: {e}")
    
    except Exception as e:
        await sent_msg.edit(f"❌ Error processing file: {e}")
    
    finally:
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Warning: Could not remove file {file_path}: {e}")


# ✅ Show queue status
async def show_queue_status(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id not in client.user_queues or not client.user_queues[user_id]["files"]:
        await callback_query.answer("📭 Queue is empty!", show_alert=True)
        return
    
    queue = client.user_queues[user_id]
    files = queue["files"]
    current_index = queue["current_index"]
    
    status_text = f"📋 **Queue Status**\n\n"
    status_text += f"📊 Total Files: **{len(files)}**\n"
    status_text += f"✅ Processed: **{len([f for f in files if f['processed']])}**\n"
    status_text += f"⏳ Remaining: **{len(files) - current_index}**\n"
    status_text += f"🔄 Status: **{queue['status'].replace('_', ' ').title()}**\n\n"
    
    status_text += "📁 **Files in Queue:**\n"
    for i, file_info in enumerate(files):
        status = "✅" if file_info["processed"] else ("🔄" if i == current_index else "⏳")
        status_text += f"{status} {i+1}. `{file_info['original_name']}`\n"
    
    await callback_query.edit_message_text(status_text)


# ✅ Clear user queue
async def clear_user_queue(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id in client.user_queues:
        client.user_queues[user_id] = {
            "files": [],
            "status": QUEUE_IDLE,
            "current_index": 0,
            "start_time": time.time(),
            "temp_file": None
        }
    
    await callback_query.answer("🗑️ Queue cleared!", show_alert=True)
    await callback_query.edit_message_text("✅ **Queue Cleared!**\nSend new files to start over.")


# ✅ Remove last file from queue
async def remove_last_file(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id not in client.user_queues or not client.user_queues[user_id]["files"]:
        await callback_query.answer("📭 Queue is empty!", show_alert=True)
        return
    
    queue = client.user_queues[user_id]
    if queue["status"] == QUEUE_PROCESSING:
        await callback_query.answer("⚠️ Cannot remove files while processing!", show_alert=True)
        return
    
    removed_file = queue["files"].pop()
    await callback_query.answer(f"🗑️ Removed: {removed_file['original_name']}", show_alert=True)
    
    remaining = len(queue["files"])
    if remaining == 0:
        await callback_query.edit_message_text("✅ **Queue is now empty!**\nSend files to start over.")
    else:
        await callback_query.edit_message_text(f"✅ **File Removed!**\n📊 Remaining files: **{remaining}**")


# ✅ Skip current file
async def skip_current_file(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id not in client.user_queues:
        await callback_query.answer("❌ No active queue!", show_alert=True)
        return
    
    queue = client.user_queues[user_id]
    files = queue["files"]
    current_index = queue["current_index"]
    
    if current_index < len(files):
        files[current_index]["processed"] = True  # Mark as skipped
        queue["current_index"] += 1
        
        await callback_query.answer("⏭️ File skipped!", show_alert=True)
        await process_next_file(client, user_id)
    else:
        await callback_query.answer("✅ No more files to skip!", show_alert=True)


# ✅ Stop queue processing
async def stop_queue_processing(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id in client.user_queues:
        queue = client.user_queues[user_id]
        processed_count = len([f for f in queue["files"] if f["processed"]])
        total_count = len(queue["files"])
        
        client.user_queues[user_id]["status"] = QUEUE_IDLE
        
        await callback_query.answer("⏹️ Queue processing stopped!", show_alert=True)
        await callback_query.edit_message_text(
            f"⏹️ **Queue Processing Stopped!**\n\n"
            f"📊 Progress: **{processed_count}/{total_count}** files processed\n"
            f"💡 You can resume by clicking 'Start Renaming' again."
        )


# ✅ Send completion message
async def send_completion_message(client: Client, user_id: int):
    queue = client.user_queues[user_id]
    files = queue["files"]
    total_files = len(files)
    processed_files = len([f for f in files if f["processed"]])
    
    completion_text = f"🎉 **Queue Processing Complete!**\n\n"
    completion_text += f"📊 **Summary:**\n"
    completion_text += f"✅ Processed: **{processed_files}/{total_files}** files\n"
    completion_text += f"⏭️ Skipped: **{total_files - processed_files}** files\n"
    completion_text += f"⏱️ Total Time: **{int(time.time() - queue['start_time'])}** seconds\n\n"
    completion_text += f"🔄 Send more files to start a new queue!"
    
    # Clear the queue
    client.user_queues[user_id] = {
        "files": [],
        "status": QUEUE_IDLE,
        "current_index": 0,
        "start_time": time.time(),
        "temp_file": None
    }
    
    await client.send_message(user_id, completion_text)


# ✅ Initialize client-specific storage
def init(client: Client):
    """Initialize the rename plugin for the client"""
    if not hasattr(client, "user_queues"):
        client.user_queues = {}
    print("✅ File rename plugin initialized successfully!")