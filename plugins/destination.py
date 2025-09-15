from typing import Optional, Tuple
from pyrogram import Client, filters, enums
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import time
import logging

from helper.database import jishubotz

try:
    from config import DESTINATION_PIC_URL
except ImportError:
    DESTINATION_PIC_URL = None

DEST_WAIT_TIMEOUT = 120  # 2 minutes

# Callback keys
CB_SET_DEST = "set_dest_channel"
CB_CLEAR_DEST = "clear_dest_channel"
CB_HELP_DEST = "dest_help"
CB_CANCEL_SET = "cancel_set_dest"

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ================== UI HELPERS ==================
def _dest_kb(current: Optional[int]) -> InlineKeyboardMarkup:
    label = f"📡 Set Destination Channel" if not current else f"📡 Change Destination (now: {current})"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=CB_SET_DEST)],
        [InlineKeyboardButton("🗑️ Clear Destination", callback_data=CB_CLEAR_DEST)],
        [InlineKeyboardButton("❓ How it works", callback_data=CB_HELP_DEST)],
    ])


async def _send_dest_card(c: Client, m: Message):
    uid = m.from_user.id
    current = await jishubotz.get_destination_channel(uid)
    caption = (
        "🧭 <b>Destination Channel</b>\n\n"
        "• Set a channel once, and every renamed file will also be posted there automatically.\n"
        "• Bot must be <b>Admin</b> in that channel with permission to post.\n\n"
        f"<i>Current:</i> <code>{current or 'Not set'}</code>"
    )
    if DESTINATION_PIC_URL:
        await m.reply_photo(DESTINATION_PIC_URL, caption=caption, reply_markup=_dest_kb(current))
    else:
        await m.reply_text(caption, reply_markup=_dest_kb(current))


async def _extract_channel_id(c: Client, m: Message) -> Tuple[Optional[int], Optional[str]]:
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
                return None, "Not a channel"
            except Exception as e:
                return None, str(e)
    return None, "Not a valid channel. Please forward a post or send @username/invite link."


async def _can_post_to_channel(c: Client, channel_id: int) -> Tuple[bool, str]:
    try:
        me = await c.get_chat_member(channel_id, "me")
        if me.status in (enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR):
            priv = getattr(me, "privileges", None)
            if not priv or getattr(priv, "can_post_messages", True):
                return True, "ok"
            return False, "Admin but cannot post messages."
        return False, f"Bot is not an admin (status: {me.status})."
    except Exception as e:
        return False, str(e)


# ================== COMMAND HANDLERS ==================
@Client.on_message(filters.private & filters.command(["setchannel", "setdest"]))
async def cmd_setchannel(c: Client, m: Message):
    await _send_dest_card(c, m)


@Client.on_message(filters.private & filters.command(["cancelsetchannel", "cancelsetdest"]))
async def cmd_cancel_setchannel(c: Client, m: Message):
    uid = m.from_user.id
    await jishubotz.clear_waiting_for_channel(uid)
    await m.reply_text("✅ Cancelled destination setup.")


# ================== CALLBACK HANDLERS ==================
@Client.on_callback_query(filters.regex(f"^{CB_SET_DEST}$"))
async def cb_set_dest(c: Client, q: CallbackQuery):
    uid = q.from_user.id
    await jishubotz.set_waiting_for_channel(uid, True, int(time.time()))
    await q.answer("Send a forwarded post or @username/invite link.", show_alert=False)
    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=CB_CANCEL_SET)]])
    await q.message.reply_text(
        f"➡️ Forward a post from your channel OR send @username/invite link.\n⏳ You have {DEST_WAIT_TIMEOUT//60} min.",
        reply_markup=cancel_kb
    )


@Client.on_callback_query(filters.regex(f"^{CB_CANCEL_SET}$"))
async def cb_cancel_set(c: Client, q: CallbackQuery):
    uid = q.from_user.id
    await jishubotz.clear_waiting_for_channel(uid)
    await q.answer("Setup cancelled.", show_alert=False)
    await q.message.edit_text("❌ Destination setup cancelled.")


@Client.on_callback_query(filters.regex(f"^{CB_CLEAR_DEST}$"))
async def cb_clear_dest(c: Client, q: CallbackQuery):
    uid = q.from_user.id
    await jishubotz.clear_destination_channel(uid)
    await q.answer("Destination cleared.", show_alert=False)
    await _send_dest_card(c, q.message)


@Client.on_callback_query(filters.regex(f"^{CB_HELP_DEST}$"))
async def cb_help_dest(c: Client, q: CallbackQuery):
    await q.answer()
    await q.message.reply_text(
        "❓ <b>How it works</b>\n\n"
        "1) Tap <b>Set Destination Channel</b>\n"
        "2) Forward any post from your channel or send @username/invite link\n"
        "3) Bot must be <b>Admin</b> there\n"
        "4) After each rename, bot copies the file to that channel"
    )


# ================== MESSAGE HANDLER FOR WAITING ==================
@Client.on_message(filters.private & (filters.text | filters.forwarded))
async def handle_forward_or_text_while_waiting(c: Client, m: Message):
    uid = m.from_user.id

    # 🔍 Check waiting state first
    waiting, ts = await jishubotz.is_waiting_for_channel(uid, with_ts=True)
    if not waiting:
        return  # 🚫 Ignore if not waiting → lets other commands run

    # Timeout check
    if ts and (time.time() - ts > DEST_WAIT_TIMEOUT):
        await jishubotz.clear_waiting_for_channel(uid)
        await m.reply_text("⌛ Timeout! Setup cancelled. Use /setchannel again.")
        return

    # Try extracting channel
    channel_id, reason = await _extract_channel_id(c, m)
    if not channel_id:
        await m.reply_text(f"⚠️ Couldn’t detect a channel. Reason: {reason}")
        return

    # Permission check
    ok, why = await _can_post_to_channel(c, channel_id)
    if not ok:
        await m.reply_text(f"🚫 Bot cannot post there.\nReason: {why}")
        return

    # Save destination
    await jishubotz.save_destination_channel(uid, channel_id)
    await jishubotz.clear_waiting_for_channel(uid)
    await m.reply_text(f"✅ Destination channel saved:\n<code>{channel_id}</code>")


# ================== SEND TO DESTINATION ==================
async def send_to_destination_if_set(c: Client, user_id: int, src_message: Message, caption: Optional[str] = None):
    dest = await jishubotz.get_destination_channel(user_id)
    if not dest:
        return
    try:
        if caption:
            await src_message.copy(chat_id=dest, caption=caption)
        else:
            await src_message.copy(chat_id=dest)
    except Exception as e:
        try:
            await c.send_message(user_id, f"⚠️ Failed to send to Destination Channel:\n<code>{e}</code>")
        except Exception:
            pass