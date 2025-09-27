import os
import asyncio
from datetime import datetime
from pytz import timezone
from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from config import Config
from aiohttp import web
from route import web_server
import pyrogram.utils
import pyromod
from plugins import destination  # <-- updated

pyrogram.utils.MIN_CHAT_ID = -999999999999
pyrogram.utils.MIN_CHANNEL_ID = -1009999999999


class Bot(Client):
    def __init__(self):
        super().__init__(
            name="renamer",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            workers=200,
            plugins={"root": "plugins"},
            sleep_threshold=15,
        )

    async def start(self):
        if 'message' not in self.listeners:
            self.listeners['message'] = []
        if 'callback_query' not in self.listeners:
            self.listeners['callback_query'] = []
        print(f"Initial listeners: {self.listeners}")

        await super().start()
        me = await self.get_me()
        self.mention = me.mention
        self.username = me.username  
        self.uptime = Config.BOT_UPTIME

        try:
            destination.init(self)
            print("✅ Destination plugin initialized")
        except Exception as e:
            print(f"⚠️ Warning: Could not initialize destination plugin: {e}")

        if Config.WEBHOOK:
            app = web.AppRunner(await web_server())
            await app.setup()
            PORT = int(os.environ.get("PORT", 8000))
            await web.TCPSite(app, "0.0.0.0", PORT).start()
            print(f"🌐 Webhook server started on port {PORT}")

        print(f"{me.first_name} Is Started.....✨️")

        for id in Config.ADMIN:
            try: 
                await self.send_message(id, f"**{me.first_name} Is Started...**")                                
            except Exception as e:
                print(f"Error sending message to admin {id}: {e}")

        if Config.LOG_CHANNEL:
            try:
                curr = datetime.now(timezone("Asia/Kolkata"))
                date = curr.strftime('%d %B, %Y')
                time = curr.strftime('%I:%M:%S %p')
                await self.send_message(
                    Config.LOG_CHANNEL,
                    f"**{me.mention} Is Restarted !!**\n\n"
                    f"📅 Date : `{date}`\n"
                    f"⏰ Time : `{time}`\n"
                    f"🌐 Timezone : `Asia/Kolkata`\n\n"
                    f"🉐 Version : `v{__version__} (Layer {layer})`</b>"
                )                                
            except Exception as e:
                print(f"Error sending message to LOG_CHANNEL: {e}")

    async def stop(self):
        await super().stop()
        print(f"{self.mention} is stopped.")


async def run_bot_loop():
    while True:
        try:
            bot = Bot()
            await bot.start()
            # Keep the bot running indefinitely
            while True:
                await asyncio.sleep(600)  # Check every 10 minutes
        except Exception as e:
            print(f"⚠️ Bot crashed: {e}")
            print("🔄 Restarting bot in 10 seconds...")
            await asyncio.sleep(10)  # Small delay before restart


if __name__ == "__main__":
    asyncio.run(run_bot_loop())