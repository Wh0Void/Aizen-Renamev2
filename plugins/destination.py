from typing import Optional, Tuple
from pyrogram import Client, filters, enums
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import time

from helper.database import jishubotz

# Optional picture for destination card
try:
    from config import DESTINATION_PIC_URL
except Exception:
    DESTINATION_PIC_URL = None

# Timeout (in seconds) for waiting channel forward/text
DEST_WAIT_TIMEOUT = 120  # 2 minutes

# Callback constants
CB_SET_DEST = "set_dest_channel"
CB_CLEAR_DEST = "clear_dest_channel"
CB_HELP_DEST = "dest_help"
CB_CANCEL_SET = "cancel_set_dest"


# ============ Inline Keyboard Builder ============ #
def _dest_kb(current: Optional[int]) -> InlineKeyboardMarkup:
    """Builds inline keyboard for destination channel settings."""
    label = f"📡 Set Destination Channel" if not current else f"📡 Change Destination (now: {current})"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=CB_SET_DEST)],
        [InlineKeyboardButton("🗑️ Clear Destination", callback_data=CB_CLEAR_DEST)],
        [InlineKeyboardButton("❓ How it works", callback_data=CB_HELP_DEST)],
    ])


# ============ UI Message ============ #
async def _send_dest_card(c: Client, m: Message):
    """Send destination channel settings card to user."""
    uid = m.from_user.id
    current = await jishubotz.get_destination_channel(uid)
    caption = (
        "🧭 <b>Destination Channel</b>\n\n"
        "• Set a channel once, and every renamed file will also be posted there automatically.\n"
        "• Bot must be <b>Admin</b> in that channel with permission to post.\n\n"
        f"<i>Current:</i> <code>{current or 'Not set'}</code>"
    )
    if DESTINATION_PIC_URL:
        await m.reply_photo(photo=DESTINATION_PIC_URL, caption=caption, reply_markup=_dest_kb(current))
    else:
        await m.reply_text(caption, reply_markup=_dest_kb(current))


# ============ COMMAND HANDLERS ============ #
async def cmd_setchannel(c: Client, m: Message):
    """User runs /setchannel → show destination card"""
    await _send_dest_card(c, m)


async def cmd_cancel_setchannel(c: Client, m: Message):
    """User runs /cancelsetchannel → cancel setup"""
    uid = m.from_user.id
    await jishubotz.clear_waiting_for_channel(uid)
    await m.reply_text("✅ Cancelled destination setup.")


# ============ CALLBACK HANDLERS ============ #
async def cb_set_dest(c: Client, q: CallbackQuery):
    """Triggered when user presses 'Set Destination Channel'"""
    uid = q.from_user.id
    await jishubotz.set_waiting_for_channel(uid, True, int(time.time()))
    await q.answer("Send me a forwarded post from your channel.", show_alert=False)
    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=CB_CANCEL_SET)]])
    await q.message.reply_text(
        "➡️ Forward any post from your <b>Destination Channel</b> here.\n"
        "➡️ Or send @username / invite link.\n"
        f"⏳ You have {DEST_WAIT_TIMEOUT // 60} minutes.",
        reply_markup=cancel_kb
    )


async def cb_cancel_set(c: Client, q: CallbackQuery):
    """Triggered when user presses 'Cancel' while waiting"""
    uid = q.from_user.id
    await jishubotz.clear_waiting_for_channel(uid)
    await q.answer("Setup cancelled.", show_alert=False)
    await q.message.edit_text("❌ Destination setup cancelled.")


async def cb_clear_dest(c: Client, q: CallbackQuery):
    """Triggered when user presses 'Clear Destination'"""
    uid = q.from_user.id
    await jishubotz.clear_destination_channel(uid)
    await jishubotz.clear_waiting_for_channel(uid)
    await q.answer("Destination cleared.", show_alert=False)
    await _send_dest_card(c, q.message)


async def cb_help_dest(c: Client, q: CallbackQuery):
    """Triggered when user presses 'How it works'"""
    await q.answer()
    await q.message.reply_text(
        "❓ <b>How it works</b>\n\n"
        "1) Tap <b>Set Destination Channel</b>.\n"
        "2) Forward any post from your target channel or send @username / invite link.\n"
        "3) Make sure the bot is <b>Admin</b> in that channel.\n"
        "4) After each rename, the bot will also copy the file to that channel.\n\n"
        f"⏳ Setup auto-cancels in {DEST_WAIT_TIMEOUT // 60} minutes."
    )


# ============ FORWARD / TEXT HANDLER WHILE WAITING ============ #
async def handle_forward_or_text_while_waiting(c: Client, m: Message):
    """Handles forwarded post or text while user is setting destination channel."""
    uid = m.from_user.id
    waiting, ts = await jishubotz.is_waiting_for_channel(uid, with_ts=True)
    if not waiting:
        return

    if ts and (time.time() - ts > DEST_WAIT_TIMEOUT):
        await jishubotz.clear_waiting_for_channel(uid)
        return await m.reply_text("⌛ Timeout! Setup cancelled. Use /setchannel again.")

    if m.text and m.text.startswith("/"):
        return

    channel_id, reason = await _extract_channel_id(c, m)
    if not channel_id:
        return await m.reply_text(f"⚠️ Couldn’t detect a channel. Reason: {reason or 'unknown'}")

    ok, why = await _can_post_to_channel(c, channel_id)
    if not ok:
        return await m.reply_text(f"🚫 Bot lacks permission in that channel.\nReason: {why}")

    await jishubotz.save_destination_channel(uid, channel_id)
    await jishubotz.clear_waiting_for_channel(uid)
    await m.reply_text(f"✅ Destination channel saved:\n<code>{channel_id}</code>")


# ============ HELPER FUNCTIONS ============ #
async def _extract_channel_id(c: Client, m: Message) -> Tuple[Optional[int], Optional[str]]:
    """Extract channel id from forwarded message or text"""
    try:
        if m.forward_from_chat and m.forward_from_chat.type == enums.ChatType.CHANNEL:
            return m.forward_from_chat.id, None
        if m.sender_chat and m.sender_chat.type == enums.ChatType.CHANNEL:
            return m.sender_chat.id, None
        if m.text:
            text = m.text.strip()
            if text.startswith("-100") and text[4:].isdigit():
                return int(text), None
            if text.startswith("@"):
                try:
                    chat = await c.get_chat(text)
                    if chat.type == enums.ChatType.CHANNEL:
                        return chat.id, None
                except Exception as e:
                    return None, str(e)
            if "t.me" in text:
                try:
                    chat = await c.get_chat(text.split("/")[-1])
                    if chat.type == enums.ChatType.CHANNEL:
                        return chat.id, None
                except Exception as e:
                    return None, str(e)
        return None, "Not a valid channel."
    except Exception as e:
        return None, str(e)


async def _can_post_to_channel(c: Client, channel_id: int) -> Tuple[bool, str]:
    """Check if bot can post to channel"""
    try:
        me = await c.get_chat_member(channel_id, "me")
        if me.status in (enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR):
            priv = getattr(me, "privileges", None)
            if not priv or getattr(priv, "can_post_messages", True):
                return True, "ok"
            return False, "Admin but cannot post."
        return False, f"My status is {me.status}"
    except Exception as e:
        return False, str(e)


async def send_to_destination_if_set(c: Client, user_id: int, src_message: Message, caption: Optional[str] = None):
    """Copy renamed file to destination channel if user has set one"""
    try:
        dest = await jishubotz.get_destination_channel(user_id)
        if not dest:
            return
        if caption:
            await src_message.copy(chat_id=dest, caption=caption)
        else:
            await src_message.copy(chat_id=dest)
    except Exception as e:
        try:
            await c.send_message(user_id, f"⚠️ Failed to send to Destination Channel:\n<code>{e}</code>")
        except Exception:
            pass


# ============ INIT FUNCTION ============ #
def init(bot: Client):
    """Attach all handlers to the bot"""

    # Commands
    bot.add_handler(filters.command(["setchannel", "setdest"]) & filters.private, cmd_setchannel)
    bot.add_handler(filters.command(["cancelsetchannel", "cancelsetdest"]) & filters.private, cmd_cancel_setchannel)

    # Callback buttons
    bot.add_handler(filters.callback_data(CB_SET_DEST), cb_set_dest)
    bot.add_handler(filters.callback_data(CB_CANCEL_SET), cb_cancel_set)
    bot.add_handler(filters.callback_data(CB_CLEAR_DEST), cb_clear_dest)
    bot.add_handler(filters.callback_data(CB_HELP_DEST), cb_help_dest)

    # Forwarded post / text (when waiting for channel)
    bot.add_handler(filters.private & (filters.text | filters.forwarded), handle_forward_or_text_while_waiting)