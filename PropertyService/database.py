from motor.motor_asyncio import AsyncIOMotorClient

MONGO_DATABASE_URL = "mongodb://property_service_db:27017"

client = AsyncIOMotorClient(MONGO_DATABASE_URL)
database = client["mydatabase"]
collection = database["properties"]

