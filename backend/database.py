"""Shared database module — imported by server.py and auth.py to avoid circular imports."""
import os
from motor.motor_asyncio import AsyncIOMotorClient

# Client is instantiated at import time using env vars already loaded by server.py.
mongo_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = mongo_client[os.environ["DB_NAME"]]
