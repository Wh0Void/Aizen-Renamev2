<div align="center">

<!-- Animated Wave Header -->
<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f0c29,50:302b63,100:00d2ff&height=220&section=header&text=%E2%9F%90%20COSMIC%20RENAME%202GB%20BOT%20%E2%9F%90&fontSize=36&fontColor=ffffff&animation=fadeIn&fontAlignY=36&desc=%E2%9C%A6%20Next-Gen%20High-Speed%20Telegram%20File%20%26%20Media%20Renamer%20%E2%9C%A6&descAlignY=58&descSize=17" width="100%" alt="CosmicBotz Banner"/>

<!-- Animated Typing SVG -->
<a href="https://telegram.me/CosmicBotz">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=20&duration=3000&pause=900&color=00E5FF&center=true&vCenter=true&repeat=true&width=780&height=45&lines=%E2%97%88+Ultra-Fast+2GB+Telegram+File+%26+Video+Renamer;%E2%9F%90+Smart+Auto+Video-Frame+Thumbnail+Extractor;%E2%8C%AC+Custom+FFmpeg+Stream+Metadata+%26+Tag+Editor;%E2%9F%A1+Auto-Forward+Renamed+Files+To+Your+Channel;%E2%9C%A6+Engineered+By+%40CosmicBotz" alt="Typing SVG" />
</a>

<br/>

<!-- Modern Shields.io Badges -->
<p align="center">
  <a href="https://telegram.me/CosmicBotz">
    <img src="https://img.shields.io/badge/Telegram-@CosmicBotz-0088cc?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram Channel"/>
  </a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/MongoDB-Atlas-47A248?style=for-the-badge&logo=mongodb&logoColor=white" alt="MongoDB"/>
  <img src="https://img.shields.io/badge/FFmpeg-Supported-007808?style=for-the-badge&logo=ffmpeg&logoColor=white" alt="FFmpeg"/>
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"/>
</p>

</div>

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%">

## ❖ ᴋᴇʏ ꜰᴇᴀᴛᴜʀᴇs

| ◈ Feature | ▸ Description |
| :--- | :--- |
| **⟡ 2GB File Renaming** | Seamlessly rename any Telegram file, video, or audio up to **2 GB** with real-time progress tracking. |
| **⇄ Format Conversion** | Convert between **▣ Document**, **▷ Video**, and **♪ Audio** output modes with a single tap. |
| **⟐ Smart Auto-Thumbnail** | Set a custom permanent thumbnail, or let the bot **automatically extract a non-blank HD video frame (~30s)** when no thumbnail is set. |
| **⌘ Prefix & Suffix** | Automatically prepend or append custom tags (e.g. `@CosmicBotz`) to every renamed file. |
| **✎ Dynamic Captions** | Create rich custom captions with `{filename}`, `{filesize}`, and `{duration}` variables. |
| **⌬ Stream Metadata** | Inject custom `title`, `author`, `artist`, video, audio, and subtitle stream tags via FFmpeg. |
| **⏣ Destination Channel** | Link your channel once and automatically forward every renamed file directly to it. |
| **★ User Leaderboard** | Built-in live leaderboard tracking top users by total renamed files. |
| **⛨ Admin Control Suite** | Full Force-Subscribe, Broadcast, Ban/Unban with alerts, user count, and live system telemetry. |

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%">

## ❖ ᴏɴᴇ-ᴄʟɪᴄᴋ & ᴄʟᴏᴜᴅ ᴅᴇᴘʟᴏʏᴍᴇɴᴛ

<div align="center">

| ◈ Render | ◈ Koyeb | ◈ Heroku |
| :---: | :---: | :---: |
| [![Deploy to Render](https://img.shields.io/badge/Deploy%20to-Render-46E3B7?style=for-the-badge&logo=render&logoColor=black)](https://render.com/deploy) | [![Deploy to Koyeb](https://img.shields.io/badge/Deploy%20to-Koyeb-121212?style=for-the-badge&logo=koyeb&logoColor=white)](https://app.koyeb.com/deploy) | [![Deploy to Heroku](https://img.shields.io/badge/Deploy%20to-Heroku-430098?style=for-the-badge&logo=heroku&logoColor=white)](https://heroku.com/deploy) |

</div>

<details>
<summary><b>▸ ᴅᴇᴘʟᴏʏ ᴡɪᴛʜ ᴅᴏᴄᴋᴇʀ (ᴄʟɪᴄᴋ ᴛᴏ ᴇxᴘᴀɴᴅ)</b></summary>
<br/>

```bash
# 1. Clone the repository
git clone https://github.com/CosmicBotz/Rename-2gb-bot.git
cd Rename-2gb-bot

# 2. Configure your environment variables
cp .env.example .env

# 3. Build and run the container
docker build -t cosmic-rename-bot .
docker run -d --env-file .env -p 8000:8000 --name cosmic-rename-bot cosmic-rename-bot
```
</details>

<details>
<summary><b>▸ ʟᴏᴄᴀʟ / ᴠᴘs ᴅᴇᴘʟᴏʏᴍᴇɴᴛ (ᴄʟɪᴄᴋ ᴛᴏ ᴇxᴘᴀɴᴅ)</b></summary>
<br/>

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .\.venv\Scripts\activate       # Windows PowerShell

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up .env and start the bot
cp .env.example .env
python bot.py
```
</details>

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%">

## ❖ ᴇɴᴠɪʀᴏɴᴍᴇɴᴛ ᴠᴀʀɪᴀʙʟᴇs

| ◈ Variable | ◈ Status | ▸ Description |
| :--- | :---: | :--- |
| `API_ID` | **● Required** | Your Telegram API ID from [my.telegram.org](https://my.telegram.org). |
| `API_HASH` | **● Required** | Your Telegram API Hash from [my.telegram.org](https://my.telegram.org). |
| `BOT_TOKEN` | **● Required** | Your Bot Token from [@BotFather](https://telegram.me/BotFather). |
| `ADMIN` | **● Required** | Space-separated Telegram User IDs of bot admins (e.g. `123456789 987654321`). |
| `DB_URL` | **● Required** | MongoDB Atlas connection URI. |
| `LOG_CHANNEL` | **● Required** | Log Channel ID (`-100xxxxxxxxxx`) where bot logs & new users are reported. |
| `BIN_CHANNEL` | **● Required** | Storage/Bin Channel ID (`-100xxxxxxxxxx`) where renamed files are archived. |
| `DB_NAME` | *○ Optional* | MongoDB database name (defaults to `CosmicBotz`). |
| `FORCE_SUB` | *○ Optional* | Force Subscribe channel username without `@` (e.g. `CosmicBotz`). |
| `START_PIC` | *○ Optional* | Direct image URL for the `/start` welcome banner. |
| `STICKER_ID` | *○ Optional* | Telegram Sticker File ID sent before the `/start` message. |
| `WEBHOOK` | *○ Optional* | Set `True` to enable the built-in health-check web server (default `True`). |
| `PORT` | *○ Optional* | Web server port for cloud health checks (default `8000`). |

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%">

## ❖ ʙᴏᴛ ᴄᴏᴍᴍᴀɴᴅs

| ◈ Command | ◈ Scope | ▸ Description |
| :--- | :---: | :--- |
| `/start` | `✦ User` | Start the bot & display the interactive control panel |
| `/help` | `✦ User` | Open the modules & settings guide |
| `/viewthumb` / `/delthumb` | `✦ User` | View or delete your saved custom thumbnail |
| `/set_caption` / `/see_caption` / `/del_caption` | `✦ User` | Set, view, or remove your custom file caption |
| `/set_prefix` / `/see_prefix` / `/del_prefix` | `✦ User` | Set, view, or remove your custom filename prefix |
| `/set_suffix` / `/see_suffix` / `/del_suffix` | `✦ User` | Set, view, or remove your custom filename suffix |
| `/metadata` | `✦ User` | Toggle & customize FFmpeg stream metadata tags |
| `/setchannel` / `/adddestination` | `✦ User` | Configure automatic destination channel forwarding |
| `/viewdestination` / `/deldestination` | `✦ User` | View or remove your active destination channel |
| `/leaderboard` | `✦ User` | View the top renamers leaderboard |
| `/system` / `/sys` | `✦ User / ⛨ Admin` | View safe live CPU, RAM, Disk, Uptime & Ping stats |
| `/ping` | `✦ User` | Check live bot response latency |
| `/status` | `⛨ Admin` | View bot uptime, ping, user count & system status |
| `/users` / `/banned` | `⛨ Admin` | View total registered or banned user counts |
| `/ban` / `/unban` | `⛨ Admin` | Ban or unban a user with optional alert notification |
| `/broadcast` | `⛨ Admin` | Broadcast a replied message to all registered users |
| `/restart` | `⛨ Admin` | Restart the bot process |

<details>
<summary><b>▸ ᴄᴏᴘʏ-ᴘᴀsᴛᴇ ᴄᴏᴍᴍᴀɴᴅs ꜰᴏʀ @BotFather (ᴄʟɪᴄᴋ ᴛᴏ ᴇxᴘᴀɴᴅ)</b></summary>
<br/>

```text
start - ⟡ Start the bot & open main menu
help - ❖ Open modules & configuration guide
viewthumb - ⟐ View your saved custom thumbnail
delthumb - ✕ Delete your custom thumbnail
set_caption - ✎ Set a custom file caption
see_caption - ◈ View your current caption
del_caption - ✕ Delete your custom caption
metadata - ⌬ Configure FFmpeg stream metadata
set_prefix - ⌘ Set custom filename prefix
see_prefix - ◈ View your filename prefix
del_prefix - ✕ Delete your filename prefix
set_suffix - ⌘ Set custom filename suffix
see_suffix - ◈ View your filename suffix
del_suffix - ✕ Delete your filename suffix
setchannel - ⏣ Interactive destination channel setup
adddestination - ✚ Set destination channel by ID
viewdestination - ◈ View active destination channel
deldestination - ✕ Remove destination channel
leaderboard - ★ View top renamers leaderboard
system - ◈ View live system & resource stats
ping - ⟡ Check bot latency
status - ◈ View bot system stats [Admin]
users - ✦ View total registered users [Admin]
banned - ⊘ View banned users list [Admin]
ban - ⊘ Ban a user [Admin]
unban - ✓ Unban a user [Admin]
broadcast - » Broadcast message to users [Admin]
restart - ↻ Restart the bot [Admin]
```
</details>

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%">

## ❖ ᴄʀᴇᴅɪᴛs & ᴄᴏᴍᴍᴜɴɪᴛʏ

<div align="center">

<a href="https://telegram.me/CosmicBotz">
  <img src="https://img.shields.io/badge/Developed%20By-CosmicBotz-7F00FF?style=for-the-badge&logo=telegram&logoColor=white" alt="Developed by CosmicBotz"/>
</a>
<a href="https://telegram.me/CosmicBotz">
  <img src="https://img.shields.io/badge/Updates%20Channel-@CosmicBotz-00C9FF?style=for-the-badge&logo=telegram&logoColor=white" alt="Updates Channel"/>
</a>

<!-- Animated Wave Footer -->
<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f0c29,50:302b63,100:00d2ff&height=120&section=footer" width="100%" alt="Footer Wave"/>

</div>
