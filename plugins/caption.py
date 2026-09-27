from pyrogram import Client, filters
from helper.database import Mythicbotz


@Client.on_message(filters.private & filters.command("set_caption"))
async def add_caption(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "<blockquote>📝 <b>sᴇᴛ ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ</b></blockquote>\n\n"
            "╭─▸ ⚠️ <b>ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴄᴀᴘᴛɪᴏɴ ᴛᴇᴍᴘʟᴀᴛᴇ!</b>\n"
            "╰─▸ 💡 <b>ᴇxᴀᴍᴘʟᴇ :</b>\n"
            "<code>/set_caption 📕 ɴᴀᴍᴇ : {filename}\n📦 sɪᴢᴇ : {filesize}\n⏰ ᴅᴜʀᴀᴛɪᴏɴ : {duration}</code>"
        )
    caption = message.text.split(" ", 1)[1]
    await Mythicbotz.set_caption(message.from_user.id, caption=caption)
    await message.reply_text(
        "<blockquote>✅ <b>ᴄᴀᴘᴛɪᴏɴ sᴀᴠᴇᴅ</b></blockquote>\n"
        "╰─▸ <i>ʏᴏᴜʀ ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ ʜᴀs ʙᴇᴇɴ sᴜᴄᴄᴇssꜰᴜʟʟʏ ᴜᴘᴅᴀᴛᴇᴅ!</i>"
    )


@Client.on_message(filters.private & filters.command("del_caption"))
async def delete_caption(client, message):
    caption = await Mythicbotz.get_caption(message.from_user.id)
    if not caption:
        return await message.reply_text(
            "<blockquote>❌ <b>ɴᴏ ᴄᴀᴘᴛɪᴏɴ ꜰᴏᴜɴᴅ</b></blockquote>\n"
            "╰─▸ <i>ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ sᴇᴛ.</i>"
        )
    await Mythicbotz.set_caption(message.from_user.id, caption=None)
    await message.reply_text(
        "<blockquote>🗑️ <b>ᴄᴀᴘᴛɪᴏɴ ᴅᴇʟᴇᴛᴇᴅ</b></blockquote>\n"
        "╰─▸ <i>ʏᴏᴜʀ ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ ʜᴀs ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ.</i>"
    )


@Client.on_message(filters.private & filters.command("see_caption"))
async def see_caption(client, message):
    caption = await Mythicbotz.get_caption(message.from_user.id)
    if caption:
        await message.reply_text(
            "<blockquote>📝 <b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴄᴀᴘᴛɪᴏɴ</b></blockquote>\n\n"
            f"<code>{caption}</code>"
        )
    else:
        await message.reply_text(
            "<blockquote>❌ <b>ɴᴏ ᴄᴀᴘᴛɪᴏɴ ꜰᴏᴜɴᴅ</b></blockquote>\n"
            "╰─▸ <i>ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ sᴇᴛ.</i>"
        )


# Developer @CosmicBotz
# Telegram Channel @CosmicBotz

