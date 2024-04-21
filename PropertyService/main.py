import firebase_admin
from fastapi import FastAPI, HTTPException, status, Depends, APIRouter
from firebase_admin import credentials
from pymongo import ReturnDocument

from ProjectUtils.DecoderService.decode_token import decode_token
from PropertyService.database import collection
from PropertyService.dependencies import get_user
from PropertyService.schemas import Property, UpdateProperty, Amenity, BathroomFixture, BedType
from contextlib import asynccontextmanager
from PropertyService.messaging_operations import channel, setup, publish_update_property_message

import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(setup(loop))
    yield


cred = credentials.Certificate(".secret.json")
firebase_admin.initialize_app(cred)
app = FastAPI(lifespan=lifespan)
authRouter = APIRouter(dependencies=[Depends(get_user)])


@app.get("/health", tags=["healthcheck"], summary="Perform a Health Check",
         response_description="Return HTTP Status Code 200 (OK)", status_code=status.HTTP_200_OK)
def get_health():
    return {"status": "ok"}


@authRouter.get("/properties", response_model=list[Property])
async def read_properties(user_email: str = None):
    return await collection.find(
        {} if user_email is None else {"user_email": user_email}
    ).to_list(1000)


@authRouter.post("/properties", response_model=Property, response_model_by_alias=False,
                 status_code=status.HTTP_201_CREATED)
async def create_property(prop: Property):
    property_dict = prop.model_dump(exclude={"id"})
    await collection.insert_one(property_dict)
    # property_dict automatically gets id after insertion
    return property_dict


@authRouter.get("/properties/{prop_id}", response_model=Property, response_model_by_alias=False)
async def read_property(prop_id: int):
    if (result := await collection.find_one({"_id": prop_id})) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Property {prop_id} not found")
    return result


@authRouter.put("/properties/{prop_id}", response_model=Property, response_model_by_alias=False)
async def update_property(prop_id: int, prop: UpdateProperty):
    upd_prop = {k: v for k, v in prop.model_dump().items() if v is not None}

    # The update is empty, but we should still return the matching document:
    if len(upd_prop) <= 0:
        return await read_property(prop_id)

    update_result = await collection.find_one_and_update(
        {"_id": prop_id},
        {"$set": upd_prop},
        return_document=ReturnDocument.AFTER,
    )
    if update_result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Property {prop_id} not found")

    await publish_update_property_message(prop_id, upd_prop)
    return update_result


@authRouter.delete("/properties/{prop_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(prop_id: int):
    if (await collection.delete_one({"_id": prop_id})).deleted_count != 1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Property {prop_id} not found")

    
@authRouter.get("/amenities", response_model=list[Amenity], response_model_by_alias=False)
async def get_amenities():
    return [a.value for a in Amenity]
    

@authRouter.get("/bathroom_fixtures", response_model=list[BathroomFixture], response_model_by_alias=False)
async def get_bathroom_fixtures():
    return [bf.value for bf in BathroomFixture]


@authRouter.get("/bed_types", response_model=list[BedType], response_model_by_alias=False)
async def get_bed_types():
    return [b.value for b in BedType]


app.include_router(authRouter, tags=["auth"])
