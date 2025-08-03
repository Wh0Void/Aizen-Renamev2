# file_rename.py

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply, CallbackQuery
from config import Config
from bot.utils import get_file_name, human_readable_size
from bot.database import update_user_token, is_user_premium
import os
import time
import asyncio
from typing import Dict, List, Optional

# ✅ Queue status constants
QUEUE_IDLE = "idle"
QUEUE_WAITING_NAME = "waiting_name"
QUEUE_PROCESSING = "processing"

# ✅ Handle media files sent (Add to queue)
@Client.on_message(filters.document | filters.video | filters.audio)
async def handle_media(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Initialize user queue if not exists
    if user_id not in client.user_queues:
        client.user_queues[user_id] = {
            "files": [],
            "status": QUEUE_IDLE,
            "current_index": 0,
            "start_time": time.time()
        }
    
    # Add file to queue
    file_info = {
        "message": message,
        "original_name": get_file_name(message),
        "new_name": None,
        "processed": False
    }
    
    client.user_queues[user_id]["files"].append(file_info)
    queue_length = len(client.user_queues[user_id]["files"])
    
    # Create inline keyboard for queue management
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
    
    await message.reply_text(
        f"📁 **File Added to Queue!**\n"
        f"📄 File: `{file_info['original_name']}`\n"
        f"📊 Queue Position: **{queue_length}**\n"
        f"📈 Total Files: **{queue_length}**\n\n"
        f"➕ Send more files to add them to queue, or start renaming process below:",
        reply_markup=keyboard
    )


# ✅ Handle callback queries for queue management
@Client.on_callback_query()
async def handle_callback(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    if data.startswith("start_rename_"):
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
    
    # Check if user has active queue
    if user_id not in client.user_queues:
        return await message.reply("⚠️ No active rename queue. Send files first.")
    
    queue = client.user_queues[user_id]
    
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


# ✅ Process individual file rename
async def process_file_rename(client: Client, message: Message, file_info: dict, current: int, total: int):
    user_id = message.from_user.id
    file_message = file_info["message"]
    new_name = file_info["new_name"]
    
    sent_msg = await message.reply(f"⏳ **Processing {current}/{total}**\n📁 Renaming to: `{new_name}`...")
    
    try:
        # Download file
        file_path = await file_message.download(file_name=new_name)
        
        # Forward to bin channel
        try:
            await client.send_document(
                chat_id=Config.BIN_CHANNEL,
                document=file_path,
                caption=f"👤 Uploaded by: [{message.from_user.first_name}](tg://user?id={user_id})\n📦 File: `{new_name}` ({current}/{total})",
                file_name=new_name
            )
        except Exception as e:
            await sent_msg.edit(f"❌ Error uploading to bin: {e}")
            return
        
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
            os.remove(file_path)


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
            "start_time": time.time()
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
        "start_time": time.time()
    }
    
    await client.send_message(user_id, completion_text)


# ✅ Initialize client-specific storage
def init(client: Client):
    if not hasattr(client, "user_queues"):
        client.user_queues = {}