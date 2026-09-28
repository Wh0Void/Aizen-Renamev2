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
    MultiSessionMediaPool,
    configure_wzgram_environment,
    install_fast_event_loop,
    release_memory,
)

# 1. Configure Wzgram environment knobs & uvloop BEFORE importing wzgram/pyrogram
configure_wzgram_environment(
    pool_size=Config.MEDIA_POOL_SIZE,
    max_read_ahead=Config.WZGRAM_MAX_READ_AHEAD,
)
EVENT_LOOP_BACKEND = install_fast_event_loop()

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

pyrogram.utils.MIN_CHAT_ID = -999999999999
pyrogram.utils.MIN_CHANNEL_ID = -1009999999999


class Bot(Client):
    """
    High-Speed Wzgram Bot Client with Multi-Session Media Connection Pool (24 TCP sockets),
    Hardware AES-NI Crypto (`WarpCrypto`), and Low-RAM In-Memory Session Storage.
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

        # Apply low-memory Wzgram client options when supported by Client.__init__
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

        # Attach Multi-Session Connection Pool (16-24 parallel TCP media sessions + AES-NI)
        self.fast_pool = MultiSessionMediaPool(
            client=self,
            pool_size=Config.MEDIA_POOL_SIZE,
        ).attach(self)

    async def start(self):
        await super().start()

        if self.premium_client:
            await self.premium_client.start()
            print("⚡ Premium Client Started (STRING_SESSION)")

        if self.helper_client:
            await self.helper_client.start()
            print("⚡ Helper Client Started (HELPER_SESSION)")

        await self.fast_pool.start_background_reaper()
        asyncio.create_task(self.fast_pool.warm_up())

        me = await self.get_me()
        self.mention = me.mention
        self.username = me.username
        self.uptime = Config.BOT_UPTIME

        if Config.WEBHOOK:
            app = web.AppRunner(await web_server())
            await app.setup()
            port = int(os.environ.get("PORT", 8000))
            await web.TCPSite(app, "0.0.0.0", port).start()
            print(f"🌐 Webhook server started on port {port}")

        print(
            f"⚡ {me.first_name} Started | Wzgram v{__version__} | "
            f"Loop: {EVENT_LOOP_BACKEND} | Media Pool: {self.fast_pool.pool_size} TCP sockets | "
            f"Crypto: {self.fast_pool.crypto.backend_name}"
        )

        # Send startup message to admins
        for admin_id in Config.ADMIN:
            try:
                await self.send_message(
                    admin_id,
                    f"<blockquote>⚡ <b>{me.first_name} ɪs ᴏɴʟɪɴᴇ!</b></blockquote>\n"
                    f"╭─▸ 🚀 <b>ᴇɴɢɪɴᴇ :</b> <code>ᴡᴢɢʀᴀᴍ ᴠ{__version__}</code>\n"
                    f"├─▸ 🔌 <b>ᴍᴇᴅɪᴀ ᴘᴏᴏʟ :</b> <code>{self.fast_pool.pool_size} ᴛᴄᴘ sᴛʀᴇᴀᴍs</code>\n"
                    f"╰─▸ 🔐 <b>ᴄʀʏᴘᴛᴏ :</b> <code>{self.fast_pool.crypto.backend_name}</code>",
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
                    f"├─▸ ⚡ <b>ᴇɴɢɪɴᴇ :</b> <code>Wzgram v{__version__} (Layer {layer})</code>\n"
                    f"├─▸ 🚀 <b>ᴍᴇᴅɪᴀ ᴘᴏᴏʟ :</b> <code>{self.fast_pool.pool_size} ᴘᴀʀᴀʟʟᴇʟ ᴛᴄᴘ sᴛʀᴇᴀᴍs</code>\n"
                    f"╰─▸ 🔐 <b>ᴄʀʏᴘᴛᴏ :</b> <code>{self.fast_pool.crypto.backend_name}</code>",
                )
            except Exception as e:
                print(f"Error sending message to LOG_CHANNEL: {e}")

        release_memory()

    async def stop(self, *args):
        await self.fast_pool.stop()
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