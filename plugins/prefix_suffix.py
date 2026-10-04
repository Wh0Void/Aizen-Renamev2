from pyrogram import Client, filters
from helper.database import Mythicbotz


@Client.on_message(filters.private & filters.command("set_prefix"))
async def add_caption(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "<blockquote>🔤 <b>sᴇᴛ ᴄᴜsᴛᴏᴍ ᴘʀᴇꜰɪx</b></blockquote>\n\n"
            "╭─▸ ⚠️ <b>ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴘʀᴇꜰɪx!</b>\n"
            "╰─▸ 💡 <b>ᴇxᴀᴍᴘʟᴇ :</b> <code>/set_prefix @CosmicBotz</code>"
        )
    prefix = message.text.split(" ", 1)[1]
    ms = await message.reply_text("<blockquote>⏳ <b>sᴀᴠɪɴɢ ᴘʀᴇꜰɪx...</b></blockquote>")
    await Mythicbotz.set_prefix(message.from_user.id, prefix)
    await ms.edit(
        "<blockquote>✅ <b>ᴘʀᴇꜰɪx sᴀᴠᴇᴅ</b></blockquote>\n"
        f"╰─▸ <b>ᴘʀᴇꜰɪx :</b> <code>{prefix}</code>"
    )


@Client.on_message(filters.private & filters.command("del_prefix"))
async def delete_prefix(client, message):
    ms = await message.reply_text("<blockquote>⏳ <b>ᴄʜᴇᴄᴋɪɴɢ ᴘʀᴇꜰɪx...</b></blockquote>")
    prefix = await Mythicbotz.get_prefix(message.from_user.id)
    if not prefix:
        return await ms.edit(
            "<blockquote>❌ <b>ɴᴏ ᴘʀᴇꜰɪx ꜰᴏᴜɴᴅ</b></blockquote>\n"
            "╰─▸ <i>ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ᴄᴜsᴛᴏᴍ ᴘʀᴇꜰɪx sᴇᴛ.</i>"
        )
    await Mythicbotz.set_prefix(message.from_user.id, None)
    await ms.edit(
        "<blockquote>🗑️ <b>ᴘʀᴇꜰɪx ᴅᴇʟᴇᴛᴇᴅ</b></blockquote>\n"
        "╰─▸ <i>ʏᴏᴜʀ ᴄᴜsᴛᴏᴍ ᴘʀᴇꜰɪx ʜᴀs ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ.</i>"
    )


@Client.on_message(filters.private & filters.command("see_prefix"))
async def see_caption(client, message):
    ms = await message.reply_text("<blockquote>⏳ <b>ꜰᴇᴛᴄʜɪɴɢ ᴘʀᴇꜰɪx...</b></blockquote>")
    prefix = await Mythicbotz.get_prefix(message.from_user.id)
    if prefix:
        await ms.edit(
            "<blockquote>🔤 <b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴘʀᴇꜰɪx</b></blockquote>\n"
            f"╰─▸ <code>{prefix}</code>"
        )
    else:
        await ms.edit(
            "<blockquote>❌ <b>ɴᴏ ᴘʀᴇꜰɪx ꜰᴏᴜɴᴅ</b></blockquote>\n"
            "╰─▸ <i>ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ᴄᴜsᴛᴏᴍ ᴘʀᴇꜰɪx sᴇᴛ.</i>"
        )


# SUFFIX
@Client.on_message(filters.private & filters.command("set_suffix"))
async def add_csuffix(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "<blockquote>🔡 <b>sᴇᴛ ᴄᴜsᴛᴏᴍ sᴜꜰꜰɪx</b></blockquote>\n\n"
            "╭─▸ ⚠️ <b>ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ sᴜꜰꜰɪx!</b>\n"
            "╰─▸ 💡 <b>ᴇxᴀᴍᴘʟᴇ :</b> <code>/set_suffix @CosmicBotz</code>"
        )
    suffix = message.text.split(" ", 1)[1]
    ms = await message.reply_text("<blockquote>⏳ <b>sᴀᴠɪɴɢ sᴜꜰꜰɪx...</b></blockquote>")
    await Mythicbotz.set_suffix(message.from_user.id, suffix)
    await ms.edit(
        "<blockquote>✅ <b>sᴜꜰꜰɪx sᴀᴠᴇᴅ</b></blockquote>\n"
        f"╰─▸ <b>sᴜꜰꜰɪx :</b> <code>{suffix}</code>"
    )


@Client.on_message(filters.private & filters.command("del_suffix"))
async def delete_suffix(client, message):
    ms = await message.reply_text("<blockquote>⏳ <b>ᴄʜᴇᴄᴋɪɴɢ sᴜꜰꜰɪx...</b></blockquote>")
    suffix = await Mythicbotz.get_suffix(message.from_user.id)
    if not suffix:
        return await ms.edit(
            "<blockquote>❌ <b>ɴᴏ sᴜꜰꜰɪx ꜰᴏᴜɴᴅ</b></blockquote>\n"
            "╰─▸ <i>ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ᴄᴜsᴛᴏᴍ sᴜꜰꜰɪx sᴇᴛ.</i>"
        )
    await Mythicbotz.set_suffix(message.from_user.id, None)
    await ms.edit(
        "<blockquote>🗑️ <b>sᴜꜰꜰɪx ᴅᴇʟᴇᴛᴇᴅ</b></blockquote>\n"
        "╰─▸ <i>ʏᴏᴜʀ ᴄᴜsᴛᴏᴍ sᴜꜰꜰɪx ʜᴀs ʙᴇᴇɴ ʀᴇᴍᴏᴠᴇᴅ.</i>"
    )


@Client.on_message(filters.private & filters.command("see_suffix"))
async def see_csuffix(client, message):
    ms = await message.reply_text("<blockquote>⏳ <b>ꜰᴇᴛᴄʜɪɴɢ sᴜꜰꜰɪx...</b></blockquote>")
    suffix = await Mythicbotz.get_suffix(message.from_user.id)
    if suffix:
        await ms.edit(
            "<blockquote>🔡 <b>ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ sᴜꜰꜰɪx</b></blockquote>\n"
            f"╰─▸ <code>{suffix}</code>"
        )
    else:
        await ms.edit(
            "<blockquote>❌ <b>ɴᴏ sᴜꜰꜰɪx ꜰᴏᴜɴᴅ</b></blockquote>\n"
            "╰─▸ <i>ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀɴʏ ᴄᴜsᴛᴏᴍ sᴜꜰꜰɪx sᴇᴛ.</i>"
        )


# Developer @CosmicBotz
# Telegram Channel @CosmicBotz

