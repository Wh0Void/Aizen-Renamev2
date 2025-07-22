import motor.motor_asyncio
from config import Config
from .utils import send_log
from pymongo import MongoClient
from datetime import datetime, timedelta

class Database:



# ⛓ Connect to MongoDB
client = MongoClient(Config.MONGO_URL)
db = client["Rename"]  # Use your actual DB name
token_col = db["token_access"]

# ✅ Save token with expiry (12 hours)
async def save_token(user_id: int):
    expiry_time = datetime.utcnow() + timedelta(hours=12)
    token_data = {
        "user_id": user_id,
        "expires_at": expiry_time
    }
    await token_col.update_one(
        {"user_id": user_id},
        {"$set": token_data},
        upsert=True
    )

# ✅ Check if token is valid
async def is_token_valid(user_id: int) -> bool:
    user_token = await token_col.find_one({"user_id": user_id})
    if not user_token:
        return False
    return user_token["expires_at"] > datetime.utcnow()

# ✅ (Optional) Cleanup expired tokens
async def remove_expired_tokens():
    await token_col.delete_many({"expires_at": {"$lt": datetime.utcnow()}})

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
            metadata_code="By :- @TechifyBots"
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
            e = f'Fᴀɪʟᴇᴅ ᴛᴏ ᴜɴʙᴀɴ.Rᴇᴀsᴏɴ : {e}'
            print(e)
            return e

# Create a Database instance
jishubotz = Database(Config.DB_URL, Config.DB_NAME)
