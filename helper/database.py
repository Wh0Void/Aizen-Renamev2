import motor.motor_asyncio
from config import Config
from .utils import send_log

class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.jishubotz = self._client[database_name]
        self.col = self.jishubotz.user
        self.bannedList = self.jishubotz.bannedList

    def new_user(self, id):
        return dict(
            _id=int(id),                                   
            file_id=None,
            caption=None,
            prefix=None,
            suffix=None,
            metadata=False,
            metadata_code="By :- @Otaku_Hindi_Hub",
            rename_count=0,  # Rename count tracking
            destination_channel=None,  # New field for Destination Channel
            waiting_for_channel=False  # State flag while setting Destination
        )

    async def add_user(self, b, m):
        u = m.from_user
        if not await self.is_user_exist(u.id):
            user = self.new_user(u.id)
            await self.col.insert_one(user)            
            await send_log(b, u)

    async def is_user_exist(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return bool(user)

    async def total_users_count(self):
        count = await self.col.count_documents({})
        return count

    async def get_all_users(self):
        all_users = self.col.find({})
        return all_users

    async def delete_user(self, user_id):
        await self.col.delete_many({'_id': int(user_id)})

    #======================= Thumbnail ========================#

    async def set_thumbnail(self, id, file_id):
        await self.col.update_one({'_id': int(id)}, {'$set': {'file_id': file_id}})

    async def get_thumbnail(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('file_id', None)

    #======================= Caption ========================#

    async def set_caption(self, id, caption):
        await self.col.update_one({'_id': int(id)}, {'$set': {'caption': caption}})

    async def get_caption(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('caption', None)

    #======================= Prefix ========================#

    async def set_prefix(self, id, prefix):
        await self.col.update_one({'_id': int(id)}, {'$set': {'prefix': prefix}})  

    async def get_prefix(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('prefix', None)

    #======================= Suffix ========================#

    async def set_suffix(self, id, suffix):
        await self.col.update_one({'_id': int(id)}, {'$set': {'suffix': suffix}})  

    async def get_suffix(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('suffix', None)

    #======================= Metadata ========================#

    async def set_metadata(self, id, bool_meta):
        await self.col.update_one({'_id': int(id)}, {'$set': {'metadata': bool_meta}})

    async def get_metadata(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('metadata', None)

    #======================= Metadata Code ========================#    

    async def set_metadata_code(self, id, metadata_code):
        await self.col.update_one({'_id': int(id)}, {'$set': {'metadata_code': metadata_code}})

    async def get_metadata_code(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('metadata_code', None)

    #======================= Ban User ========================#

    async def ban_user(self, user_id):
        user = await self.bannedList.find_one({'banId': int(user_id)})
        if user:
            return False
        else:
            await self.bannedList.insert_one({'banId': int(user_id)})
            return True

    async def is_banned(self, user_id):
        user = await self.bannedList.find_one({'banId': int(user_id)})
        return True if user else False

    async def is_unbanned(self, user_id):
        try: 
            if await self.bannedList.find_one({'banId': int(user_id)}):
                await self.bannedList.delete_one({'banId': int(user_id)})
                return True
            else:
                return False
        except Exception as e:
            e = f'Failed to unban. Reason: {e}'
            print(e)
            return e

    #======================= Rename Count ========================#

    async def increase_rename_count(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        if user:
            count = user.get('rename_count', 0) + 1
            await self.col.update_one({'_id': int(user_id)}, {'$set': {'rename_count': count}})
            return count
        return 0

    #======================= Leaderboard ========================#

    async def get_leaderboard(self, limit=10):
        users = self.col.find({}).sort('rename_count', -1).limit(limit)
        return [(user['_id'], user.get('rename_count', 0)) async for user in users]

    #======================= Destination Channel ========================#

    async def set_waiting_for_channel(self, user_id, value: bool):
        await self.col.update_one(
            {"_id": int(user_id)},
            {"$set": {"waiting_for_channel": bool(value)}},
            upsert=True
        )

    async def is_waiting_for_channel(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)}, {"waiting_for_channel": 1})
        return bool(user and user.get("waiting_for_channel"))

    async def clear_waiting_for_channel(self, user_id):
        await self.col.update_one(
            {"_id": int(user_id)},
            {"$unset": {"waiting_for_channel": ""}}
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


# Create a Database instance
jishubotz = Database(Config.DB_URL, Config.DB_NAME)