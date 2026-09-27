from pyrogram import Client, filters
from helper.database import Mythicbotz


@Client.on_message(filters.private & filters.command(["view_thumb", "viewthumb"]))
async def viewthumb(client, message):
    thumb = await Mythicbotz.get_thumbnail(message.from_user.id)
    if thumb:
        await client.send_photo(
            chat_id=message.chat.id,
            photo=thumb,
            caption=(
                "<blockquote>🖼️ <b>ʏᴏᴜʀ ᴄᴜsᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ</b></blockquote>\n"
                "╰─▸ <i>ᴜsᴇ</i> <code>/del_thumb</code> <i>ᴛᴏ ʀᴇᴍᴏᴠᴇ ɪᴛ.</i>"
            ),
        )
    else:
        await message.reply_text(
            "<blockquote>❌ <b>ɴᴏ ᴄᴜsᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ sᴇᴛ</b></blockquote>\n"
            "╭─▸ <i>ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ sᴇᴛ ᴀ ᴄᴜsᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ ʏᴇᴛ.</i>\n"
            "╰─▸ 🎬 <b>ᴀᴜᴛᴏ-ᴛʜᴜᴍʙ :</b> <code>ᴀᴄᴛɪᴠᴇ (ᴇxᴛʀᴀᴄᴛs ᴠɪᴅᴇᴏ ꜰʀᴀᴍᴇ ᴀᴛ ~30s)</code>"
        )


@Client.on_message(filters.private & filters.command(["del_thumb", "delthumb"]))
async def removethumb(client, message):
    await Mythicbotz.set_thumbnail(message.from_user.id, file_id=None)
    await message.reply_text(
        "<blockquote>🗑️ <b>ᴛʜᴜᴍʙɴᴀɪʟ ᴅᴇʟᴇᴛᴇᴅ</b></blockquote>\n"
        "╭─▸ <i>ᴄᴜsᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ ʀᴇᴍᴏᴠᴇᴅ sᴜᴄᴄᴇssꜰᴜʟʟʏ.</i>\n"
        "╰─▸ 🎬 <b>ᴀᴜᴛᴏ-ᴛʜᴜᴍʙ :</b> <code>ᴇɴᴀʙʟᴇᴅ ꜰᴏʀ ᴠɪᴅᴇᴏs</code>"
    )


@Client.on_message(filters.private & filters.photo)
async def addthumbs(client, message):
    mkn = await message.reply_text("<blockquote>⏳ <b>sᴀᴠɪɴɢ ᴛʜᴜᴍʙɴᴀɪʟ...</b></blockquote>")
    await Mythicbotz.set_thumbnail(message.from_user.id, file_id=message.photo.file_id)
    await mkn.edit(
        "<blockquote>✅ <b>ᴛʜᴜᴍʙɴᴀɪʟ sᴀᴠᴇᴅ</b></blockquote>\n"
        "╰─▸ <i>ʏᴏᴜʀ ᴄᴜsᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ ɪs ɴᴏᴡ ᴀᴄᴛɪᴠᴇ & ᴄᴀᴄʜᴇᴅ ɪɴ ʀᴀᴍ!</i>"
    )


# Developer @CosmicBotz
# Telegram Channel @CosmicBotz

