# bot/destination.py
# ✨ Destination Channel feature (Set once → every renamed file is copied to that channel)

from typing import Optional, Tuple
from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
import re

# 🧠 Import your DB helper functions
from helper.database import (
    save_destination_channel,
    get_destination_channel,
    clear_destination_channel,
    set_waiting_for_channel,
    is_waiting_for_channel,
    clear_waiting_for_channel,
)

# 🔧 Optional banner image for the settings card
try:
    from config import DESTINATION_PIC_URL
except Exception:
    DESTINATION_PIC_URL = None

# 🔖 Callback IDs
CB_SET_DEST = "set_dest_channel"
CB_CLEAR_DEST = "clear_dest_channel"
CB_HELP_DEST = "dest_help"


# 🧩 UI Keyboard
def _dest_kb(current: Optional[int]) -> InlineKeyboardMarkup:
    label = f"📡 Set Destination Channel" if not current else f"📡 Change Destination (now: {current})"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(label, callback_data=CB_SET_DEST)],
            [InlineKeyboardButton("🗑️ Clear Destination", callback_data=CB_CLEAR_DEST)],
            [InlineKeyboardButton("❓ How it works", callback_data=CB_HELP_DEST)],
        ]
    )


# 🖼️ Show card
async def _send_dest_card(c: Client, m: Message) -> None:
    uid = m.from_user.id
    current = await get_destination_channel(uid)
    caption = (
        "🧭 <b>Destination Channel</b>\n\n"
        "• Set a channel once, and every renamed file will also be posted there automatically.\n"
        "• Bot must be <b>Admin</b> in that channel with permission to post.\n\n"
        f"<i>Current:</i> <code>{current}</code>" if current else
        "🧭 <b>Destination Channel</b>\n\n"
        "• Set a channel once, and every renamed file will also be posted there automatically.\n"
        "• Bot must be <b>Admin</b> in that channel with permission to post.\n\n"
        "<i>Current:</i> <code>Not set</code>"
    )
    if DESTINATION_PIC_URL:
        await m.reply_photo(photo=DESTINATION_PIC_URL, caption=caption, reply_markup=_dest_kb(current))
    else:
        await m.reply_text(caption, reply_markup=_dest_kb(current))


# 🔘 Commands
@Client.on_message(filters.command(["setchannel", "setdest"]) & filters.private)
async def cmd_setchannel(c: Client, m: Message):
    await _send_dest_card(c, m)


# 🔘 Callbacks
@Client.on_callback_query(filters.regex(f"^{CB_SET_DEST}$"))
async def cb_set_dest(c: Client, q: CallbackQuery):
    uid = q.from_user.id
    await set_waiting_for_channel(uid, True)
    await q.answer("Send me a forwarded post from your channel.", show_alert=False)
    await q.message.reply_text(
        "➡️ <b>Step 1:</b> Forward any post from your <b>Destination Channel</b> here.\n"
        "➡️ <b>Step 2:</b> Make sure the bot is <b>Admin</b> in that channel.\n\n"
        "💡 If forwarding hides channel info, send the <code>@username</code> or invite link instead.",
        quote=True,
    )


@Client.on_callback_query(filters.regex(f"^{CB_CLEAR_DEST}$"))
async def cb_clear_dest(c: Client, q: CallbackQuery):
    uid = q.from_user.id
    await clear_destination_channel(uid)
    await clear_waiting_for_channel(uid)
    await q.answer("Destination cleared.", show_alert=False)
    await _send_dest_card(c, q.message)


@Client.on_callback_query(filters.regex(f"^{CB_HELP_DEST}$"))
async def cb_help_dest(c: Client, q: CallbackQuery):
    await q.answer()
    await q.message.reply_text(
        "❓ <b>How it works</b>\n\n"
        "1) Tap <b>Set Destination Channel</b>.\n"
        "2) Forward any post from your target channel or send @username / invite link.\n"
        "3) Make sure the bot is <b>Admin</b> in that channel.\n"
        "4) After each rename, the bot will also copy the file there.\n\n"
        "🔐 Private channel? Add the bot as admin first.",
    )


# 📥 Handle waiting mode only
@Client.on_message(filters.private & filters.text | filters.private & filters.forwarded)
async def handle_forward_or_text_while_waiting(c: Client, m: Message):
    uid = m.from_user.id
    if not await is_waiting_for_channel(uid):
        return

    channel_id, reason = await _extract_channel_id(c, m)
    if channel_id is None:
        await m.reply_text(
            "⚠️ I couldn't detect a channel.\n\n"
            "• Forward a post from your channel (with info visible),\n"
            "  or send its <code>@username</code> / invite link.\n"
            f"Details: {reason or 'unknown'}"
        )
        return

    ok, why = await _can_post_to_channel(c, channel_id)
    if not ok:
        await m.reply_text(
            "🚫 I don't have permission to post in that channel.\n"
            "Please add me as <b>Admin</b> and try again.\n\n"
            f"Details: {why}"
        )
        return

    await save_destination_channel(uid, channel_id)
    await clear_waiting_for_channel(uid)
    await m.reply_text(f"✅ Destination saved:\n<code>{channel_id}</code>\n\nAll future renamed files will be posted there.")


# 🔎 Extract channel id
async def _extract_channel_id(c: Client, m: Message) -> Tuple[Optional[int], Optional[str]]:
    try:
        if m.forward_from_chat and m.forward_from_chat.type == enums.ChatType.CHANNEL:
            return m.forward_from_chat.id, None
        if m.sender_chat and m.sender_chat.type == enums.ChatType.CHANNEL:
            return m.sender_chat.id, None

        if m.text:
            text = m.text.strip()

            # @username
            at_match = re.search(r"@([A-Za-z0-9_]{5,})", text)
            if at_match:
                chat = await c.get_chat(at_match.group(1))
                if chat and chat.type == enums.ChatType.CHANNEL:
                    return chat.id, None

            # t.me/username OR joinchat/invite links
            link_match = re.search(r"(?:https?://)?t\.me/(?:joinchat/|\+)?([A-Za-z0-9_+\-]{5,})", text)
            if link_match:
                handle = link_match.group(1)
                chat = await c.get_chat(handle)
                if chat and chat.type == enums.ChatType.CHANNEL:
                    return chat.id, None

            # Raw numeric ID
            if text.startswith("-100") and text[4:].isdigit():
                return int(text), None

        return None, "Channel not detected."
    except Exception as e:
        return None, str(e)


# 🔎 Permission check
async def _can_post_to_channel(c: Client, channel_id: int) -> Tuple[bool, str]:
    try:
        me = await c.get_chat_member(channel_id, "me")
        if me.status in (enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR):
            priv = getattr(me, "privileges", None)
            if priv is None or getattr(priv, "can_post_messages", True):
                return True, "ok"
            return False, "Admin but cannot post."
        return False, f"My status is {me.status}, not admin."
    except Exception as e:
        return False, str(e)


# 🚚 Public helper
async def send_to_destination_if_set(c: Client, user_id: int, src_message: Message, caption: Optional[str] = None):
    try:
        dest = await get_destination_channel(user_id)
        if not dest:
            return
        await src_message.copy(chat_id=dest, caption=caption) if caption else await src_message.copy(chat_id=dest)
    except Exception as e:
        try:
            await c.send_message(user_id, f"⚠️ Failed to send to Destination:\n<code>{e}</code>\nEnsure I'm admin there.")
        except Exception:
            pass