import os
from datetime import datetime
from pytz import timezone
from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from config import Config
from aiohttp import web
from route import web_server
import pyrogram.utils
import pyromod

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
        # Initialize pyromod listeners to prevent KeyError
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

        # Initialize file rename plugin
        try:
            from plugins import file_rename
            file_rename.init(self)
            print("✅ File rename plugin initialized")
        except Exception as e:
            print(f"⚠️ Warning: Could not initialize file_rename plugin: {e}")

        if Config.WEBHOOK:
            app = web.AppRunner(await web_server())
            await app.setup()
            PORT = int(os.environ.get("PORT", 8000))  # Use port 8000 or env PORT
            await web.TCPSite(app, "0.0.0.0", PORT).start()
            print(f"🌐 Webhook server started on port {PORT}")

        print(f"{me.first_name} Is Started.....✨️")

        # Send startup message to admins
        for id in Config.ADMIN:
            try: 
                await self.send_message(id, f"**{me.first_name} Is Started...**")                                
            except Exception as e:
                print(f"Error sending message to admin {id}: {e}")

        # Send startup message to log channel
        if Config.LOG_CHANNEL:
            try:
                curr = datetime.now(timezone("Asia/Kolkata"))
                date = curr.strftime('%d %B, %Y')
                time = curr.strftime('%I:%M:%S %p')
                await self.send_message(Config.LOG_CHANNEL, f"**{me.mention} Is Restarted !!**\n\n📅 Date : `{date}`\n⏰ Time : `{time}`\n🌐 Timezone : `Asia/Kolkata`\n\n🉐 Version : `v{__version__} (Layer {layer})`</b>")                                
            except Exception as e:
                print(f"Error sending message to LOG_CHANNEL: {e}")

    async def stop(self):
        await super().stop()
        print(f"{self.mention} is stopped.")


if __name__ == "__main__":
    Bot().run()