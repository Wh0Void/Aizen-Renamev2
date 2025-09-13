from typing import Optional, Tuple
from pyrogram import Client, filters, enums
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import re
import time
import logging

from helper.database import jishubotz

try:
    from config import DESTINATION_PIC_URL
except ImportError:
    DESTINATION_PIC_URL = None

DEST_WAIT_TIMEOUT = 120  # 2 minutes

CB_SET_DEST = "set_dest_channel"
CB_CLEAR_DEST = "clear_dest_channel"
CB_HELP_DEST = "dest_help"
CB_CANCEL_SET = "cancel_set_dest"

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _dest_kb(current: Optional[int]) -> InlineKeyboardMarkup:
    label = f"📡 Set Destination Channel" if not current else f"📡 Change Destination (now: {current})"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=CB_SET_DEST)],
        [InlineKeyboardButton("🗑️ Clear Destination", callback_data=CB_CLEAR_DEST)],
        [InlineKeyboardButton("❓ How it works", callback_data=CB_HELP_DEST)],
    ])

async def _send_dest_card(c: Client, m: Message):
    try:
        uid = m.from_user.id
        current = await jishubotz.get_destination_channel(uid)
        caption = (
            "🧭 <b>Destination Channel</b>\n\n"
            "• Set a channel once, and every renamed file will also be posted there automatically.\n"
            "• Bot must be <b>Admin</b> in that channel with permission to post.\n\n"
            f"<i>Current:</i> <code>{current or 'Not set'}</code>"
        )
        logger.info(f"Sending destination card to user {uid}, current channel: {current}")
        if DESTINATION_PIC_URL:
            await m.reply_photo(photo=DESTINATION_PIC_URL, caption=caption, reply_markup=_dest_kb(current))
        else:
            await m.reply_text(caption, reply_markup=_dest_kb(current))
    except Exception as e:
        logger.error(f"Error in _send_dest_card for user {uid}: {e}")
        await m.reply_text("⚠️ An error occurred while displaying the destination card.")

async def _extract_channel_id(c: Client, m: Message) -> Tuple[Optional[int], Optional[str]]:
    try:
        if m.forward_from_chat and m.forward_from_chat.type == enums.ChatType.CHANNEL:
            logger.info(f"Extracted channel ID {m.forward_from_chat.id} from forwarded message")
            return m.forward_from_chat.id, None
        if m.sender_chat and m.sender_chat.type == enums.ChatType.CHANNEL:
            logger.info(f"Extracted channel ID {m.sender_chat.id} from sender chat")
            return m.sender_chat.id, None
        if m.text:
            text = m.text.strip()
            if text.startswith("-100") and text[4:].isdigit():
                logger.info(f"Extracted channel ID {text} from text")
                return int(text), None
            if text.startswith("@"):
                try:
                    chat = await c.get_chat(text)
                    if chat.type == enums.ChatType.CHANNEL:
                        logger.info(f"Extracted channel ID {chat.id} from username {text}")
                        return chat.id, None
                    return None, "Not a channel"
                except Exception as e:
                    logger.error(f"Error resolving username {text}: {e}")
                    return None, str(e)
            if "t.me" in text:
                try:
                    chat = await c.get_chat(text.split("/")[-1])
                    if chat.type == enums.ChatType.CHANNEL:
                        logger.info(f"Extracted channel ID {chat.id} from invite link {text}")
                        return chat.id, None
                    return None, "Not a channel"
                except Exception as e:
                    logger.error(f"Error resolving invite link {text}: {e}")
                    return None, str(e)
        return None, "Not a valid channel. Please forward a post or send @username/invite link."
    except Exception as e:
        logger.error(f"Error in _extract_channel_id: {e}")
        return None, str(e)

async def _can_post_to_channel(c: Client, channel_id: int) -> Tuple[bool, str]:
    try:
        me = await c.get_chat_member(channel_id, "me")
        if me.status in (enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR):
            priv = getattr(me, "privileges", None)
            if not priv or getattr(priv, "can_post_messages", True):
                logger.info(f"Bot can post to channel {channel_id}")
                return True, "ok"
            logger.warning(f"Bot is admin in {channel_id} but cannot post messages")
            return False, "Admin but cannot post messages."
        logger.warning(f"Bot is not admin in {channel_id}, status: {me.status}")
        return False, f"Bot is not an admin (status: {me.status})."
    except Exception as e:
        logger.error(f"Error in _can_post_to_channel for channel {channel_id}: {e}")
        return False, str(e)

# ================== HANDLER FUNCTIONS ================== #
async def cmd_setchannel(c: Client, m: Message):
    logger.info(f"Received /setchannel command from user {m.from_user.id}")
    await _send_dest_card(c, m)

async def cmd_cancel_setchannel(c: Client, m: Message):
    try:
        uid = m.from_user.id
        logger.info(f"Received /cancelsetchannel command from user {uid}")
        await jishubotz.clear_waiting_for_channel(uid)
        await m.reply_text("✅ Cancelled destination setup.")
    except Exception as e:
        logger.error(f"Error in cmd_cancel_setchannel for user {uid}: {e}")
        await m.reply_text("⚠️ An error occurred while cancelling setup.")

async def cb_set_dest(c: Client, q: CallbackQuery):
    try:
        uid = q.from_user.id
        logger.info(f"Callback query {CB_SET_DEST} received from user {uid}, data: {q.data}")
        await jishubotz.set_waiting_for_channel(uid, True, int(time.time()))
        await q.answer("Send a forwarded post from your channel or @username/invite link.", show_alert=False)
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=CB_CANCEL_SET)]])
        await q.message.reply_text(
            "➡️ Forward any post from your <b>Destination Channel</b> here.\n"
            "➡️ Or send @username / invite link.\n"
            f"⏳ You have {DEST_WAIT_TIMEOUT // 60} minutes.",
            reply_markup=cancel_kb
        )
    except Exception as e:
        logger.error(f"Error in cb_set_dest for user {uid}: {e}")
        await q.message.reply_text("⚠️ An error occurred during setup.")

async def cb_cancel_set(c: Client, q: CallbackQuery):
    try:
        uid = q.from_user.id
        logger.info(f"Callback query {CB_CANCEL_SET} received from user {uid}, data: {q.data}")
        await jishubotz.clear_waiting_for_channel(uid)
        await q.answer("Setup cancelled.", show_alert=False)
        await q.message.edit_text("❌ Destination setup cancelled.")
    except Exception as e:
        logger.error(f"Error in cb_cancel_set for user {uid}: {e}")
        await q.message.edit_text("⚠️ An error occurred while cancelling setup.")

async def cb_clear_dest(c: Client, q: CallbackQuery):
    try:
        uid = q.from_user.id
        logger.info(f"Callback query {CB_CLEAR_DEST} received from user {uid}, data: {q.data}")
        await jishubotz.clear_destination_channel(uid)
        await jishubotz.clear_waiting_for_channel(uid)
        await q.answer("Destination cleared.", show_alert=False)
        await _send_dest_card(c, q.message)
    except Exception as e:
        logger.error(f"Error in cb_clear_dest for user {uid}: {e}")
        await q.message.edit_text("⚠️ An error occurred while clearing destination.")

async def cb_help_dest(c: Client, q: CallbackQuery):
    try:
        uid = q.from_user.id
        logger.info(f"Callback query {CB_HELP_DEST} received from user {uid}, data: {q.data}")
        await q.answer()
        await q.message.reply_text(
            "❓ <b>How it works</b>\n\n"
            "1) Tap <b>Set Destination Channel</b>.\n"
            "2) Forward any post from your target channel or send @username / invite link.\n"
            "3) Make sure the bot is <b>Admin</b> in that channel.\n"
            "4) After each rename, the bot will also copy the file to that channel.\n\n"
            f"⏳ Setup auto-cancels in {DEST_WAIT_TIMEOUT // 60} minutes."
        )
    except Exception as e:
        logger.error(f"Error in cb_help_dest for user {uid}: {e}")
        await q.message.reply_text("⚠️ An error occurred while displaying help.")

async def handle_forward_or_text_while_waiting(c: Client, m: Message):
    try:
        uid = m.from_user.id
        waiting, ts = await jishubotz.is_waiting_for_channel(uid, with_ts=True)
        logger.info(f"Handling message for user {uid}, waiting: {waiting}, timestamp: {ts}")
        if not waiting:
            logger.debug(f"User {uid} not waiting for channel input, ignoring message")
            return  # Silently ignore if not waiting

        if ts and (time.time() - ts > DEST_WAIT_TIMEOUT):
            logger.info(f"Timeout for user {uid}, clearing waiting state")
            await jishubotz.clear_waiting_for_channel(uid)
            await m.reply_text("⌛ Timeout! Setup cancelled. Use /setchannel again.")
            return

        if m.text and m.text.startswith("/"):
            logger.debug(f"Ignoring command message from user {uid}: {m.text}")
            return  # Ignore commands

        channel_id, reason = await _extract_channel_id(c, m)
        if not channel_id:
            logger.warning(f"Could not detect channel for user {uid}: {reason}")
            await m.reply_text(f"⚠️ Couldn’t detect a channel. Reason: {reason or 'unknown'}")
            return

        ok, why = await _can_post_to_channel(c, channel_id)
        if not ok:
            logger.warning(f"Bot lacks permission in channel {channel_id} for user {uid}: {why}")
            await m.reply_text(f"🚫 Bot lacks permission in that channel.\nReason: {why}")
            return

        await jishubotz.save_destination_channel(uid, channel_id)
        await jishubotz.clear_waiting_for_channel(uid)
        logger.info(f"Destination channel {channel_id} saved for user {uid}")
        await m.reply_text(f"✅ Destination channel saved:\n<code>{channel_id}</code>")
    except Exception as e:
        logger.error(f"Error in handle_forward_or_text_while_waiting for user {uid}: {e}")
        await m.reply_text("⚠️ An error occurred while processing the channel.")

async def send_to_destination_if_set(c: Client, user_id: int, src_message: Message, caption: Optional[str] = None):
    try:
        dest = await jishubotz.get_destination_channel(user_id)
        if not dest:
            logger.debug(f"No destination channel set for user {user_id}")
            return
        logger.info(f"Copying message to destination channel {dest} for user {user_id}")
        if caption:
            await src_message.copy(chat_id=dest, caption=caption)
        else:
            await src_message.copy(chat_id=dest)
    except Exception as e:
        logger.error(f"Error in send_to_destination_if_set for user {user_id}: {e}")
        try:
            await c.send_message(user_id, f"⚠️ Failed to send to Destination Channel:\n<code>{e}</code>")
        except Exception:
            pass

# ================== INIT FUNCTION ================== #
def init(bot: Client):
    logger.info("Registering destination.py handlers")
    @bot.on_message(filters.command(["setchannel", "setdest"]) & filters.private)
    async def _cmd_setchannel(client, message):
        logger.info(f"Registering /setchannel handler for user {message.from_user.id}")
        await cmd_setchannel(client, message)

    @bot.on_message(filters.command(["cancelsetchannel", "cancelsetdest"]) & filters.private)
    async def _cmd_cancel_setchannel(client, message):
        logger.info(f"Registering /cancelsetchannel handler for user {message.from_user.id}")
        await cmd_cancel_setchannel(client, message)

    @bot.on_callback_query(filters.regex(f"^{CB_SET_DEST}$"))
    async def _cb_set_dest(client, query):
        logger.info(f"Callback handler triggered for {CB_SET_DEST}, data: {query.data}, user: {query.from_user.id}")
        await cb_set_dest(client, query)

    @bot.on_callback_query(filters.regex(f"^{CB_CANCEL_SET}$"))
    async def _cb_cancel_set(client, query):
        logger.info(f"Callback handler triggered for {CB_CANCEL_SET}, data: {query.data}, user: {query.from_user.id}")
        await cb_cancel_set(client, query)

    @bot.on_callback_query(filters.regex(f"^{CB_CLEAR_DEST}$"))
    async def _cb_clear_dest(client, query):
        logger.info(f"Callback handler triggered for {CB_CLEAR_DEST}, data: {query.data}, user: {query.from_user.id}")
        await cb_clear_dest(client, query)

    @bot.on_callback_query(filters.regex(f"^{CB_HELP_DEST}$"))
    async def _cb_help_dest(client, query):
        logger.info(f"Callback handler triggered for {CB_HELP_DEST}, data: {query.data}, user: {query.from_user.id}")
        await cb_help_dest(client, query)

    @bot.on_message(filters.private & (filters.text | filters.forwarded) & ~filters.command([]))
    async def _handle_forward_or_text(client, message):
        uid = message.from_user.id
        waiting, _ = await jishubotz.is_waiting_for_channel(uid, with_ts=True)
        logger.debug(f"Checking message for user {uid}, waiting: {waiting}")
        if waiting:
            await handle_forward_or_text_while_waiting(client, message)