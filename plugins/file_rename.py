from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from helper.ffmpeg import fix_thumb, take_screen_shot, add_metadata
from helper.utils import progress_for_pyrogram, convert, humanbytes, add_prefix_suffix
from helper.database import jishubotz
from asyncio import sleep
from PIL import Image
from config import Config
import os, time, re, random, asyncio


@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def rename_start(client, message):
    file = getattr(message, message.media.value)
    filename = file.file_name
    user_id = message.from_user.id

    # 🚫 Check banned
    if await jishubotz.is_banned(user_id):
        return await message.reply("🚫 You are banned. Contact @CallOwnerBot to appeal.")

    # 🪙 Token limit check (if not premium)
    is_premium = await jishubotz.is_premium(user_id)
    if not is_premium:
        tokens = await jishubotz.get_token(user_id)
        if tokens <= 0:
            return await message.reply(
                "🚫 **Token Limit Reached!**\nYou have no tokens left.\n\n💎 Upgrade to Premium or refer friends to earn tokens.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💎 Buy Premium", url="https://t.me/CallOwnerBot")
                ]])
            )

    # ⚠️ Check file size limit
    if file.file_size > 2 * 1024 * 1024 * 1024:
        return await message.reply_text("❌ File size exceeds 2GB limit.")

    try:
        await message.reply_text(
            f"📝 **Send new file name**\n\n📂 Old Name: `{filename}`",
            reply_to_message_id=message.id,
            reply_markup=ForceReply(True)
        )
    except FloodWait as e:
        await sleep(e.value)

    await asyncio.sleep(600)
    await message.delete()


@Client.on_message(filters.private & filters.reply)
async def refunc(client, message):
    reply = message.reply_to_message
    if not reply or not isinstance(reply.reply_markup, ForceReply):
        return

    new_name = message.text.strip()
    await message.delete()

    original = reply.reply_to_message
    if not original:
        return

    media = getattr(original, original.media.value)
    if not "." in new_name:
        ext = media.file_name.rsplit('.', 1)[-1] if "." in media.file_name else "mkv"
        new_name += f".{ext}"

    await reply.delete()

    buttons = [[InlineKeyboardButton("📁 Document", callback_data="upload_document")]]
    if original.media in [MessageMediaType.VIDEO, MessageMediaType.DOCUMENT]:
        buttons.append([InlineKeyboardButton("🎥 Video", callback_data="upload_video")])
    elif original.media == MessageMediaType.AUDIO:
        buttons.append([InlineKeyboardButton("🎵 Audio", callback_data="upload_audio")])

    await message.reply(
        f"✅ **Choose upload type**\n\n📦 File: `{new_name}`",
        reply_to_message_id=original.id,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@Client.on_callback_query(filters.regex(r"upload_"))
async def upload_media(bot, update):
    if not os.path.isdir("Metadata"):
        os.makedirs("Metadata")

    user_id = update.from_user.id
    file_msg = update.message.reply_to_message

    try:
        prefix = await jishubotz.get_prefix(user_id)
        suffix = await jishubotz.get_suffix(user_id)
        new_name = update.message.text.split(":-")[1].strip()
        new_name = add_prefix_suffix(new_name, prefix, suffix)
    except Exception as e:
        return await update.message.edit(f"❌ Error applying prefix/suffix: `{e}`")

    file_path = f"downloads/{user_id}/{new_name}"

    try:
        ms = await update.message.edit("📥 Downloading file...")
        path = await bot.download_media(
            file_msg, file_path,
            progress=progress_for_pyrogram,
            progress_args=("📥 Downloading...", ms, time.time())
        )
    except Exception as e:
        return await ms.edit(f"Download error: `{e}`")

    # 📦 Metadata mode
    metadata_enabled = await jishubotz.get_metadata(user_id)
    metadata_path = f"Metadata/{new_name}" if metadata_enabled else file_path
    if metadata_enabled:
        meta = await jishubotz.get_metadata_code(user_id)
        await add_metadata(file_path, metadata_path, meta, ms)

    # ⏱ Duration
    duration = 0
    try:
        parser = createParser(file_path)
        metadata = extractMetadata(parser)
        if metadata and metadata.has("duration"):
            duration = metadata.get('duration').seconds
        parser.close()
    except:
        pass

    # 🖼️ Thumbnail
    ph_path = None
    media = getattr(file_msg, file_msg.media.value)
    c_caption = await jishubotz.get_caption(user_id)
    c_thumb = await jishubotz.get_thumbnail(user_id)

    if c_caption:
        try:
            caption = c_caption.format(
                filename=new_name,
                filesize=humanbytes(media.file_size),
                duration=convert(duration)
            )
        except Exception as e:
            return await ms.edit(f"⚠️ Caption formatting error: `{e}`")
    else:
        caption = f"**{new_name}**\n👤 {update.message.chat.first_name}\n🆔 `{user_id}`"

    try:
        if c_thumb:
            ph_path = await bot.download_media(c_thumb)
            _, _, ph_path = await fix_thumb(ph_path)
        else:
            ph_path_ = await take_screen_shot(file_path, os.path.dirname(file_path), random.randint(0, duration - 1))
            _, _, ph_path = await fix_thumb(ph_path_)
    except Exception as e:
        print(f"Thumbnail error: {e}")

    await ms.edit("📤 Uploading...")

    file_to_send = metadata_path if metadata_enabled else file_path
    upload_type = update.data.split("_")[1]

    try:
        if upload_type == "document":
            sent = await bot.send_document(
                user_id,
                document=file_to_send,
                thumb=ph_path,
                caption=caption,
                progress=progress_for_pyrogram,
                progress_args=("📤 Uploading...", ms, time.time())
            )
        elif upload_type == "video":
            sent = await bot.send_video(
                user_id,
                video=file_to_send,
                thumb=ph_path,
                caption=caption,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("📤 Uploading...", ms, time.time())
            )
        elif upload_type == "audio":
            sent = await bot.send_audio(
                user_id,
                audio=file_to_send,
                thumb=ph_path,
                caption=caption,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("📤 Uploading...", ms, time.time())
            )

        # 📤 Forward to BIN_CHANNEL
        await bot.forward_messages(Config.BIN_CHANNEL, user_id, sent.id)

        # 🔁 Reduce token (if not premium)
        if not await jishubotz.is_premium(user_id):
            await jishubotz.reduce_token(user_id)

        delete_note = await sent.reply("🗑 This file will auto-delete in 30 minutes.")
        await ms.delete()

    except Exception as e:
        return await ms.edit(f"❌ Upload failed: `{e}`")

    try:
        await asyncio.sleep(1800)
        await sent.delete()
        await delete_note.delete()
    except Exception as e:
        print(f"Auto-delete error: {e}")

    try:
        if ph_path: os.remove(ph_path)
        if file_path: os.remove(file_path)
        if metadata_enabled and os.path.exists(metadata_path): os.remove(metadata_path)
    except:
        pass