# plugins/destination.py
# ✅ Destination Plugin using database.py helper functions

from pyrogram import Client, filters
from pyrogram.types import Message
from helper.database import (
    get_destination_channel,
    save_destination_channel,
    clear_destination_channel,
    set_waiting_for_channel,
    clear_waiting_for_channel,
    is_waiting_for_channel
)


# ➕ /adddestination <channel_id>
@Client.on_message(filters.private & filters.command("adddestination"))
async def add_destination(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage: `/adddestination -100xxxxxxxxxx`", quote=True)

    channel_id = message.command[1]

    await save_destination_channel(channel_id)
    await message.reply_text(f"✅ Destination saved:\n`{channel_id}`", quote=True)


# ➖ /removedestination
@Client.on_message(filters.private & filters.command("removedestination"))
async def remove_destination(client: Client, message: Message):
    await clear_destination_channel()
    await message.reply_text("🗑️ Destination removed successfully.", quote=True)


# 📋 /listdestinations
@Client.on_message(filters.private & filters.command("listdestinations"))
async def list_destinations(client: Client, message: Message):
    channel_id = await get_destination_channel()
    if not channel_id:
        return await message.reply_text("📭 No destination channel set.", quote=True)

    await message.reply_text(f"📌 Current destination:\n`{channel_id}`", quote=True)


# 🧹 /cleardestinations
@Client.on_message(filters.private & filters.command("cleardestinations"))
async def clear_destinations(client: Client, message: Message):
    await clear_destination_channel()
    await message.reply_text("🧹 All destinations cleared.", quote=True)


# 🔍 /checkdestination <channel_id>
@Client.on_message(filters.private & filters.command("checkdestination"))
async def check_destination(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage: `/checkdestination -100xxxxxxxxxx`", quote=True)

    channel_id = message.command[1]
    current = await get_destination_channel()

    if current == channel_id:
        await message.reply_text(f"✅ Destination `{channel_id}` is set.", quote=True)
    else:
        await message.reply_text(f"❌ Destination `{channel_id}` is not set.", quote=True)


# ⚡ Extra (interactive flow) using waiting flags
@Client.on_message(filters.private & filters.command("setdestination"))
async def set_destination_interactive(client: Client, message: Message):
    await set_waiting_for_channel(message.from_user.id)
    await message.reply_text("📩 Please send me the channel ID now.")


@Client.on_message(filters.private & filters.text)
async def handle_channel_input(client: Client, message: Message):
    if await is_waiting_for_channel(message.from_user.id):
        channel_id = message.text.strip()
        await save_destination_channel(channel_id)
        await clear_waiting_for_channel(message.from_user.id)
        await message.reply_text(f"✅ Destination saved via interactive mode:\n`{channel_id}`")