from bson import ObjectId
from fastapi import FastAPI, HTTPException, status
from pymongo import ReturnDocument

from PropertyService.database import collection
from PropertyService.schemas import Property, UpdateProperty
from contextlib import asynccontextmanager
from PropertyService.messaging_operations import channel, consume

import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(consume(loop))
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/properties", response_model=list[Property])
async def read_properties(user_id: int = None):
    return await collection.find(
        {} if user_id is None else {"user_id": user_id}
    ).to_list(1000)


@app.post("/properties", response_model=Property, response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def create_property(prop: Property):
    property_dict = prop.model_dump(exclude={"id"})
    await collection.insert_one(property_dict)
    # property_dict automatically gets id after insertion
    return property_dict


@app.get("/properties/{prop_id}", response_model=Property, response_model_by_alias=False)
async def read_property(prop_id: str):
    if not ObjectId.is_valid(prop_id) or (result := await collection.find_one({"_id": ObjectId(prop_id)})) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Property {prop_id} not found")
    return result


@app.put("/properties/{prop_id}", response_model=Property, response_model_by_alias=False)
async def update_property(prop_id: str, prop: UpdateProperty):
    upd_prop = {k: v for k, v in prop.model_dump().items() if v is not None}

    # The update is empty, but we should still return the matching document:
    if len(upd_prop) <= 0:
        return await read_property(prop_id)

    if (not ObjectId.is_valid(prop_id)
        or (
            update_result := await collection.find_one_and_update(
                {"_id": ObjectId(prop_id)},
                {"$set": upd_prop},
                return_document=ReturnDocument.AFTER,
            )
        )
        is None
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Property {prop_id} not found")
    return update_result


@app.delete("/properties/{prop_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(prop_id: str):
    if (
        not ObjectId.is_valid(prop_id)
        or (await collection.delete_one({"_id": ObjectId(prop_id)})).deleted_count != 1
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Property {prop_id} not found")
