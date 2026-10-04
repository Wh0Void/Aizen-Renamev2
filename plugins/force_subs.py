from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import UserNotParticipant
from config import Config
from helper.database import Mythicbotz
from bot.core.cache import cache_manager


async def not_subscribed(_, client, message):
    if not getattr(message, "from_user", None):
        return False

    uid = int(message.from_user.id)
    await Mythicbotz.add_user(client, message)
    if not Config.FORCE_SUB:
        return False

    # Check 5-minute Force-Sub RAM cache first to avoid calling get_chat_member on every message
    cache_key = f"{Config.FORCE_SUB}:{uid}"
    cached_status = cache_manager.fsub_cache.get(cache_key)
    if cached_status is not None:
        return not bool(cached_status)

    try:
        user = await client.get_chat_member(Config.FORCE_SUB, uid)
        if user.status == enums.ChatMemberStatus.BANNED:
            cache_manager.fsub_cache.set(cache_key, False, ttl=60.0)
            return True
        cache_manager.fsub_cache.set(cache_key, True, ttl=300.0)
        return False
    except UserNotParticipant:
        pass
    except Exception:
        # Do not block users if FORCE_SUB channel is misconfigured or unreachable
        return False
    return True


@Client.on_message(filters.private & filters.create(not_subscribed))
async def forces_sub(client, message):
    buttons = [[InlineKeyboardButton(text="📢 ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ", url=f"https://telegram.me/{Config.FORCE_SUB}")]]
    text = (
        f"<blockquote>🔒 <b>ᴀᴄᴄᴇss ʀᴇsᴛʀɪᴄᴛᴇᴅ</b></blockquote>\n\n"
        f"╭─▸ 👋 <b>ʜᴇʟʟᴏ {message.from_user.mention}!</b>\n"
        f"├─▸ 📢 <i>ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴏᴜʀ ᴏꜰꜰɪᴄɪᴀʟ ᴜᴘᴅᴀᴛᴇs ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴜsᴇ ᴛʜɪs ʙᴏᴛ.</i>\n"
        f"╰─▸ 👇 <i>ᴛᴀᴘ ᴛʜᴇ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴊᴏɪɴ & ᴛʀʏ ᴀɢᴀɪɴ!</i>"
    )
    uid = int(message.from_user.id)
    cache_key = f"{Config.FORCE_SUB}:{uid}"
    cache_manager.fsub_cache.delete(cache_key)
    try:
        user = await client.get_chat_member(Config.FORCE_SUB, uid)
        if user.status == enums.ChatMemberStatus.BANNED:
            return await client.send_message(
                uid,
                text=(
                    "<blockquote>🚫 <b>ᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ</b></blockquote>\n"
                    "╰─▸ <i>sᴏʀʀʏ, ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ ꜰʀᴏᴍ ᴜsɪɴɢ ᴛʜɪs ʙᴏᴛ.</i>"
                ),
            )
    except UserNotParticipant:
        return await message.reply_text(text=text, quote=True, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        pass
    return await message.reply_text(text=text, quote=True, reply_markup=InlineKeyboardMarkup(buttons))


# Developer @CosmicBotz
# Telegram Channel @CosmicBotz

