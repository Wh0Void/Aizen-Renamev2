# plugins/destination.py

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import pyromod.listen

# Temporary store (replace with DB later)
DESTINATIONS = {}


# 🔹 Initialize plugin
def init(bot: Client):
    print("✅ Destination plugin initialized")


# 🔹 /set_destination command
@Client.on_message(filters.private & filters.command("set_destination"))
async def set_destination(client: Client, message: Message):
    user_id = message.from_user.id

    # Ask user for channel ID
    ask = await message.reply_text(
        "📌 Please send me the **channel ID** (e.g., `-1001234567890`) where files should be saved.\n\n"
        "➝ You must add me as **Admin** in that channel."
    )

    try:
        response = await client.listen(user_id, timeout=60)
        channel_id = response.text.strip()

        DESTINATIONS[user_id] = channel_id
        await message.reply_text(
            f"✅ Destination channel saved: `{channel_id}`",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("📂 View Destination", callback_data="view_destination")]]
            )
        )

    except Exception as e:
        await message.reply_text(f"❌ Timeout or error: {e}")
    finally:
        await ask.delete()


# 🔹 Callback for viewing destination
@Client.on_callback_query(filters.regex("view_destination"))
async def view_destination(client: Client, callback_query):
    user_id = callback_query.from_user.id
    channel_id = DESTINATIONS.get(user_id)

    if channel_id:
        await callback_query.message.edit_text(
            f"📂 Your current destination channel is: `{channel_id}`"
        )
    else:
        await callback_query.message.edit_text(
            "⚠️ You haven’t set any destination channel yet. Use /set_destination."
        )