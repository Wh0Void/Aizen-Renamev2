import asyncio
import time
from typing import Optional, Tuple
from pyrogram import Client, filters, enums
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from helper.database import Mythicbotz

try:
    from wzgram.errors import ListenerTimeout
except ImportError:
    try:
        from pyrogram.errors import ListenerTimeout
    except ImportError:
        ListenerTimeout = asyncio.TimeoutError

DEST_WAIT_TIMEOUT = 120  # 2 minutes

CB_SET_DEST = "set_dest_channel"
CB_CLEAR_DEST = "clear_dest_channel"
CB_HELP_DEST = "dest_help"
CB_CANCEL_SET = "cancel_set_dest"


def _dest_kb(current: Optional[int]) -> InlineKeyboardMarkup:
    label = "📡 sᴇᴛ ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ᴄʜᴀɴɴᴇʟ" if not current else f"📡 ᴄʜᴀɴɢᴇ ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ({current})"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(label, callback_data=CB_SET_DEST)],
            [InlineKeyboardButton("🗑️ ᴄʟᴇᴀʀ ᴅᴇsᴛɪɴᴀᴛɪᴏɴ", callback_data=CB_CLEAR_DEST)],
            [InlineKeyboardButton("❓ ʜᴏᴡ ɪᴛ ᴡᴏʀᴋs", callback_data=CB_HELP_DEST)],
        ]
    )


async def _send_dest_card(c: Client, m: Message, user_id: Optional[int] = None):
    uid = user_id or (m.from_user.id if m.from_user else m.chat.id)
    current = await Mythicbotz.get_destination_channel(uid)
    caption = (
        "<blockquote>🧭 <b>ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ᴄʜᴀɴɴᴇʟ</b></blockquote>\n\n"
        "╭─▸ 📌 <b>ᴀᴜᴛᴏ-ꜰᴏʀᴡᴀʀᴅ :</b> <i>ᴇᴠᴇʀʏ ʀᴇɴᴀᴍᴇᴅ ꜰɪʟᴇ ɪs ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴘᴏsᴛᴇᴅ ᴛᴏ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ.</i>\n"
        "├─▸ 🛡️ <b>ᴘᴇʀᴍɪssɪᴏɴ :</b> <i>ʙᴏᴛ ᴍᴜsᴛ ʙᴇ <b>ᴀᴅᴍɪɴ</b> ɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ.</i>\n"
        f"╰─▸ 📡 <b>ᴄᴜʀʀᴇɴᴛ :</b> <code>{current or 'ɴᴏᴛ sᴇᴛ'}</code>"
    )
    await m.reply_text(caption, reply_markup=_dest_kb(current), quote=True)


# ➕ /adddestination or /setdestination <channel_id>
@Client.on_message(filters.private & filters.command(["adddestination", "setdestination"]))
async def add_destination(client: Client, message: Message):
    if len(message.command) < 2:
        return await _send_dest_card(client, message)

    channel_id = message.command[1]
    try:
        cid = int(channel_id)
    except ValueError:
        return await message.reply_text(
            "<blockquote>❌ <b>ɪɴᴠᴀʟɪᴅ ᴄʜᴀɴɴᴇʟ ɪᴅ</b></blockquote>\n"
            "╰─▸ 💡 <b>ᴜsᴀɢᴇ :</b> <code>/adddestination -100xxxxxxxxxx</code>",
            quote=True,
        )

    await Mythicbotz.save_destination_channel(message.from_user.id, cid)
    await message.reply_text(
        "<blockquote>✅ <b>ᴅᴇsᴛɪɴᴀᴛɪᴏɴ sᴀᴠᴇᴅ</b></blockquote>\n"
        f"╰─▸ 📡 <b>ᴄʜᴀɴɴᴇʟ ɪᴅ :</b> <code>{cid}</code>",
        quote=True,
    )


# ➖ /removedestination or /deldestination
@Client.on_message(filters.private & filters.command(["removedestination", "deldestination"]))
async def remove_destination(client: Client, message: Message):
    await Mythicbotz.clear_destination_channel(message.from_user.id)
    await message.reply_text(
        "<blockquote>🗑️ <b>ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ʀᴇᴍᴏᴠᴇᴅ</b></blockquote>\n"
        "╰─▸ <i>ʏᴏᴜʀ ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ᴄʜᴀɴɴᴇʟ ʜᴀs ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ sᴜᴄᴄᴇssꜰᴜʟʟʏ.</i>",
        quote=True,
    )


# 📋 /listdestinations or /viewdestination
@Client.on_message(filters.private & filters.command(["listdestinations", "viewdestination"]))
async def list_destinations(client: Client, message: Message):
    channel_id = await Mythicbotz.get_destination_channel(message.from_user.id)
    if not channel_id:
        return await message.reply_text(
            "<blockquote>📭 <b>ɴᴏ ᴅᴇsᴛɪɴᴀᴛɪᴏɴ sᴇᴛ</b></blockquote>\n"
            "╰─▸ <i>ᴜsᴇ</i> <code>/setchannel</code> <i>ᴛᴏ ᴄᴏɴꜰɪɢᴜʀᴇ ᴀ ᴄʜᴀɴɴᴇʟ.</i>",
            quote=True,
        )

    await message.reply_text(
        "<blockquote>📌 <b>ᴄᴜʀʀᴇɴᴛ ᴅᴇsᴛɪɴᴀᴛɪᴏɴ</b></blockquote>\n"
        f"╰─▸ 📡 <b>ᴄʜᴀɴɴᴇʟ ɪᴅ :</b> <code>{channel_id}</code>",
        quote=True,
    )


# 🧹 /cleardestinations
@Client.on_message(filters.private & filters.command("cleardestinations"))
async def clear_destinations(client: Client, message: Message):
    await Mythicbotz.clear_destination_channel(message.from_user.id)
    await message.reply_text(
        "<blockquote>🧹 <b>ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ᴄʟᴇᴀʀᴇᴅ</b></blockquote>\n"
        "╰─▸ <i>ᴀʟʟ ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ᴄʜᴀɴɴᴇʟ sᴇᴛᴛɪɴɢs ʜᴀᴠᴇ ʙᴇᴇɴ ʀᴇsᴇᴛ.</i>",
        quote=True,
    )


# 🔍 /checkdestination <channel_id>
@Client.on_message(filters.private & filters.command("checkdestination"))
async def check_destination(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "<blockquote>❌ <b>ᴍɪssɪɴɢ ᴄʜᴀɴɴᴇʟ ɪᴅ</b></blockquote>\n"
            "╰─▸ 💡 <b>ᴜsᴀɢᴇ :</b> <code>/checkdestination -100xxxxxxxxxx</code>",
            quote=True,
        )

    channel_id = message.command[1]
    try:
        target_id = int(channel_id)
    except ValueError:
        return await message.reply_text(
            "<blockquote>❌ <b>ɪɴᴠᴀʟɪᴅ ᴄʜᴀɴɴᴇʟ ɪᴅ</b></blockquote>",
            quote=True,
        )

    current = await Mythicbotz.get_destination_channel(message.from_user.id)
    if current == target_id:
        await message.reply_text(
            "<blockquote>✅ <b>ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ᴀᴄᴛɪᴠᴇ</b></blockquote>\n"
            f"╰─▸ 📡 <code>{target_id}</code> <i>ɪs ᴄᴜʀʀᴇɴᴛʟʏ sᴇᴛ.</i>",
            quote=True,
        )
    else:
        await message.reply_text(
            "<blockquote>❌ <b>ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ɴᴏᴛ sᴇᴛ</b></blockquote>\n"
            f"╰─▸ 📡 <code>{target_id}</code> <i>ɪs ɴᴏᴛ ʏᴏᴜʀ ᴀᴄᴛɪᴠᴇ ᴅᴇsᴛɪɴᴀᴛɪᴏɴ.</i>",
            quote=True,
        )


# 🧭 /setchannel or /setdest interactive card
@Client.on_message(filters.command(["setchannel", "setdest"]) & filters.private)
async def cmd_setchannel(c: Client, m: Message):
    await _send_dest_card(c, m)


@Client.on_message(filters.command(["cancelsetchannel", "cancelsetdest"]) & filters.private)
async def cmd_cancel_setchannel(c: Client, m: Message):
    uid = m.from_user.id
    await Mythicbotz.clear_waiting_for_channel(uid)
    await m.reply_text(
        "<blockquote>✅ <b>sᴇᴛᴜᴘ ᴄᴀɴᴄᴇʟʟᴇᴅ</b></blockquote>\n"
        "╰─▸ <i>ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ᴄʜᴀɴɴᴇʟ sᴇᴛᴜᴘ ʜᴀs ʙᴇᴇɴ ᴄᴀɴᴄᴇʟʟᴇᴅ.</i>",
        quote=True,
    )


@Client.on_callback_query(filters.regex(f"^{CB_SET_DEST}$"))
async def cb_set_dest(c: Client, q: CallbackQuery):
    uid = q.from_user.id
    await Mythicbotz.set_waiting_for_channel(uid, True, int(time.time()))
    await q.answer("Send a forwarded post or channel ID.", show_alert=False)
    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ ᴄᴀɴᴄᴇʟ", callback_data=CB_CANCEL_SET)]])
    prompt = await q.message.reply_text(
        "<blockquote>📡 <b>ʟɪɴᴋ ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ᴄʜᴀɴɴᴇʟ</b></blockquote>\n\n"
        "╭─▸ ➡️ <b>ꜰᴏʀᴡᴀʀᴅ ᴀɴʏ ᴘᴏsᴛ</b> <i>ꜰʀᴏᴍ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ʜᴇʀᴇ</i>\n"
        "├─▸ 🆔 <b>ᴏʀ sᴇɴᴅ :</b> <code>-100xxxxxxxxxx</code> / <code>@username</code>\n"
        f"╰─▸ ⏳ <b>ᴛɪᴍᴇᴏᴜᴛ :</b> <code>{DEST_WAIT_TIMEOUT // 60} ᴍɪɴᴜᴛᴇs</code>",
        reply_markup=cancel_kb,
    )
    try:
        resp = await c.listen(chat_id=uid, timeout=DEST_WAIT_TIMEOUT)
    except (ListenerTimeout, asyncio.TimeoutError):
        await Mythicbotz.clear_waiting_for_channel(uid)
        return await prompt.edit_text(
            "<blockquote>⌛ <b>sᴇᴛᴜᴘ ᴛɪᴍᴇᴅ ᴏᴜᴛ</b></blockquote>\n"
            "╰─▸ <i>ᴜsᴇ</i> <code>/setchannel</code> <i>ᴛᴏ ᴛʀʏ ᴀɢᴀɪɴ.</i>"
        )

    if resp is None or (resp.text and resp.text.startswith("/")):
        await Mythicbotz.clear_waiting_for_channel(uid)
        return

    channel_id, reason = await _extract_channel_id(c, resp)
    if not channel_id:
        await Mythicbotz.clear_waiting_for_channel(uid)
        return await resp.reply_text(
            "<blockquote>⚠️ <b>ᴄʜᴀɴɴᴇʟ ᴅᴇᴛᴇᴄᴛɪᴏɴ ꜰᴀɪʟᴇᴅ</b></blockquote>\n"
            f"╰─▸ <b>ʀᴇᴀsᴏɴ :</b> <code>{reason or 'unknown'}</code>"
        )

    await Mythicbotz.save_destination_channel(uid, channel_id)
    await Mythicbotz.clear_waiting_for_channel(uid)
    await resp.reply_text(
        "<blockquote>✅ <b>ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ᴄʜᴀɴɴᴇʟ sᴀᴠᴇᴅ</b></blockquote>\n"
        f"╰─▸ 📡 <b>ᴄʜᴀɴɴᴇʟ ɪᴅ :</b> <code>{channel_id}</code>"
    )


@Client.on_callback_query(filters.regex(f"^{CB_CANCEL_SET}$"))
async def cb_cancel_set(c: Client, q: CallbackQuery):
    uid = q.from_user.id
    await Mythicbotz.clear_waiting_for_channel(uid)
    try:
        c.stop_listening(chat_id=uid)
    except Exception:
        pass
    await q.answer("Setup cancelled.", show_alert=False)
    await q.message.edit_text(
        "<blockquote>❌ <b>sᴇᴛᴜᴘ ᴄᴀɴᴄᴇʟʟᴇᴅ</b></blockquote>\n"
        "╰─▸ <i>ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ᴄʜᴀɴɴᴇʟ sᴇᴛᴜᴘ ᴄᴀɴᴄᴇʟʟᴇᴅ.</i>"
    )


@Client.on_callback_query(filters.regex(f"^{CB_CLEAR_DEST}$"))
async def cb_clear_dest(c: Client, q: CallbackQuery):
    uid = q.from_user.id
    await Mythicbotz.clear_destination_channel(uid)
    await Mythicbotz.clear_waiting_for_channel(uid)
    await q.answer("Destination cleared.", show_alert=False)
    await q.message.edit_text(
        "<blockquote>🗑️ <b>ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ᴄʟᴇᴀʀᴇᴅ</b></blockquote>\n"
        "╰─▸ <i>ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ᴄʜᴀɴɴᴇʟ ʜᴀs ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ.</i>",
        reply_markup=_dest_kb(None),
    )


@Client.on_callback_query(filters.regex(f"^{CB_HELP_DEST}$"))
async def cb_help_dest(c: Client, q: CallbackQuery):
    await q.answer()
    await q.message.reply_text(
        "<blockquote>❓ <b>ʜᴏᴡ ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ᴄʜᴀɴɴᴇʟ ᴡᴏʀᴋs</b></blockquote>\n\n"
        "╭─▸ <b>1.</b> ᴛᴀᴘ <b>sᴇᴛ ᴅᴇsᴛɪɴᴀᴛɪᴏɴ ᴄʜᴀɴɴᴇʟ</b> ᴏʀ ᴜsᴇ <code>/adddestination -100xxxx</code>\n"
        "├─▸ <b>2.</b> ꜰᴏʀᴡᴀʀᴅ ᴀɴʏ ᴘᴏsᴛ ꜰʀᴏᴍ ʏᴏᴜʀ ᴛᴀʀɢᴇᴛ ᴄʜᴀɴɴᴇʟ ᴏʀ sᴇɴᴅ <code>@username</code>\n"
        "├─▸ <b>3.</b> ᴍᴀᴋᴇ sᴜʀᴇ ᴛʜᴇ ʙᴏᴛ ɪs <b>ᴀᴅᴍɪɴ</b> ɪɴ ᴛʜᴀᴛ ᴄʜᴀɴɴᴇʟ\n"
        "╰─▸ <b>4.</b> ᴇᴠᴇʀʏ ʀᴇɴᴀᴍᴇᴅ ꜰɪʟᴇ ᴡɪʟʟ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ʙᴇ ᴘᴏsᴛᴇᴅ ᴛʜᴇʀᴇ!"
    )


async def _extract_channel_id(c: Client, m: Message) -> Tuple[Optional[int], Optional[str]]:
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
                chat = await c.get_chat(text)
                if chat.type == enums.ChatType.CHANNEL:
                    return chat.id, None
            if "t.me/" in text:
                chat = await c.get_chat(text.rstrip("/").split("/")[-1])
                if chat.type == enums.ChatType.CHANNEL:
                    return chat.id, None
        return None, "Not a valid channel."
    except Exception as e:
        return None, str(e)


# Developer @CosmicBotz
# Telegram Channel @CosmicBotz