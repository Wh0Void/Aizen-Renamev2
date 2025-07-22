# ⚙️ token.py – Handles token creation, shortlink, and verification

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from config import Config
from bot.database import save_token, is_token_valid
import requests
import time


# 🧠 Command: /gettoken → generate shortlink
@Client.on_message(filters.command("gettoken") & filters.private)
async def get_token(client, message: Message):
    user_id = message.from_user.id
    verify_link = f"https://t.me/{client.me.username}?start=verify_{user_id}"

    try:
        short_url = create_shortlink(verify_link)
    except Exception as e:
        return await message.reply(f"❌ Error generating shortlink:\n`{e}`")

    # 📩 Send shortlink button
    await message.reply(
        text="🔐 **To get access for 12 hours, click below and complete the shortlink**:",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔗 Get 12H Access", url=short_url)]]
        )
    )


# 🧠 Start command handler for verifying token
@Client.on_message(filters.command("start") & filters.private)
async def start_verify(client, message: Message):
    args = message.text.split(" ", 1)
    if len(args) == 2 and args[1].startswith("verify_"):
        user_id_str = args[1].split("_")[1]

        if str(message.from_user.id) != user_id_str:
            return await message.reply("🚫 Invalid verification link. Please request a new token.")

        # ✅ Store token timestamp
        await save_token(message.from_user.id)
        await message.reply(
            "✅ **Token Verified!**\nYou now have 12-hour access to use the bot.",
        )
    elif message.text == "/start":
        await message.reply("👋 Welcome! Use /gettoken to access bot features.")


# 🛠️ Create shortlink via SetURL.in API
def create_shortlink(destination_url: str) -> str:
    api_key = Config.SHORTLINK_API
    domain = Config.SHORTLINK_DOMAIN

    response = requests.get(
        f"{domain}/api",
        params={
            "api": api_key,
            "url": destination_url
        }
    )
    result = response.json()
    if result["status"] != "success":
        raise Exception(result.get("message", "Unknown error"))

    return result["shortenedUrl"]