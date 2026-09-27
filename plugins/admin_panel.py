import os
import sys
import time
import asyncio
import logging
import datetime
from config import Config
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
from helper.database import Mythicbotz
from bot.core.cache import cache_manager

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@Client.on_message(filters.command("status") & filters.user(Config.ADMIN))
async def get_stats(bot, message: Message):
    total_users = await Mythicbotz.total_users_count()
    uptime_sec = max(0, time.time() - getattr(bot, "uptime", Config.BOT_UPTIME))
    uptime = time.strftime("%Hh %Mm %Ss", time.gmtime(uptime_sec))
    start_t = time.time()
    st = await message.reply("<blockquote>⏳ <b>ꜰᴇᴛᴄʜɪɴɢ sʏsᴛᴇᴍ ᴛᴇʟᴇᴍᴇᴛʀʏ...</b></blockquote>")
    end_t = time.time()
    time_taken_s = (end_t - start_t) * 1000

    # Gather Multi-Session Pool & RAM Cache metrics
    pool_stats = bot.fast_pool.get_stats() if hasattr(bot, "fast_pool") else {}
    cache_stats = cache_manager.get_summary()
    mem_info = cache_stats.get("memory", {})
    user_c = cache_stats.get("user_cache", {})
    thumb_c = cache_stats.get("thumb_cache", {})

    status_text = (
        f"<blockquote>⚡ <b>ᴄᴏsᴍɪᴄʙᴏᴛᴢ ʜɪɢʜ-sᴘᴇᴇᴅ sᴛᴀᴛs</b></blockquote>\n\n"
        f"╭─▸ ⌚ <b>ᴜᴘᴛɪᴍᴇ :</b> <code>{uptime}</code>\n"
        f"├─▸ 🛰️ <b>ᴘɪɴɢ :</b> <code>{time_taken_s:.2f} ms</code>\n"
        f"╰─▸ 👥 <b>ᴛᴏᴛᴀʟ ᴜsᴇʀs :</b> <code>{total_users}</code>\n\n"
        f"<blockquote>🚀 <b>ᴍᴜʟᴛɪ-sᴇssɪᴏɴ ᴍᴇᴅɪᴀ ᴘᴏᴏʟ</b></blockquote>\n"
        f"╭─▸ 🔌 <b>ᴘᴀʀᴀʟʟᴇʟ sᴛʀᴇᴀᴍs :</b> <code>{pool_stats.get('configured_pool_size', Config.MEDIA_POOL_SIZE)} ᴛᴄᴘ sᴏᴄᴋᴇᴛs</code> (<code>{pool_stats.get('chunk_size_kb', 512)} KB</code>)\n"
        f"├─▸ 📡 <b>ᴀᴄᴛɪᴠᴇ sᴏᴄᴋᴇᴛs :</b> <code>{pool_stats.get('active_media_sockets', 0)}</code>\n"
        f"╰─▸ 🔐 <b>ᴄʀʏᴘᴛᴏ ᴇɴɢɪɴᴇ :</b> <code>{pool_stats.get('crypto_backend', 'WarpCrypto AES-NI')}</code>\n\n"
        f"<blockquote>🧠 <b>ᴍᴇᴍᴏʀʏ & ʀᴀᴍ ᴄᴀᴄʜᴇ</b></blockquote>\n"
        f"╭─▸ 📊 <b>ᴘʀᴏᴄᴇss ʀᴀᴍ (ʀss) :</b> <code>{mem_info.get('process_rss_mb', 0.0)} MB</code>\n"
        f"├─▸ 💾 <b>ᴀᴠᴀɪʟᴀʙʟᴇ ʀᴀᴍ :</b> <code>{mem_info.get('available_ram_mb', 0.0)} MB</code>\n"
        f"├─▸ ⚡ <b>ʀᴀᴍ-ᴅɪsᴋ (<code>/dev/shm</code>) :</b> <code>{'ᴇɴᴀʙʟᴇᴅ ✅' if cache_stats.get('shm_enabled') else 'ᴅɪsᴋ ꜰᴀʟʟʙᴀᴄᴋ 📁'}</code>\n"
        f"├─▸ 🗂️ <b>ᴜsᴇʀ ᴅʙ ᴄᴀᴄʜᴇ :</b> <code>{user_c.get('items', 0)}</code> (<code>{user_c.get('hit_rate_pct', 0.0)}%</code> ʜɪᴛs)\n"
        f"╰─▸ 🖼️ <b>ᴛʜᴜᴍʙ ʀᴀᴍ ᴄᴀᴄʜᴇ :</b> <code>{thumb_c.get('items', 0)}</code> (<code>{thumb_c.get('size_kb', 0.0)} KB</code>)"
    )
    await st.edit(text=status_text)


@Client.on_message(filters.command("users") & filters.user(Config.ADMIN))
async def list_users_count(bot, message: Message):
    total_users = await Mythicbotz.total_users_count()
    await message.reply_text(
        "<blockquote>👥 <b>ʀᴇɢɪsᴛᴇʀᴇᴅ ᴜsᴇʀs</b></blockquote>\n"
        f"╰─▸ <b>ᴛᴏᴛᴀʟ ᴜsᴇʀs :</b> <code>{total_users}</code>",
        quote=True,
    )


@Client.on_message(filters.command("banned") & filters.user(Config.ADMIN))
async def list_banned_users(bot, message: Message):
    cursor = Mythicbotz.bannedList.find({})
    banned_ids = [str(doc.get("banId")) async for doc in cursor if doc.get("banId") is not None]
    if not banned_ids:
        return await message.reply_text(
            "<blockquote>✅ <b>ʙᴀɴɴᴇᴅ ᴜsᴇʀs</b></blockquote>\n"
            "╰─▸ <i>ɴᴏ ᴜsᴇʀs ᴀʀᴇ ᴄᴜʀʀᴇɴᴛʟʏ ʙᴀɴɴᴇᴅ.</i>",
            quote=True,
        )
    await message.reply_text(
        f"<blockquote>🚫 <b>ʙᴀɴɴᴇᴅ ᴜsᴇʀs ({len(banned_ids)})</b></blockquote>\n\n"
        + "\n".join(f"├─▸ <code>{uid}</code>" for uid in banned_ids[:50]),
        quote=True,
    )


@Client.on_message(filters.command("restart") & filters.user(Config.ADMIN))
async def restart_bot(bot, message: Message):
    msg = await bot.send_message(
        text="<blockquote>🔄 <b>ʀᴇsᴛᴀʀᴛɪɴɢ ʙᴏᴛ...</b></blockquote>\n╰─▸ <i>sᴛᴏᴘᴘɪɴɢ ᴀᴄᴛɪᴠᴇ ᴘʀᴏᴄᴇssᴇs...</i>",
        chat_id=message.chat.id,
    )
    await asyncio.sleep(3)
    await msg.edit(
        "<blockquote>✅ <b>ʙᴏᴛ ʀᴇsᴛᴀʀᴛᴇᴅ</b></blockquote>\n"
        "╰─▸ <i>ᴀʟʟ sʏsᴛᴇᴍs ᴏɴʟɪɴᴇ!</i>"
    )
    os.execl(sys.executable, sys.executable, *sys.argv)


@Client.on_message(filters.private & filters.command("ping"))
async def ping(_, message: Message):
    start_t = time.time()
    rm = await message.reply_text("<blockquote>🛰️ <b>ᴘɪɴɢɪɴɢ...</b></blockquote>")
    end_t = time.time()
    time_taken_s = (end_t - start_t) * 1000
    await rm.edit(
        "<blockquote>⚡ <b>ᴘᴏɴɢ!</b></blockquote>\n"
        f"╰─▸ 🛰️ <b>ʟᴀᴛᴇɴᴄʏ :</b> <code>{time_taken_s:.3f} ms</code>"
    )
    return time_taken_s


@Client.on_message(filters.command("broadcast") & filters.user(Config.ADMIN) & filters.reply)
async def broadcast_handler(bot: Client, m: Message):
    await bot.send_message(
        Config.LOG_CHANNEL,
        f"<blockquote>📢 <b>ʙʀᴏᴀᴅᴄᴀsᴛ ɪɴɪᴛɪᴀᴛᴇᴅ</b></blockquote>\n"
        f"╰─▸ <b>ᴀᴅᴍɪɴ :</b> {m.from_user.mention} (<code>{m.from_user.id}</code>)",
    )
    all_users = await Mythicbotz.get_all_users()
    broadcast_msg = m.reply_to_message
    sts_msg = await m.reply_text("<blockquote>📢 <b>ʙʀᴏᴀᴅᴄᴀsᴛ sᴛᴀʀᴛᴇᴅ...</b></blockquote>")
    done = 0
    failed = 0
    success = 0
    start_time = time.time()
    total_users = await Mythicbotz.total_users_count()
    async for user in all_users:
        sts = await send_msg(user["_id"], broadcast_msg)
        if sts == 200:
            success += 1
        else:
            failed += 1
        if sts == 400:
            await Mythicbotz.delete_user(user["_id"])
        done += 1
        if not done % 20:
            await sts_msg.edit(
                "<blockquote>📢 <b>ʙʀᴏᴀᴅᴄᴀsᴛ ɪɴ ᴘʀᴏɢʀᴇss</b></blockquote>\n\n"
                f"╭─▸ 👥 <b>ᴛᴏᴛᴀʟ ᴜsᴇʀs :</b> <code>{total_users}</code>\n"
                f"├─▸ 📊 <b>ᴄᴏᴍᴘʟᴇᴛᴇᴅ :</b> <code>{done} / {total_users}</code>\n"
                f"├─▸ ✅ <b>sᴜᴄᴄᴇss :</b> <code>{success}</code>\n"
                f"╰─▸ ❌ <b>ꜰᴀɪʟᴇᴅ :</b> <code>{failed}</code>"
            )
    completed_in = datetime.timedelta(seconds=int(time.time() - start_time))
    await sts_msg.edit(
        "<blockquote>✅ <b>ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ</b></blockquote>\n\n"
        f"╭─▸ ⏱️ <b>ᴅᴜʀᴀᴛɪᴏɴ :</b> <code>{completed_in}</code>\n"
        f"├─▸ 👥 <b>ᴛᴏᴛᴀʟ ᴜsᴇʀs :</b> <code>{total_users}</code>\n"
        f"├─▸ 📊 <b>ᴄᴏᴍᴘʟᴇᴛᴇᴅ :</b> <code>{done} / {total_users}</code>\n"
        f"├─▸ ✅ <b>sᴜᴄᴄᴇss :</b> <code>{success}</code>\n"
        f"╰─▸ ❌ <b>ꜰᴀɪʟᴇᴅ :</b> <code>{failed}</code>"
    )


async def send_msg(user_id, message):
    try:
        await message.copy(chat_id=int(user_id))
        return 200
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await send_msg(user_id, message)
    except InputUserDeactivated:
        logger.info(f"{user_id} : Deactivated")
        return 400
    except UserIsBlocked:
        logger.info(f"{user_id} : Blocked The Bot")
        return 400
    except PeerIdInvalid:
        logger.info(f"{user_id} : User ID Invalid")
        return 400
    except Exception as e:
        logger.error(f"{user_id} : {e}")
        return 500


@Client.on_message(filters.command("ban") & filters.user(Config.ADMIN))
async def do_ban(bot, message: Message):
    userid = message.text.split(" ", 2)[1] if len(message.text.split(" ", 1)) > 1 else None
    reason = message.text.split(" ", 2)[2] if len(message.text.split(" ", 2)) > 2 else None
    if not userid:
        return await message.reply(
            "<blockquote>🚫 <b>ʙᴀɴ ᴜsᴇʀ / ᴄʜᴀɴɴᴇʟ</b></blockquote>\n\n"
            "╭─▸ ⚠️ <b>ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴠᴀʟɪᴅ ɪᴅ!</b>\n"
            "├─▸ 💡 <b>ᴇxᴀᴍᴘʟᴇ :</b> <code>/ban 1234567899</code>\n"
            "╰─▸ 📝 <b>ᴡɪᴛʜ ʀᴇᴀsᴏɴ :</b> <code>/ban 1234567899 spamming</code>"
        )
    text = await message.reply("<blockquote>⏳ <b>ᴘʀᴏᴄᴇssɪɴɢ ʙᴀɴ...</b></blockquote>")
    banSts = await Mythicbotz.ban_user(userid)
    if banSts is True:
        await text.edit(
            text=(
                "<blockquote>🚫 <b>ᴜsᴇʀ ʙᴀɴɴᴇᴅ</b></blockquote>\n\n"
                f"╭─▸ 🆔 <b>ᴜsᴇʀ ɪᴅ :</b> <code>{userid}</code>\n"
                "╰─▸ 📩 <i>sʜᴏᴜʟᴅ ɪ sᴇɴᴅ ᴀɴ ᴀʟᴇʀᴛ ᴛᴏ ᴛʜᴇ ʙᴀɴɴᴇᴅ ᴜsᴇʀ?</i>"
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "ʏᴇs ✅",
                            callback_data=f"sendAlert_{userid}_{reason if reason else 'no reason provided'}",
                        ),
                        InlineKeyboardButton("ɴᴏ ❌", callback_data=f"noAlert_{userid}"),
                    ],
                ]
            ),
        )
    else:
        await text.edit(
            "<blockquote>⚠️ <b>ᴀʟʀᴇᴀᴅʏ ʙᴀɴɴᴇᴅ</b></blockquote>\n"
            f"╰─▸ <code>{userid}</code> <i>ɪs ᴀʟʀᴇᴀᴅʏ ᴏɴ ᴛʜᴇ ʙᴀɴ ʟɪsᴛ!</i>"
        )
    return


@Client.on_message(filters.command("unban") & filters.user(Config.ADMIN))
async def do_unban(bot, message: Message):
    userid = message.text.split(" ", 2)[1] if len(message.text.split(" ", 1)) > 1 else None
    if not userid:
        return await message.reply(
            "<blockquote>✅ <b>ᴜɴʙᴀɴ ᴜsᴇʀ</b></blockquote>\n"
            "╰─▸ 💡 <b>ᴇxᴀᴍᴘʟᴇ :</b> <code>/unban 1234567899</code>"
        )
    text = await message.reply("<blockquote>⏳ <b>ᴘʀᴏᴄᴇssɪɴɢ ᴜɴʙᴀɴ...</b></blockquote>")
    unban_chk = await Mythicbotz.is_unbanned(userid)
    if unban_chk is True:
        await text.edit(
            text=(
                "<blockquote>✅ <b>ᴜsᴇʀ ᴜɴʙᴀɴɴᴇᴅ</b></blockquote>\n\n"
                f"╭─▸ 🆔 <b>ᴜsᴇʀ ɪᴅ :</b> <code>{userid}</code>\n"
                "╰─▸ 📩 <i>sʜᴏᴜʟᴅ ɪ sᴇɴᴅ ᴀɴ ᴜɴʙᴀɴ ᴀʟᴇʀᴛ ᴛᴏ ᴛʜᴇ ᴜsᴇʀ?</i>"
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("ʏᴇs ✅", callback_data=f"sendUnbanAlert_{userid}"),
                        InlineKeyboardButton("ɴᴏ ❌", callback_data=f"NoUnbanAlert_{userid}"),
                    ],
                ]
            ),
        )
    elif unban_chk is False:
        await text.edit(
            "<blockquote>ℹ️ <b>ɴᴏᴛ ʙᴀɴɴᴇᴅ</b></blockquote>\n"
            "╰─▸ <i>ᴛʜɪs ᴜsᴇʀ ɪs ɴᴏᴛ ᴄᴜʀʀᴇɴᴛʟʏ ʙᴀɴɴᴇᴅ.</i>"
        )
    else:
        await text.edit(
            "<blockquote>❌ <b>ᴜɴʙᴀɴ ꜰᴀɪʟᴇᴅ</b></blockquote>\n"
            f"╰─▸ <b>ʀᴇᴀsᴏɴ :</b> <code>{unban_chk}</code>"
        )


# Developer @CosmicBotz
# Telegram Channel @CosmicBotz

