import json
from aio_pika import connect_robust, ExchangeType, Message
from ProjectUtils.MessagingService.queue_definitions import (
    channel,
    USER_QUEUE_NAME,
    EXCHANGE_NAME,
    USER_QUEUE_ROUTING_KEY,
    WRAPPER_TO_APP_QUEUE,
    WRAPPER_TO_APP_ROUTING_KEY,
    WRAPPER_ZOOKING_ROUTING_KEY,
    PROPERTY_TO_ANALYTICS_QUEUE_ROUTING_KEY,
    ANALYTICS_TO_PROPERTY_QUEUE_NAME,
    analytics_to_property,
)
from PropertyService.database import collection
from PropertyService.schemas import UpdateProperty

from ProjectUtils.MessagingService.schemas import to_json_aoi_bytes, MessageFactory, MessageType, from_json, Service, to_json
from ProjectUtils.MessagingService.queue_definitions import routing_key_by_service, WRAPPER_BROADCAST_ROUTING_KEY

import time
from pydantic import BaseModel

# TODO: fix this in the future
channel.close()  # don't use the channel from this file, we need to use an async channel

async_exchange = None

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


async def setup(loop):
    connection = await connect_robust(host="rabbit_mq" ,loop=loop)

    async_channel = await connection.channel()

    global async_exchange

    async_exchange = await async_channel.declare_exchange(
        name=EXCHANGE_NAME, type=ExchangeType.TOPIC, durable=True
    )

    users_queue = await async_channel.declare_queue(USER_QUEUE_NAME, durable=True)

    wrappers_queue = await async_channel.declare_queue(WRAPPER_TO_APP_QUEUE, durable=True)

    priceRecomendation_queue = await async_channel.declare_queue(ANALYTICS_TO_PROPERTY_QUEUE_NAME, durable=True)

    await users_queue.bind(exchange=EXCHANGE_NAME, routing_key=USER_QUEUE_ROUTING_KEY)

    await wrappers_queue.bind(
        exchange=EXCHANGE_NAME, routing_key=WRAPPER_TO_APP_ROUTING_KEY
    )

    await users_queue.consume(callback=consume_user_message)

    await wrappers_queue.consume(callback=consume_wrappers_message)

    await priceRecomendation_queue.consume(callback=consume_price_recomendation)

    return connection


async def consume_user_message(incoming_message):
    print("Received Message @ Users queue")
    async with incoming_message.process():
        try:
            decoded_message = json.loads(incoming_message)
        except Exception as e:
            print("Error while processing message:", e)
        print(incoming_message.body)


async def consume_wrappers_message(incoming_message):
    print("Received Message @ Wrappers queue")
    async with incoming_message.process():
        try:
            decoded_message = from_json(incoming_message.body)
            if decoded_message.message_type == MessageType.PROPERTY_IMPORT_RESPONSE:
                body = decoded_message.body
                await import_properties(body["service"], body["properties"])
        except Exception as e:
            print("Error while processing message:", e)


async def import_properties(service: Service, properties):
    global async_exchange
    print("IMPORT_PROPERTIES_RESPONSE - importing properties...")
    for prop in properties:
        property_same_address = await collection.find_one(
            {"address": prop.get("address"), "user_email": prop.get("user_email")}
        )
        if property_same_address is not None:
            if prop["_id"] != property_same_address["_id"]:
                await async_exchange.publish(
                    routing_key=routing_key_by_service[service],
                    message=to_json_aoi_bytes(MessageFactory.create_duplicate_import_property_message(prop, property_same_address))
                )
        else:
            await collection.insert_one(prop)


async def publish_update_property_message(prop_id: int, prop: dict):
    global async_exchange
    print(f"UPDATING PROPERTY {prop}")
    await async_exchange.publish(
        routing_key=WRAPPER_BROADCAST_ROUTING_KEY,
        message=to_json_aoi_bytes(MessageFactory.create_property_update_message(prop_id, prop))
    )

    print("Craete Property Update Message", MessageFactory.create_property_update_message(prop_id, prop).__dict__)

async def publish_get_recommended_price(properties: list):
    global async_exchange
    print("Sending price recommendation request")
    json_properties = [property.model_dump() for property in properties]
    message = MessageFactory.create_get_recommended_price(json_properties)
    await async_exchange.publish(
        routing_key=PROPERTY_TO_ANALYTICS_QUEUE_ROUTING_KEY,
        message=to_json_aoi_bytes(message)
    )
    print("Price recommendation request sent")

async def consume_price_recomendation(incoming_message):
    print("Received Message @ Price Recomendation queue")
    async with incoming_message.process():
        try:
            decoded_message = from_json(incoming_message.body)
            if decoded_message.message_type == MessageType.RECOMMENDED_PRICE_RESPONSE:
                print("Recommended prices for each property: " + str(decoded_message.body))
        except Exception as e:
            print("Error while processing message:", e) 

