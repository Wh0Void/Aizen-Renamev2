# bot/destination.py
# ✨ Destination Channel feature (Set once → every renamed file is copied to that channel)
# Works with Pyrofork/Pyrogram. Add the DB helpers shown in the guide below.

from typing import Optional, Tuple
from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
import re

# 🧠 Import your DB helper functions (you'll add these to database.py)
from helper.database import (
    save_destination_channel,
    get_destination_channel,
    clear_destination_channel,
    set_waiting_for_channel,
    is_waiting_for_channel,
    clear_waiting_for_channel,
)

# 🔧 Optional banner image for the settings card
# You can set DESTINATION_PIC_URL in config.py (string URL). Falls back to None if missing.
try:
    from config import DESTINATION_PIC_URL  # e.g. "https://graph.org/file/your-image.jpg"
except Exception:
    DESTINATION_PIC_URL = None

# 🔖 Callback IDs (keep them stable)
CB_SET_DEST = "set_dest_channel"
CB_CLEAR_DEST = "clear_dest_channel"
CB_HELP_DEST = "dest_help"

# 🧩 UI: Inline keyboard for the Destination settings card
def _dest_kb(current: Optional[int]) -> InlineKeyboardMarkup:
    label = f"📡 Set Destination Channel" if not current else f"📡 Change Destination (now: {current})"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(label, callback_data=CB_SET_DEST)],
            [InlineKeyboardButton("🗑️ Clear Destination", callback_data=CB_CLEAR_DEST)],
            [InlineKeyboardButton("❓ How it works", callback_data=CB_HELP_DEST)],
        ]
    )


# 🖼️ Show Destination Settings card
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
        await m.reply_photo(
            photo=DESTINATION_PIC_URL,
            caption=caption,
            reply_markup=_dest_kb(current),
        )
    else:
        await m.reply_text(caption, reply_markup=_dest_kb(current))


# 🔘 /setchannel command (opens the card)
@Client.on_message(filters.command(["setchannel", "setdest"]) & filters.private)
async def cmd_setchannel(c: Client, m: Message):
    await _send_dest_card(c, m)


# 🔘 Settings panel may also call this module via callback
@Client.on_callback_query(filters.regex(f"^{CB_SET_DEST}$"))
async def cb_set_dest(c: Client, q: CallbackQuery):
    uid = q.from_user.id
    await set_waiting_for_channel(uid, True)
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
    await clear_destination_channel(uid)
    await clear_waiting_for_channel(uid)
    await q.answer("Destination cleared.", show_alert=False)
    await q.message.reply_text("🗑️ Destination channel cleared.")


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


# 📥 Capture forwarded posts (when we're in 'waiting' mode)
@Client.on_message(filters.private & filters.incoming)
async def handle_forward_or_text_while_waiting(c: Client, m: Message):
    uid = m.from_user.id
    if not await is_waiting_for_channel(uid):
        return  # not in set mode

    # Try to extract channel ID from message
    channel_id, reason = await _extract_channel_id(c, m)
    if channel_id is None:
        await m.reply_text(
            "⚠️ I couldn't detect a channel from that.\n\n"
            "• Please forward a post from your channel (with channel info visible),\n"
            "  or send its <code>@username</code> / invite link.\n"
            f"Details: {reason or 'unknown'}"
        )
        return

    # Validate bot permissions in that channel
    ok, why = await _can_post_to_channel(c, channel_id)
    if not ok:
        await m.reply_text(
            "🚫 I don't have permission to post in that channel.\n"
            "Please add me as <b>Admin</b> and try again.\n\n"
            f"Details: {why}"
        )
        return

    # Save to DB
    await save_destination_channel(uid, channel_id)
    await clear_waiting_for_channel(uid)
    await m.reply_text(
        f"✅ Destination channel saved:\n<code>{channel_id}</code>\n\n"
        "All future renamed files will also be posted there."
    )


# 🔎 Helpers
async def _extract_channel_id(c: Client, m: Message) -> Tuple[Optional[int], Optional[str]]:
    """
    Try different ways to find a channel ID:
    1) Forwarded message: m.forward_from_chat (channel)
    2) Sender as channel: m.sender_chat (rare but possible)
    3) Text containing @username or t.me link
    Returns (channel_id, failure_reason)
    """
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
                username = at_match.group(1)
                chat = await c.get_chat(username)
                if chat and chat.type == enums.ChatType.CHANNEL:
                    return chat.id, None

            # t.me/username or joinchat invite
            link_match = re.search(r"(https?://)?t\.me/(joinchat/)?([A-Za-z0-9_+\-]{5,})", text)
            if link_match:
                handle = link_match.group(3)
                try:
                    chat = await c.get_chat(handle)
                    if chat and chat.type == enums.ChatType.CHANNEL:
                        return chat.id, None
                except Exception as e:
                    return None, f"Cannot resolve link: {e}"

            # Raw numeric ID
            if text.startswith("-100") and text[4:].isdigit():
                return int(text), None

        return None, "Channel not detected."
    except Exception as e:
        return None, str(e)


async def _can_post_to_channel(c: Client, channel_id: int) -> Tuple[bool, str]:
    """Check whether the bot can post in the given channel."""
    try:
        me = await c.get_chat_member(channel_id, "me")
        # Owner or Admin allowed
        if me.status in (enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR):
            # In Pyrogram v2+, admin privileges appear in me.privileges
            priv = getattr(me, "privileges", None)
            if priv is None:
                # Old forks may not expose privileges; assume OK when admin.
                return True, "ok"
            # For channels, can_post_messages should be True (if present)
            can_post = getattr(priv, "can_post_messages", True)
            if can_post:
                return True, "ok"
            return False, "Admin but cannot post messages."
        return False, f"My status is {me.status}, not admin."
    except Exception as e:
        return False, str(e)


# 🚚 Public helper for other modules (rename.py) to use:
# Call this after you send the renamed file to the user. It will copy the same message to the destination channel if set.
async def send_to_destination_if_set(c: Client, user_id: int, src_message: Message, caption: Optional[str] = None):
    try:
        dest = await get_destination_channel(user_id)
        if not dest:
            return

        # Try to copy the message (preserves media). Use provided caption override if any.
        if caption is not None:
            await src_message.copy(chat_id=dest, caption=caption)
        else:
            await src_message.copy(chat_id=dest)
    except Exception as e:
        # Swallow errors but you can log it if you have a logger available
        try:
            await c.send_message(
                user_id,
                f"⚠️ Failed to send to Destination Channel:\n<code>{e}</code>\n"
                f"Please ensure I'm admin in that channel."
            )
        except Exception:
            pass