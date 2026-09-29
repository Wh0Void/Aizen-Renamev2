import os, time, re
from dotenv import load_dotenv

load_dotenv()

id_pattern = re.compile(r'^.\d+$')


class Config(object):
    # pyro client config
    API_ID    = os.environ.get("API_ID", "")
    API_HASH  = os.environ.get("API_HASH", "")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "") 
    STRING_SESSION = os.environ.get("STRING_SESSION", "")  # Optional Premium/4GB user session
    HELPER_SESSION = os.environ.get("HELPER_SESSION", "")  # Optional user session for faster MTProto DL/UL
    STICKER_ID = "CAACAgUAAxkBAAEPPyForea7mUMyTQegrzwcdE7GyOR9LQAC3BYAAqqMAAFXZzpttZeEZiQ2BA"  # Replace with actual sticker file ID
   
    # database config
    DB_NAME = os.environ.get("DB_NAME","")     
    DB_URL  = os.environ.get("DB_URL","")

    # other configs
    BOT_UPTIME  = time.time()
    START_PIC   = os.environ.get("START_PIC", "https://graph.org/file/c54d1c60ba3ef2d4913de-82ed8fe7a03b824dc0.jpg")
    ADMIN = [int(admin) if id_pattern.search(admin) else admin for admin in os.environ.get('ADMIN', '6617544956').split()]

    # channels logs
    FORCE_SUB   = os.environ.get("FORCE_SUB", "CosmicBotz") 
    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", ""))
    BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL", ""))

    # wes response configuration     
    WEBHOOK = bool(os.environ.get("WEBHOOK", True))


    # 🔐 TOKEN SYSTEM
    TOKEN_TIME = 12   # ⏰ 12 hours in seconds
    SHORTLINK_API = os.getenv("SHORTLINK_API", "242fb1e2951cdf981a8")
    SHORTLINK_DOMAIN = "http://seturl.in"  # 🌐 Shortener base URL

    # ⚡ High-Speed Multi-Session Pool & Smart RAM Cache Configs (Auto-Rename High Performance Profile)
    MEDIA_POOL_SIZE = int(os.environ.get("MEDIA_POOL_SIZE", "12"))  # Up to 12-24 parallel TCP media sessions for multi-file concurrency
    RAM_CACHE_MAX_MB = int(os.environ.get("RAM_CACHE_MAX_MB", "128"))  # Max file size (MB) routed through /dev/shm when free RAM allows
    USER_CACHE_TTL = int(os.environ.get("USER_CACHE_TTL", "1800"))  # In-memory user DB cache TTL in seconds
    WZGRAM_MAX_READ_AHEAD = int(os.environ.get("WZGRAM_MAX_READ_AHEAD", "256"))  # 256 read-ahead slots for smooth pipelined streaming



class Txt(object):
    # Premium Modern UI Text Configuration
    START_TXT = """<blockquote>✨ <b>ʜᴇʏ {}, ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴄᴏsᴍɪᴄ ʀᴇɴᴀᴍᴇʀ ⚡</b></blockquote>

<blockquote><b>❝ ᴜʟᴛʀᴀ-ꜰᴀsᴛ 𝟸ɢʙ ꜰɪʟᴇ ʀᴇɴᴀᴍᴇʀ & ᴍᴇᴅɪᴀ ᴇɴɢɪɴᴇ ❞</b></blockquote>

<b>🚀 ᴡʜᴀᴛ ɪ ᴄᴀɴ ᴅᴏ :</b>
╭─ 📁 <b>ʀᴇɴᴀᴍᴇ :</b> <code>ʜɪɢʜ-sᴘᴇᴇᴅ ᴍᴜʟᴛɪ-sᴇssɪᴏɴ ᴛʀᴀɴsꜰᴇʀs</code>
├─ 🖼️ <b>ᴛʜᴜᴍʙɴᴀɪʟ :</b> <code>ᴄᴜsᴛᴏᴍ ᴏʀ ᴀᴜᴛᴏ ᴠɪᴅᴇᴏ-ꜰʀᴀᴍᴇ ᴇxᴛʀᴀᴄᴛ</code>
├─ 🎞️ <b>ᴄᴏɴᴠᴇʀᴛ :</b> <code>ᴅᴏᴄᴜᴍᴇɴᴛ ⇄ ᴠɪᴅᴇᴏ ⇄ ᴀᴜᴅɪᴏ</code>
├─ 🏷️ <b>ꜰᴏʀᴍᴀᴛ :</b> <code>ᴄᴜsᴛᴏᴍ ᴘʀᴇꜰɪx, sᴜꜰꜰɪx & ᴄᴀᴘᴛɪᴏɴs</code>
╰─ ⚙️ <b>ᴍᴇᴛᴀᴅᴀᴛᴀ :</b> <code>sᴛʀᴇᴀᴍ-ʟᴇᴠᴇʟ ꜰꜰᴍᴘᴇɢ ᴛᴀɢ ɪɴᴊᴇᴄᴛɪᴏɴ</code>

<blockquote>⚠️ <b>ɴᴏᴛᴇ :</b> ʀᴇɴᴀᴍɪɴɢ ᴏʀ sʜᴀʀɪɴɢ <u>ᴀᴅᴜʟᴛ / ɴsꜰᴡ ᴄᴏɴᴛᴇɴᴛ</u> ɪs <b>sᴛʀɪᴄᴛʟʏ ᴘʀᴏʜɪʙɪᴛᴇᴅ</b>.
⚡ <b>ᴘᴏᴡᴇʀᴇᴅ ʙʏ :</b> <a href='https://telegram.me/CosmicBotz'>@CosmicBotz</a></blockquote>"""

    ABOUT_TXT = """<blockquote>⚡ <b>ᴀʙᴏᴜᴛ ᴄᴏsᴍɪᴄ ʀᴇɴᴀᴍᴇ ᴇɴɢɪɴᴇ</b></blockquote>

╭─ 🤖 <b>ʙᴏᴛ ɴᴀᴍᴇ :</b> <a href='https://telegram.me/CosmicBotz'>ʀᴇɴᴀᴍᴇ 𝟸ɢʙ ʙᴏᴛ</a>
├─ 🚀 <b>ꜰʀᴀᴍᴇᴡᴏʀᴋ :</b> <code>ᴡᴢɢʀᴀᴍ ᴠ𝟹.𝟷.𝟷 (ᴍᴜʟᴛɪ-sᴇssɪᴏɴ)</code>
├─ 🔐 <b>ᴄʀʏᴘᴛᴏ :</b> <code>ᴡᴀʀᴘᴄʀʏᴘᴛᴏ (ʀᴜsᴛ ᴀᴇs-ɴɪ)</code>
├─ 🧠 <b>ᴄᴀᴄʜᴇ :</b> <code>ᴅᴜᴀʟ-ᴛɪᴇʀ ʀᴀᴍ + /dev/shm</code>
├─ 🗄️ <b>ᴅᴀᴛᴀʙᴀsᴇ :</b> <code>ᴍᴏɴɢᴏᴅʙ ᴀᴛʟᴀs</code>
├─ ☁️ <b>ᴄʟᴏᴜᴅ :</b> <code>ʀᴇɴᴅᴇʀ / ᴋᴏʏᴇʙ</code>
╰─ 👨‍💻 <b>ᴅᴇᴠᴇʟᴏᴘᴇʀ :</b> <a href='https://telegram.me/CosmicBotz'>CosmicBotz</a>

<blockquote>✨ <b>ᴛᴀᴘ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ʙᴇʟᴏᴡ ᴛᴏ ᴇxᴘʟᴏʀᴇ ᴍᴏʀᴇ.</b></blockquote>"""

    HELP_TXT = """<blockquote>🛠️ <b>ᴄᴏsᴍɪᴄ ʀᴇɴᴀᴍᴇʀ — ʜᴇʟᴘ & ᴍᴏᴅᴜʟᴇs</b></blockquote>

╭─ <b>𝟷. sᴇɴᴅ ᴀɴʏ ꜰɪʟᴇ / ᴠɪᴅᴇᴏ / ᴀᴜᴅɪᴏ (ᴜᴘ ᴛᴏ 𝟸ɢʙ)</b>
├─ <b>𝟸. ʀᴇᴘʟʏ ᴡɪᴛʜ ʏᴏᴜʀ ɴᴇᴡ ꜰɪʟᴇ ɴᴀᴍᴇ</b>
╰─ <b>𝟹. ᴄʜᴏᴏsᴇ ᴏᴜᴛᴘᴜᴛ ᴛʏᴘᴇ (📁 ᴅᴏᴄᴜᴍᴇɴᴛ / 🎥 ᴠɪᴅᴇᴏ / 🎵 ᴀᴜᴅɪᴏ)</b>

<blockquote>👇 <b>sᴇʟᴇᴄᴛ ᴀ ᴍᴏᴅᴜʟᴇ ʙᴇʟᴏᴡ ᴛᴏ ᴄᴏɴꜰɪɢᴜʀᴇ ʏᴏᴜʀ sᴇᴛᴛɪɴɢs :</b></blockquote>"""

    THUMBNAIL_TXT = """<blockquote>🖼️ <b>ᴄᴜsᴛᴏᴍ & ᴀᴜᴛᴏ ᴛʜᴜᴍʙɴᴀɪʟ ᴍᴏᴅᴜʟᴇ</b></blockquote>

╭─ 📸 <b>sᴇᴛ ᴛʜᴜᴍʙ :</b> <code>sᴇɴᴅ ᴀɴʏ ᴘʜᴏᴛᴏ ɪɴ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ</code>
├─ 👁️ <b>ᴠɪᴇᴡ ᴛʜᴜᴍʙ :</b> <code>/viewthumb</code> ᴏʀ <code>/view_thumb</code>
╰─ 🗑️ <b>ᴅᴇʟᴇᴛᴇ ᴛʜᴜᴍʙ :</b> <code>/delthumb</code> ᴏʀ <code>/del_thumb</code>

<blockquote>💡 <b>sᴍᴀʀᴛ ᴀᴜᴛᴏ-ꜰʀᴀᴍᴇ :</b> ɪꜰ ʏᴏᴜ ʜᴀᴠᴇ <u>ɴᴏ ᴄᴜsᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ</u> sᴀᴠᴇᴅ, ᴛʜᴇ ʙᴏᴛ <b>ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴇxᴛʀᴀᴄᴛs ᴀ ʜᴅ ꜰʀᴀᴍᴇ</b> ꜰʀᴏᴍ ʏᴏᴜʀ ᴠɪᴅᴇᴏ!</blockquote>"""

    CAPTION_TXT = """<blockquote>📝 <b>ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ ᴍᴏᴅᴜʟᴇ</b></blockquote>

<b>📌 ᴅʏɴᴀᴍɪᴄ ᴠᴀʀɪᴀʙʟᴇs :</b>
╭─ <code>{filename}</code> — <b>ɴᴇᴡ ꜰɪʟᴇ ɴᴀᴍᴇ</b>
├─ <code>{filesize}</code> — <b>ᴛᴏᴛᴀʟ ꜰɪʟᴇ sɪᴢᴇ</b>
╰─ <code>{duration}</code> — <b>ᴍᴇᴅɪᴀ ᴅᴜʀᴀᴛɪᴏɴ</b>

<b>⚙️ ᴄᴏᴍᴍᴀɴᴅs :</b>
╭─ ➕ <code>/set_caption</code> — <b>sᴀᴠᴇ ᴀ ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ</b>
├─ 👁️ <code>/see_caption</code> — <b>ᴘʀᴇᴠɪᴇᴡ ᴄᴜʀʀᴇɴᴛ ᴄᴀᴘᴛɪᴏɴ</b>
╰─ 🗑️ <code>/del_caption</code> — <b>ʀᴇᴍᴏᴠᴇ ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ</b>

<blockquote>💡 <b>ᴇxᴀᴍᴘʟᴇ :</b>
<code>/set_caption 📕 ɴᴀᴍᴇ : {filename}\n📦 sɪᴢᴇ : {filesize}\n⏱️ ᴅᴜʀᴀᴛɪᴏɴ : {duration}</code></blockquote>"""

    PREFIX = """<blockquote>🏷️ <b>ᴄᴜsᴛᴏᴍ ᴘʀᴇꜰɪx ᴍᴏᴅᴜʟᴇ</b></blockquote>

╭─ ➕ <code>/set_prefix</code> — <b>sᴇᴛ ꜰɪʟᴇɴᴀᴍᴇ ᴘʀᴇꜰɪx</b>
├─ 👁️ <code>/see_prefix</code> — <b>ᴠɪᴇᴡ ᴄᴜʀʀᴇɴᴛ ᴘʀᴇꜰɪx</b>
╰─ 🗑️ <code>/del_prefix</code> — <b>ʀᴇᴍᴏᴠᴇ ᴄᴜsᴛᴏᴍ ᴘʀᴇꜰɪx</b>

<blockquote>💡 <b>ᴇxᴀᴍᴘʟᴇ :</b>
<code>/set_prefix @CosmicBotz</code></blockquote>"""

    SUFFIX = """<blockquote>🔖 <b>ᴄᴜsᴛᴏᴍ sᴜꜰꜰɪx ᴍᴏᴅᴜʟᴇ</b></blockquote>

╭─ ➕ <code>/set_suffix</code> — <b>sᴇᴛ ꜰɪʟᴇɴᴀᴍᴇ sᴜꜰꜰɪx</b>
├─ 👁️ <code>/see_suffix</code> — <b>ᴠɪᴇᴡ ᴄᴜʀʀᴇɴᴛ sᴜꜰꜰɪx</b>
╰─ 🗑️ <code>/del_suffix</code> — <b>ʀᴇᴍᴏᴠᴇ ᴄᴜsᴛᴏᴍ sᴜꜰꜰɪx</b>

<blockquote>💡 <b>ᴇxᴀᴍᴘʟᴇ :</b>
<code>/set_suffix @CosmicBotz</code></blockquote>"""

    PROGRESS_BAR = """\n
╭─ 📦 <b>sɪᴢᴇ :</b> <code>{1} / {2}</code>
├─ 📊 <b>ᴅᴏɴᴇ :</b> <code>{0}%</code>
├─ ⚡ <b>sᴘᴇᴇᴅ :</b> <code>{3}/s</code>
╰─ ⏳ <b>ᴇᴛᴀ :</b> <code>{4}</code>
"""

    DONATE_TXT = """<blockquote>💖 <b>sᴜᴘᴘᴏʀᴛ & ᴅᴏɴᴀᴛɪᴏɴ — @CosmicBotz</b></blockquote>

<b><i>✨ ɪꜰ ʏᴏᴜ ᴇɴᴊᴏʏ ᴏᴜʀ ʜɪɢʜ-sᴘᴇᴇᴅ ʙᴏᴛs, ʏᴏᴜ ᴄᴀɴ sᴜᴘᴘᴏʀᴛ ᴏᴜʀ sᴇʀᴠᴇʀ & ᴅᴇᴠᴇʟᴏᴘᴍᴇɴᴛ ᴄᴏsᴛs!</i></b>

╭─ 💳 <b>ᴜᴘɪ ɪᴅ :</b> <code>CosmicBotz@UPI</code>
╰─ 💬 <b>ᴄᴏɴᴛᴀᴄᴛ :</b> <a href='https://telegram.me/CosmicBotz'>@CosmicBotz</a>

<blockquote>🙏 <b>ᴇᴠᴇʀʏ ᴄᴏɴᴛʀɪʙᴜᴛɪᴏɴ ᴋᴇᴇᴘs ᴏᴜʀ sᴇʀᴠᴇʀs ʙʟᴀᴢɪɴɢ ꜰᴀsᴛ!</b></blockquote>"""

    SEND_METADATA = """<blockquote>⚙️ <b>ᴄᴜsᴛᴏᴍ ᴍᴇᴛᴀᴅᴀᴛᴀ ᴄᴏɴꜰɪɢᴜʀᴀᴛɪᴏɴ</b></blockquote>

╭─ <b>sᴇɴᴅ ᴛʜᴇ ᴍᴇᴛᴀᴅᴀᴛᴀ ᴛᴇxᴛ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴇᴍʙᴇᴅ ɪɴᴛᴏ ᴀᴜᴅɪᴏ / ᴠɪᴅᴇᴏ / sᴜʙᴛɪᴛʟᴇ sᴛʀᴇᴀᴍs :</b>
╰─ 💡 <b>ᴇxᴀᴍᴘʟᴇ :</b> <code>By :- @CosmicBotz</code>

<blockquote>💬 <b>ɴᴇᴇᴅ ʜᴇʟᴘ? ᴄᴏɴᴛᴀᴄᴛ :</b> <a href='https://telegram.me/CosmicBotz'>@CosmicBotz</a></blockquote>"""
