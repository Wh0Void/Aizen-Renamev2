# ⚙️ token.py – Handles token creation, shortlink, and verification

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
from config import Config
from helper.database import (
    Mythicbotz,
    add_token,
    reduce_token,
    get_token,
    save_token,
    is_token_valid,
    verify_user
)  # Updated imports
import requests
from pyrogram.types import CallbackQuery


# 🧠 CONSTANTS
TOKEN_DURATION = timedelta(hours=Config.TOKEN_TIME)

# ⚡ /gettoken command – Generates and sends shortlink for verification
@Client.on_message(filters.command("gettoken") & filters.private)
async def get_token_handler(client, message: Message):
    user_id = message.from_user.id

    # Make shortlink for verification
    try:
        link = f"https://t.me/{client.me.username}?start=verify_{user_id}"
        api_key = Config.SHORTLINK_API
        api_url = Config.SHORTLINK_DOMAIN

        res = requests.get(f"{api_url}?api={api_key}&url={link}")
        data = res.json()

        if data.get("status") == "success":
            short_url = data["shortenedUrl"]
        else:
            short_url = link  # fallback
    except Exception as e:
        short_url = link  # fallback on failure

    # Save token expiration and user access timestamp
    await save_token(user_id)

    await message.reply(
        text="🔐 **Token Generated!**\n\nPlease click the button below and complete the verification to unlock 12 hours of unlimited access!",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("✅ Verify Now", url=short_url)]]
        )
    )

# 🧠 /verify command (manually or via redirect)
@Client.on_message(filters.command("verify") & filters.private)
async def verify_command(client, message: Message):
    user_id = message.from_user.id

    # Check if already verified
    if await Mythicbotz.is_premium(user_id):
        await message.reply("✅ You are already verified and have Premium access!")
        return

    if await is_token_valid(user_id):
        await verify_user(user_id)  # Updating user's premium status
        await message.reply("🎉 **Verification Successful!**\n\nYou now have 12-hour premium access.")
    else:
        await message.reply("❌ Your token is invalid or expired.\nUse /gettoken to generate a new one.")

# ⚠️ Auto file-block: Intercept incoming files from unverified users
@Client.on_message(filters.document | filters.video | filters.audio)
async def block_if_unverified(client, message: Message):
    user_id = message.from_user.id

    if not await Mythicbotz.is_premium(user_id):
        await message.reply_text(
            "**🔒 Access Denied!**\nYou must verify using /gettoken before using the bot.",
            quote=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Verify Access", callback_data="token_verify_help")]
            ])
        )
        return


@Client.on_callback_query(filters.regex("token_verify_help"))
async def token_help(client, query: CallbackQuery):
    await query.answer()
    await query.message.edit(
        "**⚠️ To unlock access:**\n\n1. Use /gettoken\n2. Complete the shortlink\n3. Use /verify\n\nYou’ll get 12-hour premium access.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔁 Get Token", callback_data="get_token_command")]
        ])
    )