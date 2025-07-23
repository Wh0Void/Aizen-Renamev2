import motor.motor_asyncio
from config import Config
from pymongo import MongoClient
from datetime import datetime, timedelta

# 🔗 Synchronous client for shortlink tokens (optional if using separately)
client = MongoClient(Config.DB_URL)
db = client["Rename"]
token_col = db["token_access"]

# ========================= TOKEN UTILITIES ========================= #

# ✅ Add tokens manually (e.g., after shortlink verification)
async def add_token(user_id: int, amount: int = 1):
    await token_col.update_one(
        {"user_id": user_id},
        {"$inc": {"tokens": amount}},
        upsert=True
    )

# ✅ Reduce token after rename
async def reduce_token(user_id: int) -> bool:
    user = await token_col.find_one({"user_id": user_id})
    if user and user.get("tokens", 0) > 0:
        await token_col.update_one({"user_id": user_id}, {"$inc": {"tokens": -1}})
        return True
    return False

# ✅ Get token count
#async def get_token(user_id: int) -> int:
    #user = await token_col.find_one({"user_id": #user_id})
    #return user.get("tokens", 0) if user else 0

# ===================== USER DATABASE CLASS ===================== #

class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.user
        self.banned = self.db.banned

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

    async def is_user_exist(self, id):
        return bool(await self.col.find_one({"_id": int(id)}))

    async def total_users_count(self):
        return await self.col.count_documents({})

    async def get_all_users(self):
        return self.col.find({})

    async def delete_user(self, user_id):
        await self.col.delete_many({'_id': int(user_id)})

    # ============= Thumbnail ============= #
    async def set_thumbnail(self, id, file_id):
        await self.col.update_one({'_id': int(id)}, {'$set': {'file_id': file_id}})

    async def get_thumbnail(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('file_id', None)

    # ============= Caption ============= #
    async def set_caption(self, id, caption):
        await self.col.update_one({'_id': int(id)}, {'$set': {'caption': caption}})

    async def get_caption(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('caption', None)

    # ============= Prefix ============= #
    async def set_prefix(self, id, prefix):
        await self.col.update_one({'_id': int(id)}, {'$set': {'prefix': prefix}})

    async def get_prefix(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('prefix', None)

    # ============= Suffix ============= #
    async def set_suffix(self, id, suffix):
        await self.col.update_one({'_id': int(id)}, {'$set': {'suffix': suffix}})

    async def get_suffix(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('suffix', None)

    # ============= Metadata ============= #
    async def set_metadata(self, id, bool_meta):
        await self.col.update_one({'_id': int(id)}, {'$set': {'metadata': bool_meta}})

    async def get_metadata(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('metadata', None)

    async def set_metadata_code(self, id, metadata_code):
        await self.col.update_one({'_id': int(id)}, {'$set': {'metadata_code': metadata_code}})

    async def get_metadata_code(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('metadata_code', None)

    # ============= Premium ============= #
    async def set_premium(self, user_id: int, value: bool = True):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'is_premium': value}})

    async def is_premium(self, user_id: int) -> bool:
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get("is_premium", False) if user else False

# ✅ Get token validity (returns 1 if valid, else 0)
async def get_token(user_id: int) -> int:
    user_token = await token_col.find_one({"user_id": user_id})
    if not user_token:
        return 0
    if user_token["expires_at"] > datetime.utcnow():
        return 1  # Valid token
    return 0


    # ============= Ban System ============= #
    async def ban_user(self, user_id):
        if await self.banned.find_one({'banId': int(user_id)}):
            return False
        await self.banned.insert_one({'banId': int(user_id)})
        return True

    async def is_banned(self, user_id):
        return bool(await self.banned.find_one({'banId': int(user_id)}))

    async def is_unbanned(self, user_id):
        try:
            if await self.banned.find_one({'banId': int(user_id)}):
                await self.banned.delete_one({'banId': int(user_id)})
                return True
            return False
        except Exception as e:
            print(f"Failed to unban: {e}")
            return f"Error: {e}"


# ✅ Global Instance
jishubotz = Database(Config.DB_URL, Config.DB_NAME)