import asyncio
import inspect
import os
import sys
from datetime import datetime
from pytz import timezone
from aiohttp import web

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config import Config

from bot.core.fast_crypto import (
    FastCryptoEngine,
    MultiSessionMediaPool,
    configure_wzgram_environment,
)

# Configure WZGram native runtime environment variables before importing wzgram/pyrogram
configure_wzgram_environment(
    pool_size=getattr(Config, "MEDIA_POOL_SIZE", 32),
    max_read_ahead=getattr(Config, "WZGRAM_MAX_READ_AHEAD", 384),
)

# Install high-performance event loop (uvloop on Linux, winloop on Windows if available)
EVENT_LOOP_BACKEND = "asyncio"
if sys.platform != "win32":
    try:
        import uvloop  # type: ignore
        uvloop.install()
        asyncio.set_event_loop(uvloop.new_event_loop())
        EVENT_LOOP_BACKEND = "uvloop"
    except ImportError:
        pass
else:
    try:
        import winloop  # type: ignore
        winloop.install()
        asyncio.set_event_loop(winloop.new_event_loop())
        EVENT_LOOP_BACKEND = "winloop"
    except ImportError:
        pass

# Ensure an active event loop exists for Python 3.12+ / 3.14 compatibility
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import wzgram  # noqa: E402
sys.modules["pyrogram"] = wzgram
from wzgram import Client, __version__  # noqa: E402
import pyrogram.utils  # noqa: E402
from route import web_server  # noqa: E402


# Detect Crypto Engine
try:
    import warpcrypto  # type: ignore
    CRYPTO_BACKEND = "warpcrypto (Rust AES-NI)"
except ImportError:
    CRYPTO_BACKEND = "pycryptodome / fallback"


class Bot(Client):
    """
    High-Speed WZGram Bot Client with Native MTProto Connection Pooling,
    Hardware AES-NI Crypto (`warpcrypto`), and Low-RAM Session Storage.
    """

    def __init__(self):
        client_kwargs = {
            "name": "renamer",
            "api_id": Config.API_ID,
            "api_hash": Config.API_HASH,
            "bot_token": Config.BOT_TOKEN,
            "in_memory": True,
            "workers": 512,
            "max_concurrent_transmissions": 128,
            "plugins": {"root": "plugins"},
            "sleep_threshold": 15,
        }

        # Apply low-memory WZGram client options when supported by Client.__init__
        sig_params = inspect.signature(Client.__init__).parameters
        optional_low_ram_kwargs = {
            "fetch_topics": False,
            "fetch_stories": False,
            "fetch_stickers": False,
            "max_message_cache_size": 200,
            "max_topic_cache_size": 100,
        }
        for key, val in optional_low_ram_kwargs.items():
            if key in sig_params:
                client_kwargs[key] = val

        super().__init__(**client_kwargs)
        self.uptime = Config.BOT_UPTIME
        self.premium_client = None
        self.helper_client = None

        if getattr(Config, "STRING_SESSION", None):
            self.premium_client = Client(
                name="premium_session",
                api_id=Config.API_ID,
                api_hash=Config.API_HASH,
                session_string=Config.STRING_SESSION,
                no_updates=True,
                in_memory=True,
                max_concurrent_transmissions=128,
            )

        if getattr(Config, "HELPER_SESSION", None):
            self.helper_client = Client(
                name="helper_session",
                api_id=Config.API_ID,
                api_hash=Config.API_HASH,
                session_string=Config.HELPER_SESSION,
                no_updates=True,
                in_memory=True,
                max_concurrent_transmissions=128,
            )

        # Attach MultiSessionMediaPool to all active MTProto clients
        self.media_pool = MultiSessionMediaPool(
            client=self,
            pool_size=getattr(Config, "MEDIA_POOL_SIZE", 32),
        ).attach(self)

        if self.premium_client:
            self.media_pool.attach(self.premium_client)

        if self.helper_client:
            self.media_pool.attach(self.helper_client)

    async def start(self):
        await super().start()

        if self.premium_client:
            await self.premium_client.start()
            print("⚡ Premium Client Started (STRING_SESSION)")

        if self.helper_client:
            await self.helper_client.start()
            print("⚡ Helper Client Started (HELPER_SESSION)")

        # Pre-warm media sessions sequentially in the background so bot is hot and ready instantly
        asyncio.create_task(self.media_pool.warm_up())

        me = await self.get_me()
        self.mention = me.mention
        self.username = me.username
        self.uptime = Config.BOT_UPTIME

        # Start dummy HTTP webserver unconditionally on PORT (default 8000) for Koyeb / UptimeRobot health checks
        try:
            app = web.AppRunner(await web_server())
            await app.setup()
            port = int(os.environ.get("PORT", 8000))
            await web.TCPSite(app, "0.0.0.0", port).start()
            print(f"🌐 Dummy HTTP webserver started on port {port} (Long-Polling Mode Active)")
        except Exception as e:
            print(f"Webserver start notice: {e}")

        pool_size = getattr(Config, "MEDIA_POOL_SIZE", 32)
        max_pool = getattr(Config, "MEDIA_POOL_MAX", 48)
        progress_interval = getattr(Config, "PROGRESS_UPDATE_INTERVAL", 6.0)
        print(
            f"⚡ {me.first_name} Started | WZGram v{__version__} | "
            f"Loop: {EVENT_LOOP_BACKEND} | Media Pool: {pool_size}-{max_pool} TCP sockets (Sequential Auth) | "
            f"Progress Throttle: {progress_interval}s | Crypto: {CRYPTO_BACKEND}"
        )

        # Send startup message to admins
        for admin_id in Config.ADMIN:
            try:
                await self.send_message(
                    admin_id,
                    f"<blockquote>⚡ <b>{me.first_name} ɪs ᴏɴʟɪɴᴇ!</b></blockquote>\n"
                    f"╭─▸ 🚀 <b>ᴇɴɢɪɴᴇ :</b> <code>ᴡᴢɢʀᴀᴍ ᴠ{__version__}</code>\n"
                    f"├─▸ 🔌 <b>ᴍᴇᴅɪᴀ ᴘᴏᴏʟ :</b> <code>{pool_size}-{max_pool} ᴛᴄᴘ sᴛʀᴇᴀᴍs (sᴇǫᴜᴇɴᴛɪᴀʟ ᴀᴜᴛʜ)</code>\n"
                    f"├─▸ ⏱️ <b>ᴘʀᴏɢʀᴇss ʀᴀᴛᴇ :</b> <code>{progress_interval}s ᴛʜʀᴏᴛᴛʟᴇ (ᴍᴀx ɪ/ᴏ)</code>\n"
                    f"╰─▸ 🔐 <b>ᴄʀʏᴘᴛᴏ :</b> <code>{CRYPTO_BACKEND}</code>",
                )
            except Exception as e:
                print(f"Error sending message to admin {admin_id}: {e}")

        # Send startup message to log channel
        if Config.LOG_CHANNEL:
            try:
                from pyrogram.raw.all import layer

                curr = datetime.now(timezone("Asia/Kolkata"))
                date_str = curr.strftime("%d %B, %Y")
                time_str = curr.strftime("%I:%M:%S %p")
                await self.send_message(
                    Config.LOG_CHANNEL,
                    f"<blockquote>⚡ <b>{me.mention} ʀᴇsᴛᴀʀᴛᴇᴅ sᴜᴄᴄᴇssꜰᴜʟʟʏ!</b></blockquote>\n\n"
                    f"╭─▸ 📅 <b>ᴅᴀᴛᴇ :</b> <code>{date_str}</code>\n"
                    f"├─▸ ⏰ <b>ᴛɪᴍᴇ :</b> <code>{time_str}</code>\n"
                    f"├─▸ 🌐 <b>ᴛɪᴍᴇᴢᴏɴᴇ :</b> <code>Asia/Kolkata</code>\n"
                    f"├─▸ ⚡ <b>ᴇɴɢɪɴᴇ :</b> <code>WZGram v{__version__} (Layer {layer})</code>\n"
                    f"├─▸ 🚀 <b>ᴍᴇᴅɪᴀ ᴘᴏᴏʟ :</b> <code>{pool_size}-{max_pool} ᴘᴀʀᴀʟʟᴇʟ ᴛᴄᴘ sᴛʀᴇᴀᴍs (sᴇǫᴜᴇɴᴛɪᴀʟ)</code>\n"
                    f"├─▸ ⏱️ <b>ᴘʀᴏɢʀᴇss ʀᴀᴛᴇ :</b> <code>{progress_interval}s ᴛʜʀᴏᴛᴛʟᴇ</code>\n"
                    f"╰─▸ 🔐 <b>ᴄʀʏᴘᴛᴏ :</b> <code>{CRYPTO_BACKEND}</code>",
                )
            except Exception as e:
                print(f"Error sending message to LOG_CHANNEL: {e}")

    async def stop(self, *args):
        if hasattr(self, "media_pool"):
            try:
                await self.media_pool.stop()
            except Exception:
                pass
        if self.helper_client and getattr(self.helper_client, "is_connected", False):
            try:
                await self.helper_client.stop()
            except Exception:
                pass
        if self.premium_client and getattr(self.premium_client, "is_connected", False):
            try:
                await self.premium_client.stop()
            except Exception:
                pass
        await super().stop(*args)
        print(f"{getattr(self, 'mention', 'Bot')} is stopped.")


if __name__ == "__main__":
    Bot().run()