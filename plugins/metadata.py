import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from helper.database import Mythicbotz
from config import Txt

try:
    from wzgram.errors import ListenerTimeout
except ImportError:
    try:
        from pyrogram.errors import ListenerTimeout
    except ImportError:
        ListenerTimeout = asyncio.TimeoutError


ON = [
    [InlineKeyboardButton("ᴍᴇᴛᴀᴅᴀᴛᴀ : ᴏɴ ✅", callback_data="metadata_1")],
    [InlineKeyboardButton("✏️ sᴇᴛ ᴄᴜsᴛᴏᴍ ᴍᴇᴛᴀᴅᴀᴛᴀ", callback_data="cutom_metadata")],
]
OFF = [
    [InlineKeyboardButton("ᴍᴇᴛᴀᴅᴀᴛᴀ : ᴏꜰꜰ ❌", callback_data="metadata_0")],
    [InlineKeyboardButton("✏️ sᴇᴛ ᴄᴜsᴛᴏᴍ ᴍᴇᴛᴀᴅᴀᴛᴀ", callback_data="cutom_metadata")],
]


def _format_metadata_card(user_metadata: str, is_on: bool) -> str:
    state_label = "ᴇɴᴀʙʟᴇᴅ ✅" if is_on else "ᴅɪsᴀʙʟᴇᴅ ❌"
    return (
        "<blockquote>⚙️ <b>ᴍᴇᴛᴀᴅᴀᴛᴀ ᴄᴏɴꜰɪɢᴜʀᴀᴛɪᴏɴ</b></blockquote>\n\n"
        f"╭─▸ 📌 <b>sᴛᴀᴛᴜs :</b> <code>{state_label}</code>\n"
        f"├─▸ 🏷️ <b>ᴄᴜʀʀᴇɴᴛ ᴛᴀɢ :</b> <code>{user_metadata}</code>\n"
        f"╰─▸ 🎬 <b>ᴀᴜᴛᴏ ᴠɪᴅᴇᴏ ᴛʜᴜᴍʙ :</b> <code>ᴀʟᴡᴀʏs ᴀᴄᴛɪᴠᴇ (~30s sᴇᴇᴋ)</code>"
    )


@Client.on_message(filters.private & filters.command("metadata"))
async def handle_metadata(bot: Client, message: Message):
    ms = await message.reply_text(
        "<blockquote>⏳ <b>ʟᴏᴀᴅɪɴɢ ᴍᴇᴛᴀᴅᴀᴛᴀ sᴇᴛᴛɪɴɢs...</b></blockquote>",
        reply_to_message_id=message.id,
    )
    user_data = await Mythicbotz.get_user_data(message.from_user.id) or {}
    bool_metadata = user_data.get("metadata", False)
    user_metadata = user_data.get("metadata_code") or "By :- @CosmicBotz"
    await ms.delete()
    if bool_metadata:
        return await message.reply_text(
            _format_metadata_card(user_metadata, True),
            quote=True,
            reply_markup=InlineKeyboardMarkup(ON),
        )
    return await message.reply_text(
        _format_metadata_card(user_metadata, False),
        quote=True,
        reply_markup=InlineKeyboardMarkup(OFF),
    )


@Client.on_callback_query(filters.regex(r"^(custom_metadata|cutom_metadata|metadata_[01])$"))
async def query_metadata(bot: Client, query: CallbackQuery):
    data = query.data

    if data.startswith("metadata_"):
        _bool = data.split("_")[1]
        user_metadata = (await Mythicbotz.get_metadata_code(query.from_user.id)) or "By :- @CosmicBotz"

        if _bool == "1":
            await Mythicbotz.set_metadata(query.from_user.id, bool_meta=False)
            await query.message.edit(
                _format_metadata_card(user_metadata, False),
                reply_markup=InlineKeyboardMarkup(OFF),
            )
        else:
            await Mythicbotz.set_metadata(query.from_user.id, bool_meta=True)
            await query.message.edit(
                _format_metadata_card(user_metadata, True),
                reply_markup=InlineKeyboardMarkup(ON),
            )

    elif data in ("cutom_metadata", "custom_metadata"):
        await query.message.delete()
        try:
            try:
                metadata = await bot.ask(
                    chat_id=query.from_user.id,
                    text=Txt.SEND_METADATA,
                    filters=filters.text,
                    timeout=30,
                    disable_web_page_preview=True,
                )
            except (ListenerTimeout, asyncio.TimeoutError):
                await query.message.reply_text(
                    "<blockquote>⚠️ <b>ʀᴇǫᴜᴇsᴛ ᴛɪᴍᴇᴅ ᴏᴜᴛ</b></blockquote>\n"
                    "╰─▸ <i>ʀᴇsᴛᴀʀᴛ ʙʏ ᴜsɪɴɢ</i> <code>/metadata</code>",
                )
                return
            ms = await query.message.reply_text(
                "<blockquote>⏳ <b>sᴀᴠɪɴɢ ᴍᴇᴛᴀᴅᴀᴛᴀ...</b></blockquote>",
                reply_to_message_id=metadata.id,
            )
            await Mythicbotz.set_metadata_code(query.from_user.id, metadata_code=metadata.text)
            await ms.edit(
                "<blockquote>✅ <b>ᴍᴇᴛᴀᴅᴀᴛᴀ sᴀᴠᴇᴅ</b></blockquote>\n"
                f"╰─▸ <b>ɴᴇᴡ ᴛᴀɢ :</b> <code>{metadata.text}</code>"
            )
        except Exception as e:
            print(f"Metadata callback error: {e}")


# Developer @CosmicBotz
# Telegram Channel @CosmicBotz

