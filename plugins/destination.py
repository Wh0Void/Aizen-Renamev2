# plugins/destination.py
from pyrogram import Client, filters
from pyrogram.types import Message
from helper.database import jishubotz


# ➕ /adddestination <channel_id>
@Client.on_message(filters.private & filters.command("adddestination"))
async def add_destination(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage: `/adddestination -100xxxxxxxxxx`", quote=True)

    channel_id = message.command[1]
    await jishubotz.save_destination_channel(message.from_user.id, channel_id)
    await message.reply_text(f"✅ Destination saved:\n`{channel_id}`", quote=True)


# ➖ /removedestination
@Client.on_message(filters.private & filters.command("removedestination"))
async def remove_destination(client: Client, message: Message):
    await jishubotz.clear_destination_channel(message.from_user.id)
    await message.reply_text("🗑️ Destination removed successfully.", quote=True)


# 📋 /listdestinations
@Client.on_message(filters.private & filters.command("listdestinations"))
async def list_destinations(client: Client, message: Message):
    channel_id = await jishubotz.get_destination_channel(message.from_user.id)
    if not channel_id:
        return await message.reply_text("📭 No destination channel set.", quote=True)

    await message.reply_text(f"📌 Current destination:\n`{channel_id}`", quote=True)


# 🧹 /cleardestinations
@Client.on_message(filters.private & filters.command("cleardestinations"))
async def clear_destinations(client: Client, message: Message):
    await jishubotz.clear_destination_channel(message.from_user.id)
    await message.reply_text("🧹 Destination cleared.", quote=True)


# 🔍 /checkdestination <channel_id>
@Client.on_message(filters.private & filters.command("checkdestination"))
async def check_destination(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage: `/checkdestination -100xxxxxxxxxx`", quote=True)

    channel_id = message.command[1]
    current = await jishubotz.get_destination_channel(message.from_user.id)

    if current == int(channel_id):
        await message.reply_text(f"✅ Destination `{channel_id}` is set.", quote=True)
    else:
        await message.reply_text(f"❌ Destination `{channel_id}` is not set.", quote=True)