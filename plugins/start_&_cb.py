from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    Message,
)
from pyrogram.enums import ParseMode
from helper.database import Mythicbotz
from helper.utils import refresh_progress_message, cancel_transfer
from config import Config, Txt


async def _safe_edit(query: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup = None):
    """Safely edit callback message whether it is a photo (caption) or text message."""
    msg = query.message
    try:
        if getattr(msg, "photo", None) or getattr(msg, "caption", None) is not None:
            return await msg.edit_caption(caption=text, reply_markup=reply_markup)
        return await msg.edit_text(
            text=text,
            disable_web_page_preview=True,
            reply_markup=reply_markup,
        )
    except Exception:
        return await msg.edit_text(
            text=text,
            disable_web_page_preview=True,
            reply_markup=reply_markup,
        )


def _start_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⚡ ᴀʙᴏᴜᴛ", callback_data="about"),
                InlineKeyboardButton("🛠️ ʜᴇʟᴘ & ᴍᴏᴅᴜʟᴇs", callback_data="help"),
            ],
            [
                InlineKeyboardButton("🏆 ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ", callback_data="leaderboard"),
                InlineKeyboardButton("👨‍💻 ᴅᴇᴠᴇʟᴏᴘᴇʀ", url="https://telegram.me/CosmicBotz"),
            ],
        ]
    )


def _help_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⚙️ ᴍᴇᴛᴀᴅᴀᴛᴀ", callback_data="meta"),
                InlineKeyboardButton("🧭 ᴅᴇsᴛɪɴᴀᴛɪᴏɴ", callback_data="set_dest_channel"),
            ],
            [
                InlineKeyboardButton("🏷️ ᴘʀᴇꜰɪx", callback_data="prefix"),
                InlineKeyboardButton("🔖 sᴜꜰꜰɪx", callback_data="suffix"),
            ],
            [
                InlineKeyboardButton("📝 ᴄᴀᴘᴛɪᴏɴ", callback_data="caption"),
                InlineKeyboardButton("🖼️ ᴛʜᴜᴍʙɴᴀɪʟ", callback_data="thumbnail"),
            ],
            [
                InlineKeyboardButton("🏆 ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ", callback_data="leaderboard"),
                InlineKeyboardButton("🏠 ʜᴏᴍᴇ", callback_data="start"),
            ],
        ]
    )


@Client.on_message(filters.private & filters.command("start"))
async def start(client: Client, message: Message):
    user = message.from_user
    await Mythicbotz.add_user(client, message)

    # 1. Send sticker BEFORE the /start welcome message
    if Config.STICKER_ID:
        try:
            await message.reply_sticker(Config.STICKER_ID)
        except Exception as e:
            print(f"Error sending sticker: {e}")

    # 2. Send premium /start card
    button = _start_buttons()
    if Config.START_PIC:
        await message.reply_photo(
            photo=Config.START_PIC,
            caption=Txt.START_TXT.format(user.mention),
            reply_markup=button,
        )
    else:
        await message.reply_text(
            text=Txt.START_TXT.format(user.mention),
            reply_markup=button,
            disable_web_page_preview=True,
        )


@Client.on_message(filters.private & filters.command("help"))
async def help_cmd(client: Client, message: Message):
    await Mythicbotz.add_user(client, message)
    await message.reply_text(
        text=Txt.HELP_TXT,
        disable_web_page_preview=True,
        reply_markup=_help_buttons(),
    )


@Client.on_callback_query(
    filters.regex(
        r"^(start|help|meta|prefix|suffix|caption|thumbnail|about|donate|leaderboard|refresh_progress|cancel_transfer|close|sendAlert_|noAlert_|sendUnbanAlert_|NoUnbanAlert_)"
    )
)
async def cb_handler(client: Client, query: CallbackQuery):
    data = query.data

    if data == "start":
        await _safe_edit(
            query,
            text=Txt.START_TXT.format(query.from_user.mention),
            reply_markup=_start_buttons(),
        )

    elif data == "help":
        await _safe_edit(
            query,
            text=Txt.HELP_TXT,
            reply_markup=_help_buttons(),
        )

    elif data == "meta":
        await _safe_edit(
            query,
            text=Txt.SEND_METADATA,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="help"),
                        InlineKeyboardButton("✖️ ᴄʟᴏsᴇ", callback_data="close"),
                    ]
                ]
            ),
        )

    elif data == "prefix":
        await _safe_edit(
            query,
            text=Txt.PREFIX,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="help"),
                        InlineKeyboardButton("✖️ ᴄʟᴏsᴇ", callback_data="close"),
                    ]
                ]
            ),
        )

    elif data == "suffix":
        await _safe_edit(
            query,
            text=Txt.SUFFIX,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="help"),
                        InlineKeyboardButton("✖️ ᴄʟᴏsᴇ", callback_data="close"),
                    ]
                ]
            ),
        )

    elif data == "caption":
        await _safe_edit(
            query,
            text=Txt.CAPTION_TXT,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="help"),
                        InlineKeyboardButton("✖️ ᴄʟᴏsᴇ", callback_data="close"),
                    ]
                ]
            ),
        )

    elif data == "thumbnail":
        await _safe_edit(
            query,
            text=Txt.THUMBNAIL_TXT,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="help"),
                        InlineKeyboardButton("✖️ ᴄʟᴏsᴇ", callback_data="close"),
                    ]
                ]
            ),
        )

    elif data == "about":
        await _safe_edit(
            query,
            text=Txt.ABOUT_TXT,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("👨‍💻 ᴅᴇᴠᴇʟᴏᴘᴇʀ", url="https://telegram.me/CosmicBotz"),
                        InlineKeyboardButton("💖 ᴅᴏɴᴀᴛᴇ", callback_data="donate"),
                    ],
                    [InlineKeyboardButton("🏠 ʜᴏᴍᴇ", callback_data="start")],
                ]
            ),
        )

    elif data == "donate":
        await _safe_edit(
            query,
            text=Txt.DONATE_TXT,
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🤖 ᴏᴜʀ ᴄʜᴀɴɴᴇʟ", url="https://telegram.me/CosmicBotz")],
                    [
                        InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="about"),
                        InlineKeyboardButton("✖️ ᴄʟᴏsᴇ", callback_data="close"),
                    ],
                ]
            ),
        )

    elif data == "leaderboard":
        leaderboard = await Mythicbotz.get_leaderboard()
        if not leaderboard:
            return await _safe_edit(
                query,
                text=(
                    "<blockquote>🏆 <b>ᴛᴏᴘ ʀᴇɴᴀᴍᴇʀs ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ</b></blockquote>\n\n"
                    "╰─ <code>ɴᴏ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ ᴅᴀᴛᴀ ꜰᴏᴜɴᴅ ʏᴇᴛ.</code>"
                ),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="help")]]),
            )

        text = "<blockquote>🏆 <b>ᴛᴏᴘ ʀᴇɴᴀᴍᴇʀs ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ</b></blockquote>\n\n"
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        for rank, (user_id, count) in enumerate(leaderboard, start=1):
            try:
                user = await client.get_users(user_id)
                name = user.mention
            except Exception:
                name = f"<a href='tg://user?id={user_id}'>ᴜsᴇʀ {user_id}</a>"
            badge = medals.get(rank, f"<b>{rank}.</b>")
            prefix_branch = "╰─" if rank == len(leaderboard) else "├─"
            text += f"{prefix_branch} {badge} {name} — <code>{count} ꜰɪʟᴇs</code>\n"

        await _safe_edit(
            query,
            text=text,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("⬅️ ʙᴀᴄᴋ", callback_data="help"),
                        InlineKeyboardButton("🏠 ʜᴏᴍᴇ", callback_data="start"),
                    ]
                ]
            ),
        )

    elif data == "refresh_progress":
        await refresh_progress_message(query)

    elif data in ("cancel_transfer", "close"):
        try:
            chat_id = query.message.chat.id
            msg_id = query.message.id
            cancel_transfer(chat_id, msg_id)
        except Exception:
            pass
        try:
            await query.answer("🛑 ᴄᴀɴᴄᴇʟʟɪɴɢ ᴛʀᴀɴsꜰᴇʀ...", show_alert=False)
        except Exception:
            pass
        try:
            await query.message.delete()
            if query.message.reply_to_message:
                await query.message.reply_to_message.delete()
        except Exception:
            pass

    elif data.startswith("sendAlert"):
        parts = data.split("_", 2)
        user_id = int(parts[1].strip())
        reason = str(parts[2]) if len(parts) > 2 else "no reason provided"
        try:
            await client.send_message(
                user_id,
                "<blockquote>🚫 <b>ᴀᴄᴄᴏᴜɴᴛ ʀᴇsᴛʀɪᴄᴛᴇᴅ</b></blockquote>\n"
                f"╭─ <b>ʙᴀɴɴᴇᴅ ʙʏ :</b> <a href='https://telegram.me/CosmicBotz'>CosmicBotz</a>\n"
                f"╰─ <b>ʀᴇᴀsᴏɴ :</b> <code>{reason}</code>",
            )
            await query.message.edit(
                "<blockquote>✅ <b>ʙᴀɴ ᴀʟᴇʀᴛ ᴅᴇʟɪᴠᴇʀᴇᴅ</b></blockquote>\n"
                f"╭─ <b>ᴜsᴇʀ ɪᴅ :</b> <code>{user_id}</code>\n"
                f"╰─ <b>ʀᴇᴀsᴏɴ :</b> <code>{reason}</code>"
            )
        except Exception as e:
            await query.message.edit(f"<b>⚠️ ᴇʀʀᴏʀ sᴇɴᴅɪɴɢ ᴀʟᴇʀᴛ :</b> <code>{e}</code>")

    elif data.startswith("noAlert"):
        user_id = int(data.split("_")[1].strip())
        await query.message.edit(
            f"<blockquote>🔇 <b>sɪʟᴇɴᴛ ʙᴀɴ ᴇxᴇᴄᴜᴛᴇᴅ</b></blockquote>\n"
            f"╰─ <b>ᴜsᴇʀ ɪᴅ :</b> <code>{user_id}</code>"
        )

    elif data.startswith("sendUnbanAlert"):
        user_id = int(data.split("_")[1].strip())
        try:
            unban_text = (
                "<blockquote>🎉 <b>ᴀᴄᴄᴇss ʀᴇsᴛᴏʀᴇᴅ</b></blockquote>\n"
                "╰─ <b>ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ᴜɴʙᴀɴɴᴇᴅ ʙʏ</b> <a href='https://telegram.me/CosmicBotz'>CosmicBotz</a>!"
            )
            await client.send_message(user_id, unban_text)
            await query.message.edit(
                "<blockquote>✅ <b>ᴜɴʙᴀɴ ᴀʟᴇʀᴛ ᴅᴇʟɪᴠᴇʀᴇᴅ</b></blockquote>\n"
                f"╰─ <b>ᴜsᴇʀ ɪᴅ :</b> <code>{user_id}</code>"
            )
        except Exception as e:
            await query.message.edit(f"<b>⚠️ ᴇʀʀᴏʀ sᴇɴᴅɪɴɢ ᴀʟᴇʀᴛ :</b> <code>{e}</code>")

    elif data.startswith("NoUnbanAlert"):
        user_id = int(data.split("_")[1].strip())
        await query.message.edit(
            f"<blockquote>🔇 <b>sɪʟᴇɴᴛ ᴜɴʙᴀɴ ᴇxᴇᴄᴜᴛᴇᴅ</b></blockquote>\n"
            f"╰─ <b>ᴜsᴇʀ ɪᴅ :</b> <code>{user_id}</code>"
        )


# ========== leaderboard command handler ==============#
@Client.on_message(filters.command("leaderboard") & filters.private)
async def leaderboard_handler(client: Client, message: Message):
    top_users = await Mythicbotz.get_leaderboard(limit=10)

    if not top_users:
        return await message.reply(
            "<blockquote>🏆 <b>ᴛᴏᴘ ʀᴇɴᴀᴍᴇʀs ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ</b></blockquote>\n\n"
            "╰─ <code>ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ ɪs ᴄᴜʀʀᴇɴᴛʟʏ ᴇᴍᴘᴛʏ.</code>"
        )

    text = "<blockquote>🏆 <b>ᴛᴏᴘ 𝟷𝟶 ʀᴇɴᴀᴍᴇʀs ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ</b></blockquote>\n\n"
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, (user_id, count) in enumerate(top_users, start=1):
        try:
            user = await client.get_users(user_id)
            mention = user.mention
        except Exception:
            mention = f"<code>{user_id}</code>"
        badge = medals.get(i, f"<b>{i}.</b>")
        branch = "╰─" if i == len(top_users) else "├─"
        text += f"{branch} {badge} {mention} — <code>{count} ꜰɪʟᴇs</code>\n"

    await message.reply(
        text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


# Developer @CosmicBotz
# Telegram Channel @CosmicBotz