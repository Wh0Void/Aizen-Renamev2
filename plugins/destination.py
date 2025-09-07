from typing import Optional, Tuple
from pyrogram import Client, filters, enums
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import time

from helper.database import jishubotz

try:
    from config import DESTINATION_PIC_URL
except Exception:
    DESTINATION_PIC_URL = None

DEST_WAIT_TIMEOUT = 120  # 2 minutes

CB_SET_DEST = "set_dest_channel"
CB_CLEAR_DEST = "clear_dest_channel"
CB_HELP_DEST = "dest_help"
CB_CANCEL_SET = "cancel_set_dest"


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
        await m.reply_photo(photo=DESTINATION_PIC_URL, caption=caption, reply_markup=_dest_kb(current))
    else:
        await m.reply_text(caption, reply_markup=_dest_kb(current))


# ================== HANDLER FUNCTIONS ================== #
async def cmd_setchannel(client: Client, message: Message):
    await _send_dest_card(client, message)


async def cmd_cancel_setchannel(client: Client, message: Message):
    uid = message.from_user.id
    await jishubotz.clear_waiting_for_channel(uid)
    await message.reply_text("✅ Cancelled destination setup.")


async def cb_set_dest(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    await jishubotz.set_waiting_for_channel(uid, True, int(time.time()))
    await query.answer("Send me a forwarded post from your channel.", show_alert=False)
    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=CB_CANCEL_SET)]])
    await query.message.reply_text(
        "➡️ Forward any post from your <b>Destination Channel</b> here.\n"
        "➡️ Or send @username / invite link.\n"
        f"⏳ You have {DEST_WAIT_TIMEOUT // 60} minutes.",
        reply_markup=cancel_kb
    )


async def cb_cancel_set(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    await jishubotz.clear_waiting_for_channel(uid)
    await query.answer("Setup cancelled.", show_alert=False)
    await query.message.edit_text("❌ Destination setup cancelled.")


async def cb_clear_dest(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    await jishubotz.clear_destination_channel(uid)
    await jishubotz.clear_waiting_for_channel(uid)
    await query.answer("Destination cleared.", show_alert=False)
    await _send_dest_card(client, query.message)


async def cb_help_dest(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.reply_text(
        "❓ <b>How it works</b>\n\n"
        "1) Tap <b>Set Destination Channel</b>.\n"
        "2) Forward any post from your target channel or send @username / invite link.\n"
        "3) Make sure the bot is <b>Admin</b> in that channel.\n"
        "4) After each rename, the bot will also copy the file to that channel.\n\n"
        f"⏳ Setup auto-cancels in {DEST_WAIT_TIMEOUT // 60} minutes."
    )


async def handle_forward_or_text_while_waiting(client: Client, message: Message):
    uid = message.from_user.id
    waiting, ts = await jishubotz.is_waiting_for_channel(uid, with_ts=True)
    if not waiting:
        return

    if ts and (time.time() - ts > DEST_WAIT_TIMEOUT):
        await jishubotz.clear_waiting_for_channel(uid)
        return await message.reply_text("⌛ Timeout! Setup cancelled. Use /setchannel again.")

    if message.text and message.text.startswith("/"):
        return

    channel_id, reason = await _extract_channel_id(client, message)
    if not channel_id:
        return await message.reply_text(f"⚠️ Couldn’t detect a channel. Reason: {reason or 'unknown'}")

    ok, why = await _can_post_to_channel(client, channel_id)
    if not ok:
        return await message.reply_text(f"🚫 Bot lacks permission in that channel.\nReason: {why}")

    await jishubotz.save_destination_channel(uid, channel_id)
    await jishubotz.clear_waiting_for_channel(uid)
    await message.reply_text(f"✅ Destination channel saved:\n<code>{channel_id}</code>")


# ================== INIT FUNCTION ================== #
def init(bot: Client):
    bot.add_handler(filters.command(["setchannel", "setdest"])(cmd_setchannel))
    bot.add_handler(filters.command(["cancelsetchannel", "cancelsetdest"])(cmd_cancel_setchannel))
    bot.add_handler(filters.regex(f"^{CB_SET_DEST}$")(cb_set_dest))
    bot.add_handler(filters.regex(f"^{CB_CANCEL_SET}$")(cb_cancel_set))
    bot.add_handler(filters.regex(f"^{CB_CLEAR_DEST}$")(cb_clear_dest))
    bot.add_handler(filters.regex(f"^{CB_HELP_DEST}$")(cb_help_dest))
    bot.add_handler((filters.private & (filters.text | filters.forwarded))(handle_forward_or_text_while_waiting))