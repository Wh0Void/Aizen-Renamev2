# plugins/destination.py
# ✅ Destination Plugin (MongoDB Version)
# Keeps SAME command names as old file

from pyrogram import Client, filters
from pyrogram.types import Message
from motor.motor_asyncio import AsyncIOMotorClient
from Config import DB_URL, DB_NAME

# Setup MongoDB
mongo = AsyncIOMotorClient(DB_URL)
db = mongo[DB_NAME]
destinations = db["destinations"]  # collection


# ➕ /adddestination <channel_id>
@Client.on_message(filters.private & filters.command("adddestination"))
async def add_destination(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage: `/adddestination -100xxxxxxxxxx`", quote=True)

    channel_id = message.command[1]

    # check duplicate
    if await destinations.find_one({"channel_id": channel_id}):
        return await message.reply_text("⚠️ Destination already exists.", quote=True)

    await destinations.insert_one({"channel_id": channel_id})
    await message.reply_text(f"✅ Destination added:\n`{channel_id}`", quote=True)


# ➖ /removedestination <channel_id>
@Client.on_message(filters.private & filters.command("removedestination"))
async def remove_destination(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage: `/removedestination -100xxxxxxxxxx`", quote=True)

    channel_id = message.command[1]

    result = await destinations.delete_one({"channel_id": channel_id})
    if result.deleted_count == 0:
        return await message.reply_text("⚠️ Destination not found.", quote=True)

    await message.reply_text(f"🗑️ Destination removed:\n`{channel_id}`", quote=True)


# 📋 /listdestinations
@Client.on_message(filters.private & filters.command("listdestinations"))
async def list_destinations(client: Client, message: Message):
    cursor = destinations.find({})
    dest_list = [f"• `{doc['channel_id']}`" async for doc in cursor]

    if not dest_list:
        return await message.reply_text("📭 No destinations saved yet.", quote=True)

    text = "📌 **Saved Destinations:**\n\n" + "\n".join(dest_list)
    await message.reply_text(text, quote=True)


# 🗑️ /cleardestinations
@Client.on_message(filters.private & filters.command("cleardestinations"))
async def clear_destinations(client: Client, message: Message):
    result = await destinations.delete_many({})
    await message.reply_text(f"🧹 Cleared `{result.deleted_count}` destinations.", quote=True)


# 🔍 /checkdestination <channel_id>
@Client.on_message(filters.private & filters.command("checkdestination"))
async def check_destination(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage: `/checkdestination -100xxxxxxxxxx`", quote=True)

    channel_id = message.command[1]

    if await destinations.find_one({"channel_id": channel_id}):
        await message.reply_text(f"✅ Destination `{channel_id}` exists.", quote=True)
    else:
        await message.reply_text(f"❌ Destination `{channel_id}` not found.", quote=True)