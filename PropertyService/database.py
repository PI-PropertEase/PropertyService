from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

user = os.getenv("MONGO_INITDB_ROOT_USERNAME")
password = os.getenv("MONGO_INITDB_ROOT_PASSWORD")

MONGO_DATABASE_URL = f"mongodb://{user}:{password}@property_service_db:27017"

client = AsyncIOMotorClient(MONGO_DATABASE_URL)
database = client["mydatabase"]
collection = database["properties"]

