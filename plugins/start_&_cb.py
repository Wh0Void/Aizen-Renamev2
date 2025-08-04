import random
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply, CallbackQuery
from helper.database import jishubotz
from config import Config, Txt  
from pyrogram.enums import ParseMode

@Client.on_message(filters.private & filters.command("start"))
async def start(client, message):
    user = message.from_user
    await jishubotz.add_user(client, message)                
    button = InlineKeyboardMarkup([
        [InlineKeyboardButton('• ᴀʙᴏᴜᴛ •', callback_data='about'),
         InlineKeyboardButton('• ʜᴇʟᴘ •', callback_data='help')],
        [InlineKeyboardButton("♻ ᴅᴇᴠᴇʟᴏᴘᴇʀ ♻", url='https://telegram.me/VoidXTora')]
    ])
    if Config.START_PIC:
        await message.reply_photo(Config.START_PIC, caption=Txt.START_TXT.format(user.mention), reply_markup=button)       
    else:
        await message.reply_text(text=Txt.START_TXT.format(user.mention), reply_markup=button, disable_web_page_preview=True)


@Client.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    data = query.data 

    if data == "start":
        await query.message.edit_text(
            text=Txt.START_TXT.format(query.from_user.mention),
            disable_web_page_preview=True,
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton('• ᴀʙᴏᴜᴛ •', callback_data='about'),
                 InlineKeyboardButton('• ʜᴇʟᴘ •', callback_data='help')],
                [InlineKeyboardButton("♻ ᴅᴇᴠᴇʟᴏᴘᴇʀ ♻", url='https://telegram.me/TechifyRahul')]
            ])
        )

    elif data == "help":
        await query.message.edit_text(
            text=Txt.HELP_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("sᴇᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ", callback_data="meta")],
                [InlineKeyboardButton("ᴘʀᴇꜰɪx", callback_data="prefix"),
                 InlineKeyboardButton("sᴜꜰꜰɪx", callback_data="suffix")],
                [InlineKeyboardButton("ᴄᴀᴘᴛɪᴏɴ", callback_data="caption"),
                 InlineKeyboardButton("ᴛʜᴜᴍʙɴᴀɪʟ", callback_data="thumbnail")],
                [InlineKeyboardButton("ʜᴏᴍᴇ", callback_data="start")]
            ])            
        )

    elif data == "meta":
        await query.message.edit_caption(
            caption=Txt.SEND_METADATA,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="help"), InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")]
            ])
        )

    elif data == "prefix":
        await query.message.edit_caption(
            caption=Txt.PREFIX,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="help"), InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")]
            ])
        )

    elif data == "suffix":
        await query.message.edit_caption(
            caption=Txt.SUFFIX,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="help"), InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")]
            ])
        )

    elif data == "caption":
        await query.message.edit_caption(
            caption=Txt.CAPTION_TXT,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="help"), InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")]
            ])
        )

    elif data == "thumbnail":
        await query.message.edit_caption(
            caption=Txt.THUMBNAIL_TXT,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="help"), InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")]
            ])
        )

    elif data == "about":
        await query.message.edit_text(
            text=Txt.ABOUT_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👨‍💻  ʀᴇᴘᴏ", url="https://github.com/TechifyBots"),
                 InlineKeyboardButton("💥  ᴅᴏɴᴀᴛᴇ", callback_data="donate")],
                [InlineKeyboardButton("ʜᴏᴍᴇ", callback_data="start")]
            ])            
        )

    elif data == "donate":
        await query.message.edit_text(
            text=Txt.DONATE_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🤖 ᴍᴏʀᴇ ʙᴏᴛs", url="https://telegram.me/TechifyBots/8")],
                [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="about"),
                 InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")]
            ])            
        )

    elif data == "leaderboard":
        leaderboard = await jishubotz.get_leaderboard()
        if not leaderboard:
            return await query.message.edit("🏆 No leaderboard data found yet.")

        text = "🏆 **Top Renamers Leaderboard** 🏆\n\n"
        for rank, (user_id, count) in enumerate(leaderboard, start=1):
            try:
                user = await client.get_users(user_id)
                name = user.mention
            except:
                name = f"[User](tg://user?id={user_id})"
            text += f"**{rank}.** {name} — `{count}` renames\n"

        await query.message.edit(
            text,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="help")]
            ])
        )

    elif data == "close":
        try:
            await query.message.delete()
            if query.message.reply_to_message:
                await query.message.reply_to_message.delete()
        except:
            pass

    elif data.startswith("sendAlert"):
        user_id = int(data.split("_")[1].strip())
        reason = str(data.split("_")[2])
        try:
            await client.send_message(user_id, f"<b>ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ ʙʏ [ʀᴀʜᴜʟ](https://telegram.me/callownerbot)\nʀᴇᴀsᴏɴ : {reason}</b>")
            await query.message.edit(f"<b>Aʟᴇʀᴛ sᴇɴᴛ ᴛᴏ <code>{user_id}</code>\nʀᴇᴀsᴏɴ : {reason}</b>")
        except Exception as e:
            await query.message.edit(f"<b>sʀʏ ɪ ɢᴏᴛ ᴛʜɪs ᴇʀʀᴏʀ : {e}</b>")

    elif data.startswith('noAlert'):
        user_id = int(data.split("_")[1].strip())
        await query.message.edit(f"<b>Tʜᴇ ʙᴀɴ ᴏɴ <code>{user_id}</code> ᴡᴀs ᴇxᴇᴄᴜᴛᴇᴅ sɪʟᴇɴᴛʟʏ.</b>")

    elif data.startswith('sendUnbanAlert'):
        user_id = int(data.split("_")[1].strip())
        try:
            unban_text = "<b>ʜᴜʀʀᴀʏ..ʏᴏᴜ ᴀʀᴇ ᴜɴʙᴀɴɴᴇᴅ ʙʏ [ʀᴀʜᴜʟ](https://telegram.me/callownerbot)</b>"
            await client.send_message(user_id, unban_text)
            await query.message.edit(f"<b>Uɴʙᴀɴɴᴇᴅ Aʟᴇʀᴛ sᴇɴᴛ ᴛᴏ <code>{user_id}</code>\nᴀʟᴇʀᴛ ᴛᴇxᴛ : {unban_text}</b>")
        except Exception as e:
            await query.message.edit(f"<b>sʀʏ ɪ ɢᴏᴛ ᴛʜɪs ᴇʀʀᴏʀ : {e}</b>")

    elif data.startswith('NoUnbanAlert'):
        user_id = int(data.split("_")[1].strip())
        await query.message.edit(f"Tʜᴇ ᴜɴʙᴀɴ ᴏɴ <code>{user_id}</code> ᴡᴀs ᴇxᴇᴄᴜᴛᴇᴅ sɪʟᴇɴᴛʟʏ.")


# ========== leaderboard command handler ==============#
@Client.on_message(filters.command("leaderboard") & filters.private)
async def leaderboard_handler(client, message):
    top_users = await jishubotz.get_leaderboard(limit=10)

    if not top_users:
        return await message.reply("🏆 Leaderboard is currently empty.")

    text = "🏆 <b>Top 10 Renamers:</b>\n\n"
    for i, user in enumerate(top_users, start=1):
        try:
            mention = f"<a href='tg://user?id={user['_id']}'>User</a>"
        except Exception:
            mention = f"<code>{user['_id']}</code>"
        count = user.get('rename_count', 0)
        text += f"{i}. {mention} — <b>{count}</b> renames\n"

    await message.reply(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)