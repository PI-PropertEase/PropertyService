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

from ProjectUtils.MessagingService.queue_definitions import (
    channel, 
    EXCHANGE_NAME, 
    PROPERTY_TO_ANALYTICS_QUEUE_ROUTING_KEY,
    analytics_to_property
)
from ProjectUtils.MessagingService.schemas import (
    MessageFactory,
    to_json, 
    from_json
)
import time


import asyncio
from pydantic import BaseModel
import schedule

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(setup(loop))
    await price_recommendation()
    yield



cred = credentials.Certificate(".secret.json")
firebase_admin.initialize_app(cred)
app = FastAPI(lifespan=lifespan)
authRouter = APIRouter(dependencies=[Depends(get_user)])

class PropertyForAnalytics(BaseModel):
    id: str
    latitude: float
    longitude: float
    bathrooms: int
    bedrooms: int
    beds: int
    number_of_guests: int
    num_amenities: int

properties = [
    PropertyForAnalytics(
        id="661a7e5ab7bd0512178cf014",
        latitude=40.639337,
        longitude=-8.65099,
        bathrooms=2,
        bedrooms=3,
        beds=4,
        number_of_guests=4,
        num_amenities=4
    ),
    PropertyForAnalytics(
        id="1f994177dc45954c6148086",
        latitude=40.649127,
        longitude=-8.65455,
        bathrooms=1,
        bedrooms=1,
        beds=1,
        number_of_guests=2,
        num_amenities=3
    ),
    PropertyForAnalytics(
        id="60a283db136301428a0ae06",
        latitude=40.63892,
        longitude=-8.65459,
        bathrooms=1,
        bedrooms=1,
        beds=2,
        number_of_guests=2,
        num_amenities=2
    ),
    PropertyForAnalytics(
        id="1ac9af963e829344c53956b",
        latitude=40.64131,
        longitude=-8.65431,
        bathrooms=2,
        bedrooms=2,
        beds=3,
        number_of_guests=4,
        num_amenities=5
    ),
    PropertyForAnalytics(
        id="2f224177dc45954c6148086",
        latitude=40.64243,
        longitude=-8.64571,
        bathrooms=2,
        bedrooms=2,
        beds=3,
        number_of_guests=4,
        num_amenities=6
    ),
    PropertyForAnalytics(
        id="1e8b214c28d15241902904a",
        latitude=40.63889,
        longitude=-8.64554,
        bathrooms=2,
        bedrooms=3,
        beds=5,
        number_of_guests=6,
        num_amenities=7
    ),
    PropertyForAnalytics(
        id="f91622341c0651489309cfa",
        latitude=40.63848,
        longitude=-8.65434,
        bathrooms=3,
        bedrooms=3,
        beds=6,
        number_of_guests=6,
        num_amenities=8
    ),
    PropertyForAnalytics(
        id="87e1dfd41f80d24d1e1845d",
        latitude=40.63956,
        longitude=-8.65434,
        bathrooms=3,
        bedrooms=4,
        beds=3,
        number_of_guests=4,
        num_amenities=3
    ),
]



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

    
@authRouter.get("/amenities", response_model=list[Amenity])
async def get_amenities():
    return [a.value for a in Amenity]
    

@authRouter.get("/bathroom_fixtures", response_model=list[BathroomFixture])
async def get_bathroom_fixtures():
    return [bf.value for bf in BathroomFixture]


@authRouter.get("/bed_types", response_model=list[BedType])
async def get_bed_types():
    return [b.value for b in BedType]

async def price_recommendation():
    logger.info("Sending price recommendation request")
    json_properties = [property.model_dump() for property in properties]
    message = MessageFactory.create_get_recommended_price(json_properties)
    channel.basic_publish(
        exchange=EXCHANGE_NAME,
        routing_key=PROPERTY_TO_ANALYTICS_QUEUE_ROUTING_KEY,
        body=to_json(message)
    )
    logger.info("Mock property service: Request message sent!")
    time.sleep(5)
    while True:
        method_frame, _, body = channel.basic_get(queue=analytics_to_property.method.queue, auto_ack=True)
        if method_frame:
            message = from_json(body)
            print("Received message:\n" + str(message.__dict__))
            print("Recommended prices for each property: " + str(message.body))
            break
    return {"message": "Price recommendation request sent"}



app.include_router(authRouter, tags=["auth"])
