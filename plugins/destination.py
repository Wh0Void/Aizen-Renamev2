# plugins/destination.py
# Destination Channel feature — uses helper.database.jishubotz instance

from typing import Optional, Tuple
from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
import re

# Import the DB instance (your helper/database.py creates `jishubotz = Database(...)`)
from helper.database import jishubotz

# Optional banner image for the settings card (set DESTINATION_PIC_URL in config.py)
try:
    from config import DESTINATION_PIC_URL
except Exception:
    DESTINATION_PIC_URL = None

# Callback IDs
CB_SET_DEST = "set_dest_channel"
CB_CLEAR_DEST = "clear_dest_channel"
CB_HELP_DEST = "dest_help"


def _dest_kb(current: Optional[int]) -> InlineKeyboardMarkup:
    label = f"📡 Set Destination Channel" if not current else f"📡 Change Destination (now: {current})"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(label, callback_data=CB_SET_DEST)],
            [InlineKeyboardButton("🗑️ Clear Destination", callback_data=CB_CLEAR_DEST)],
            [InlineKeyboardButton("❓ How it works", callback_data=CB_HELP_DEST)],
        ]
    )


async def _send_dest_card(c: Client, m: Message) -> None:
    uid = m.from_user.id
    current = await jishubotz.get_destination_channel(uid)
    if current:
        caption = (
            "🧭 <b>Destination Channel</b>\n\n"
            "• Set a channel once, and every renamed file will also be posted there automatically.\n"
            "• Bot must be <b>Admin</b> in that channel with permission to post.\n\n"
            f"<i>Current:</i> <code>{current}</code>"
        )
    else:
        caption = (
            "🧭 <b>Destination Channel</b>\n\n"
            "• Set a channel once, and every renamed file will also be posted there automatically.\n"
            "• Bot must be <b>Admin</b> in that channel with permission to post.\n\n"
            "<i>Current:</i> <code>Not set</code>"
        )

    if DESTINATION_PIC_URL:
        await m.reply_photo(photo=DESTINATION_PIC_URL, caption=caption, reply_markup=_dest_kb(current))
    else:
        await m.reply_text(caption, reply_markup=_dest_kb(current))


# /setchannel or /setdest opens the card
@Client.on_message(filters.command(["setchannel", "setdest"]) & filters.private)
async def cmd_setchannel(c: Client, m: Message):
    await _send_dest_card(c, m)


# User clicked "Set Destination Channel"
@Client.on_callback_query(filters.regex(f"^{CB_SET_DEST}$"))
async def cb_set_dest(c: Client, q: CallbackQuery):
    uid = q.from_user.id
    await jishubotz.set_waiting_for_channel(uid, True)
    await q.answer("Send me a forwarded post from your channel.", show_alert=False)
    await q.message.reply_text(
        "➡️ <b>Step 1:</b> Forward any post from your <b>Destination Channel</b> here.\n"
        "➡️ <b>Step 2:</b> Make sure the bot is <b>Admin</b> in that channel.\n\n"
        "💡 Tip: If forwarding hides channel info (anonymous forward), send the <code>@username</code> "
        "or an invite link of the channel instead.",
        quote=True,
    )


@Client.on_callback_query(filters.regex(f"^{CB_CLEAR_DEST}$"))
async def cb_clear_dest(c: Client, q: CallbackQuery):
    uid = q.from_user.id
    await jishubotz.clear_destination_channel(uid)
    await jishubotz.clear_waiting_for_channel(uid)
    await q.answer("Destination cleared.", show_alert=False)
    await _send_dest_card(c, q.message)


@Client.on_callback_query(filters.regex(f"^{CB_HELP_DEST}$"))
async def cb_help_dest(c: Client, q: CallbackQuery):
    await q.answer()
    await q.message.reply_text(
        "❓ <b>How it works</b>\n\n"
        "1) Tap <b>Set Destination Channel</b>.\n"
        "2) Forward any post from your target channel to the bot here, or send its @username / invite link.\n"
        "3) Make sure the bot is <b>Admin</b> in that channel with permission to post.\n"
        "4) After each rename, the bot will also copy the file to that channel.\n\n"
        "🔐 Private channel? Add the bot as admin first.",
    )


# Only handle forwarded/text messages when the user is in 'waiting' state
@Client.on_message(filters.private & (filters.text | filters.forwarded))
async def handle_forward_or_text_while_waiting(c: Client, m: Message):
    uid = m.from_user.id
    if not await jishubotz.is_waiting_for_channel(uid):
        return  # not setting right now

    channel_id, reason = await _extract_channel_id(c, m)
    if channel_id is None:
        # keep waiting state — user can try again or press clear
        await m.reply_text(
            "⚠️ I couldn't detect a channel from that.\n\n"
            "• Please forward a post from your channel (with channel info visible),\n"
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

    await jishubotz.save_destination_channel(uid, channel_id)
    await jishubotz.clear_waiting_for_channel(uid)
    await m.reply_text(
        f"✅ Destination channel saved:\n<code>{channel_id}</code>\n\n"
        "All future renamed files will also be posted there."
    )


async def _extract_channel_id(c: Client, m: Message) -> Tuple[Optional[int], Optional[str]]:
    """
    Try different ways to find a channel ID:
      - forwarded message (forward_from_chat)
      - sender_chat
      - @username or t.me/username or t.me/+invite
      - raw numeric -100... id
    """
    try:
        if getattr(m, "forward_from_chat", None) and m.forward_from_chat.type == enums.ChatType.CHANNEL:
            return m.forward_from_chat.id, None

        if getattr(m, "sender_chat", None) and m.sender_chat.type == enums.ChatType.CHANNEL:
            return m.sender_chat.id, None

        if m.text:
            text = m.text.strip()

            # @username
            at_match = re.search(r"@([A-Za-z0-9_]{5,})", text)
            if at_match:
                try:
                    chat = await c.get_chat(at_match.group(1))
                    if chat and chat.type == enums.ChatType.CHANNEL:
                        return chat.id, None
                except Exception as e:
                    return None, f"Cannot resolve username: {e}"

            # t.me/username OR t.me/+invite OR t.me/joinchat/xxxx
            link_match = re.search(r"(?:https?://)?t\.me/(?:joinchat/|\+)?([A-Za-z0-9_+\-]{5,})", text)
            if link_match:
                handle = link_match.group(1)
                try:
                    chat = await c.get_chat(handle)
                    if chat and chat.type == enums.ChatType.CHANNEL:
                        return chat.id, None
                except Exception as e:
                    return None, f"Cannot resolve link: {e}"

            # Raw numeric ID like -1001234567890
            if text.startswith("-100") and text[4:].isdigit():
                return int(text), None

        return None, "Channel not detected."
    except Exception as e:
        return None, str(e)


async def _can_post_to_channel(c: Client, channel_id: int) -> Tuple[bool, str]:
    try:
        me = await c.get_chat_member(channel_id, "me")
        if me.status in (enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR):
            priv = getattr(me, "privileges", None)
            if priv is None or getattr(priv, "can_post_messages", True):
                return True, "ok"
            return False, "Admin but cannot post messages."
        return False, f"My status is {me.status}, not admin."
    except Exception as e:
        return False, str(e)


# Public helper for rename.py to call
async def send_to_destination_if_set(c: Client, user_id: int, src_message: Message, caption: Optional[str] = None):
    try:
        dest = await jishubotz.get_destination_channel(user_id)
        if not dest:
            return
        if caption is not None:
            await src_message.copy(chat_id=dest, caption=caption)
        else:
            await src_message.copy(chat_id=dest)
    except Exception as e:
        try:
            await c.send_message(
                user_id,
                f"⚠️ Failed to send to Destination Channel:\n<code>{e}</code>\nPlease ensure I'm admin in that channel."
            )
        except Exception:
            pass