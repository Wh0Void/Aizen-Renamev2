<h1 align="center">
 <b><a href="https://telegram.me/CosmicBotz" target="_blank">⚡ CosmicBotz — High-Speed 2GB Rename Bot</a></b>
</h1>

<p align="center">🚀 Powered by <b>Wzgram v3.1.1</b> + <b>Multi-Session Connection Pool (6–8 TCP Streams)</b> + <b>Dual-Tier Smart RAM Cache</b> 🚀</p>

---

### ⚡ HIGH-SPEED ARCHITECTURE

- **Wzgram Framework (`wzgram==3.1.1`)**: Built-in native `ask()` / `listen()` listeners, lazy TL schema loading (~50% lower baseline RAM), and Rust `WarpCrypto` hardware-accelerated AES-NI encryption.
- **Multi-Session Connection Pool (`bot/core/fast_crypto.py`)**: Overcomes Telegram's ~3–5 MB/s per-socket cap by spawning **6 to 8 parallel TCP media sessions** (`Session(..., is_media=True)`) and distributing **512 KB chunks** across all connections simultaneously (achieving 30–50+ MB/s on Linux VPS).
- **Dual-Tier Memory & RAM Cache (`bot/core/cache.py`)**:
  - **Tier 1 (In-Memory LRU + TTL Cache)**: Caches MongoDB user profiles, prefix/suffix/caption/metadata settings, ban status, force-sub checks, and normalized 320x320 JPEG thumbnails in RAM.
  - **Tier 2 (Smart `/dev/shm` RAM-Disk Router)**: Routes thumbnails and small files through Linux `/dev/shm` RAM disk while automatically falling back to disk with strictly bounded read-ahead buffers for large 2 GB files on **Render** (512 MB RAM) and **Koyeb**.

---

### 🔥 ENVIRONMENT VARIABLES

* `API_ID` - Your Telegram API ID from [my.telegram.org](https://my.telegram.org).
* `API_HASH` - Your Telegram API HASH from [my.telegram.org](https://my.telegram.org).
* `BOT_TOKEN` - Bot token from [@BotFather](https://telegram.me/BotFather).
* `ADMIN` - Space-separated Telegram user IDs of bot admins.
* `DB_URL` - MongoDB connection URI.
* `DB_NAME` - MongoDB database name.
* `FORCE_SUB` - Force subscribe channel username without `@` (e.g. `CosmicBotz`).
* `LOG_CHANNEL` - Log Channel ID (`-100...`).
* `BIN_CHANNEL` - Bin Channel ID (`-100...`).
* `START_PIC` - Start message photo URL.
* `MEDIA_POOL_SIZE` - Parallel TCP media sessions per DC (default `6`, max `8`).
* `RAM_CACHE_MAX_MB` - Max file size in MB routed via `/dev/shm` RAM disk (default `40`).

---

### 😍 COMMANDS

```text
start - Check if the bot is running
help - Open interactive help menu
viewthumb - View current custom thumbnail
delthumb - Delete current custom thumbnail
set_caption - Set a custom caption
see_caption - View your custom caption
del_caption - Delete custom caption
metadata - Configure custom FFmpeg media metadata
set_prefix - Set filename prefix
see_prefix - View filename prefix
del_prefix - Delete filename prefix
set_suffix - Set filename suffix
see_suffix - View filename suffix
del_suffix - Delete filename suffix
setchannel - Interactive destination channel setup
adddestination - Set destination channel ID
removedestination - Remove destination channel
listdestinations - View current destination channel
leaderboard - View top renamers leaderboard
ping - Check bot latency
status - Live Multi-Session Pool & RAM Cache telemetry [ADMIN]
users - View total registered users [ADMIN]
banned - View banned users list [ADMIN]
ban - Ban a user [ADMIN]
unban - Unban a user [ADMIN]
broadcast - Broadcast a message to all users [ADMIN]
restart - Restart the bot [ADMIN]
```

---

### 🥳 CREDIT & DEVELOPER

- **Developer**: [CosmicBotz](https://telegram.me/CosmicBotz)
- **Channel**: [@CosmicBotz](https://telegram.me/CosmicBotz)
