from motor.motor_asyncio import AsyncIOMotorClient

MONGO_DATABASE_URL = "mongodb://localhost:27017"

client = AsyncIOMotorClient(MONGO_DATABASE_URL)
database = client["mydatabase"]
collection = database["items"]

