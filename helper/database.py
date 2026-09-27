import motor.motor_asyncio
import time
from config import Config
from .utils import send_log


class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.Mythicbotz = self._client[database_name]
        self.col = self.Mythicbotz.user
        self.bannedList = self.Mythicbotz.bannedList

    def new_user(self, id):
        return dict(
            _id=int(id),
            file_id=None,
            caption=None,
            prefix=None,
            suffix=None,
            metadata=False,
            metadata_code="By :- @Otaku_Hindi_Hub",
            rename_count=0,
            destination_channel=None,
            waiting_for_channel=False,
            waiting_since=None,   # ⏳ store timestamp for timeout
        )

    async def add_user(self, b, m):
        u = m.from_user
        if not await self.is_user_exist(u.id):
            user = self.new_user(u.id)
            await self.col.insert_one(user)
            await send_log(b, u)

    async def is_user_exist(self, id):
        return bool(await self.col.find_one({'_id': int(id)}))

    async def total_users_count(self):
        return await self.col.count_documents({})

    async def get_all_users(self):
        return self.col.find({})

    async def delete_user(self, user_id):
        await self.col.delete_many({'_id': int(user_id)})

    # ======================= Thumbnail ======================= #
    async def set_thumbnail(self, id, file_id):
        await self.col.update_one({'_id': int(id)}, {'$set': {'file_id': file_id}})

    async def get_thumbnail(self, id):
        user = await self.col.find_one({'_id': int(id)}, {"file_id": 1})
        return user.get('file_id') if user else None

    # ======================= Caption ======================= #
    async def set_caption(self, id, caption):
        await self.col.update_one({'_id': int(id)}, {'$set': {'caption': caption}})

    async def get_caption(self, id):
        user = await self.col.find_one({'_id': int(id)}, {"caption": 1})
        return user.get('caption') if user else None

    # ======================= Prefix ======================= #
    async def set_prefix(self, id, prefix):
        await self.col.update_one({'_id': int(id)}, {'$set': {'prefix': prefix}})

    async def get_prefix(self, id):
        user = await self.col.find_one({'_id': int(id)}, {"prefix": 1})
        return user.get('prefix') if user else None

    # ======================= Suffix ======================= #
    async def set_suffix(self, id, suffix):
        await self.col.update_one({'_id': int(id)}, {'$set': {'suffix': suffix}})

    async def get_suffix(self, id):
        user = await self.col.find_one({'_id': int(id)}, {"suffix": 1})
        return user.get('suffix') if user else None

    # ======================= Metadata ======================= #
    async def set_metadata(self, id, bool_meta):
        await self.col.update_one({'_id': int(id)}, {'$set': {'metadata': bool_meta}})

    async def get_metadata(self, id):
        user = await self.col.find_one({'_id': int(id)}, {"metadata": 1})
        return user.get('metadata') if user else None

    async def set_metadata_code(self, id, metadata_code):
        await self.col.update_one({'_id': int(id)}, {'$set': {'metadata_code': metadata_code}})

    async def get_metadata_code(self, id):
        user = await self.col.find_one({'_id': int(id)}, {"metadata_code": 1})
        return user.get('metadata_code') if user else None

    # ======================= Ban User ======================= #
    async def ban_user(self, user_id):
        if await self.bannedList.find_one({'banId': int(user_id)}):
            return False
        await self.bannedList.insert_one({'banId': int(user_id)})
        return True

    async def is_banned(self, user_id):
        return bool(await self.bannedList.find_one({'banId': int(user_id)}))

    async def is_unbanned(self, user_id):
        if await self.bannedList.find_one({'banId': int(user_id)}):
            await self.bannedList.delete_one({'banId': int(user_id)})
            return True
        return False

    # ======================= Rename Count ======================= #
    async def increase_rename_count(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)}, {"rename_count": 1})
        if user:
            count = user.get('rename_count', 0) + 1
            await self.col.update_one({'_id': int(user_id)}, {'$set': {'rename_count': count}})
            return count
        return 0

    async def get_leaderboard(self, limit=10):
        cursor = self.col.find({}).sort('rename_count', -1).limit(limit)
        return [(doc['_id'], doc.get('rename_count', 0)) async for doc in cursor]

    # ======================= Destination Channel ======================= #
    async def set_waiting_for_channel(self, user_id, value: bool, ts: int = None):
        await self.col.update_one(
            {"_id": int(user_id)},
            {"$set": {
                "waiting_for_channel": bool(value),
                "waiting_since": ts if value else None
            }},
            upsert=True
        )

    async def is_waiting_for_channel(self, user_id, with_ts: bool = False):
        user = await self.col.find_one(
            {"_id": int(user_id)},
            {"waiting_for_channel": 1, "waiting_since": 1}
        )
        if not user:
            return (False, None) if with_ts else False
        waiting = bool(user.get("waiting_for_channel", False))
        ts = user.get("waiting_since")
        return (waiting, ts) if with_ts else waiting

    async def clear_waiting_for_channel(self, user_id):
        await self.col.update_one(
            {"_id": int(user_id)},
            {"$set": {"waiting_for_channel": False, "waiting_since": None}}
        )

    async def save_destination_channel(self, user_id, channel_id: int):
        await self.col.update_one(
            {"_id": int(user_id)},
            {"$set": {"destination_channel": int(channel_id)}},
            upsert=True
        )

    async def get_destination_channel(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)}, {"destination_channel": 1})
        return int(user["destination_channel"]) if user and "destination_channel" in user else None

    async def clear_destination_channel(self, user_id):
        await self.col.update_one(
            {"_id": int(user_id)},
            {"$unset": {"destination_channel": ""}}
        )


# Global instance
Mythicbotz = Database(Config.DB_URL, Config.DB_NAME)