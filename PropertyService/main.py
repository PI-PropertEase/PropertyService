import firebase_admin
from fastapi import FastAPI, HTTPException, status, Depends, APIRouter
from firebase_admin import credentials
from pymongo import ReturnDocument

from ProjectUtils.DecoderService.decode_token import decode_token
from PropertyService.database import collection
from PropertyService.dependencies import get_user, get_user_email
from PropertyService.schemas import Property, UpdateProperty, Amenity, BathroomFixture, BedType, PropertyForAnalytics
from contextlib import asynccontextmanager
from PropertyService.messaging_operations import setup, publish_update_property_message, publish_get_recommended_price, publish_send_data_to_analytics

import asyncio

import logging
import random

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

scheduler = AsyncIOScheduler()
scheduler.start()

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    await asyncio.ensure_future(setup(loop))
    asyncio.ensure_future(price_recommendation())
    daily_time = time(hour=22, minute=30) 
    scheduler.add_job(price_recommendation, 'cron', hour=daily_time.hour, minute=daily_time.minute)
    #scheduler.add_job(send_data_to_analytics, 'interval', minutes=1) #test
    scheduler.add_job(send_data_to_analytics, 'interval', hours=1)
    yield

cred = credentials.Certificate(".secret.json")
firebase_admin.initialize_app(cred)
app = FastAPI(
    lifespan=lifespan, 
    root_path="/api/PropertyService",
    title="PropertyService",
    description="The Property Service exposes many endpoints for manipulating data related to properties, \
        such as updating properties as obtaining data related to them, such as available amenities, bed types and bathroom fixtures. \
        All endpoints require authorization, verified by the Authorization bearer token.",
    version="1.0.0"
)
authRouter = APIRouter(dependencies=[Depends(get_user)])


@app.get("/health", tags=["healthcheck"], summary="Perform a Health Check",
         response_description="Return HTTP Status Code 200 (OK)", status_code=status.HTTP_200_OK)
def get_health():
    return {"status": "ok"}


@authRouter.get("/properties", response_model=list[Property],
                summary="List all properties for a specific user.",
                response_description="Return a list of all properties for a user, based on his authorization token."
                )
async def read_properties(user_email: str = Depends(get_user_email)):
    return await collection.find({"user_email": user_email}).to_list(1000)


@authRouter.get("/properties/{prop_id}", response_model=Property, response_model_by_alias=False,
                summary="Get a specific property for a specific user.",
                response_description="Return a specific property for a user, based on his authorization token.",
                responses={
                    status.HTTP_404_NOT_FOUND: {
                        "description": "Property not found for given user.",
                        "content": {"application/json": {"example": {"detail": "Property 0 not found for user user@example.com."}}}
                    }
                })
async def read_property(prop_id: int, user_email: str = Depends(get_user_email)):
    if (result := await collection.find_one({"_id": prop_id, "user_email": user_email})) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Property {prop_id} not found for user {user_email}")
    return result


@authRouter.put("/properties/{prop_id}", response_model=Property, response_model_by_alias=False,
                summary="Update a specific property for a specific user.",
                response_description="Return the updated property for a user, based on his authorization token.",
                responses={
                    status.HTTP_404_NOT_FOUND: {
                        "description": "Property not found for given user.",
                        "content": {"application/json": {"example": {"detail": "Property 0 not found for user user@example.com."}}}
                    }
                })
async def update_property(prop_id: int, prop: UpdateProperty, user_email: str = Depends(get_user_email)):
    upd_prop = {k: v for k, v in prop.model_dump().items() if v is not None}


    # The update is empty, but we should still return the matching document:
    if len(upd_prop) <= 0:
        return await read_property(prop_id)
    
    if "recommended_price" in upd_prop and "update_price_automatically" in upd_prop and upd_prop.get("update_price_automatically") is True and upd_prop.get("price") != upd_prop.get("recommended_price"):
        upd_prop["price"] = upd_prop.get("recommended_price")

    update_result = await collection.find_one_and_update(
        {"_id": prop_id, "user_email": user_email},
        {"$set": upd_prop},
        return_document=ReturnDocument.AFTER,
    )
    if update_result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Property {prop_id} not found for user {user_email}")
    
    upd_attributes = upd_prop.keys()
    # make sure "after_commission" is always included in the message sent to wrappers
    if "price" in upd_attributes and "after_commission" not in upd_attributes:
        upd_prop["after_commission"] = update_result.get("after_commission")


    await publish_update_property_message(prop_id, upd_prop)

    return update_result

    
@authRouter.get("/amenities", response_model=list[Amenity],
                summary="List all available amenities.",
                response_description="Return a list of all available amenities.",
                responses={
                    status.HTTP_200_OK: {
                        "description": "Return a list of all available amenities.",
                        "content": {"application/json": {
                            "example": ["free_wifi", "parking_space", "air_conditioner", "pool", "kitchen"]
                        }}
                    }
                })
async def get_amenities():
    return [a.value for a in Amenity]
    

@authRouter.get("/bathroom_fixtures", response_model=list[BathroomFixture],
                summary="List all available bathroom fixtures.",
                response_description="Return a list of all available bathroom fixtures.",
                responses={
                    status.HTTP_200_OK: {
                        "description": "Return a list of all available bathroom fixtures.",
                        "content": {"application/json": {"example": ["bathtub", "shower", "bidet", "toilet"]}}
                    }
                })
async def get_bathroom_fixtures():
    return [bf.value for bf in BathroomFixture]


@authRouter.get("/bed_types", response_model=list[BedType],
                summary="List all available bed types.",
                response_description="Return a list of all available bed types.",
                responses={
                    status.HTTP_200_OK: {
                        "description": "Return a list of all available bed types.",
                        "content": {"application/json": {
                            "example": ["single", "queen", "king"]
                        }}
                    }
                })
async def get_bed_types():
    return [b.value for b in BedType]

"""
    Called periodically to send AnalyticsService a message to get recommended prices, including
    the properties' relevant features for price recommendation.
"""
async def price_recommendation():
    properties = await collection.find().to_list(1000)
    logger.info("Sending price recommendation request")
    propertiesAnalytics = []
    if properties != []: 
        for prop in properties:
            bedrooms = prop["bedrooms"]
            num_beds = 0
            for key, value in bedrooms.items():
                num_beds += value["beds"][0]["number_beds"]
                
            propertyAnalytics = PropertyForAnalytics(
                id = prop["_id"].__str__(),
                latitude= round(random.uniform(36, 42), 5),
                longitude= round(random.uniform(-9.5, -7), 5),
                bathrooms = len(prop["bathrooms"].keys()),
                bedrooms = len(prop["bedrooms"].keys()),
                beds= num_beds,
                number_of_guests = prop["number_guests"],
                num_amenities = len(prop["amenities"]),
                location = prop["location"],
                price = prop["price"])
            
            propertiesAnalytics.append(propertyAnalytics)
        
        await publish_get_recommended_price(propertiesAnalytics)
        return {"message": "Price recommendation request sent"}
    

"""
    Called periodically to send AnalyticsService a message with data for analytics purposes.
    Sent data excludes anything that connects the property to a specific owner, such as their e-mail.
"""
async def send_data_to_analytics():
    properties = await collection.find().to_list(1000)
    logger.info("Sending data to analytics")
    propertiesAnalytics = []
    if properties != []: 
        for prop in properties:
            bedrooms = prop["bedrooms"]
            num_beds = 0
            for key, value in bedrooms.items():
                num_beds += value["beds"][0]["number_beds"]
            
            propertyAnalytics = {
                "id": prop["_id"].__str__(),
                "bathrooms": len(prop["bathrooms"].keys()),
                "bedrooms": len(prop["bedrooms"].keys()),
                "beds": num_beds,
                "number_of_guests": prop["number_guests"],
                "num_amenities": len(prop["amenities"]),
                "location": prop["location"],
                "price": prop["price"],
                "services": prop["services"],
                "recommended_price": prop["recommended_price"]
            }
            
            propertiesAnalytics.append(propertyAnalytics)
        
        await publish_send_data_to_analytics(propertiesAnalytics)

        return {"message": "Data sent to analytics"}

app.include_router(authRouter, tags=["properties"])
