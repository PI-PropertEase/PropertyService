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
)
from PropertyService.database import collection
from PropertyService.schemas import Property

from ProjectUtils.MessagingService.schemas import to_json_aoi_bytes, MessageFactory, MessageType, from_json, Service
from ProjectUtils.MessagingService.queue_definitions import routing_key_by_service, WRAPPER_BROADCAST_ROUTING_KEY


# TODO: fix this in the future
channel.close()  # don't use the channel from this file, we need to use an async channel

async_exchange = None


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
            decoded_message = from_json(incoming_message.body)
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
    if len(properties) > 0:
        user_email = properties[0]["user_email"]
        old_new_id_map = {}

        for prop in properties:
            serialized_prop = Property.model_validate(prop)
            property_same_address = await collection.find_one(
                {"address": serialized_prop.address, "user_email": user_email}
            )
            if property_same_address is None:
                await collection.insert_one(serialized_prop.model_dump(by_alias=True))
            else:
                old_id = prop["_id"]
                new_id = property_same_address["_id"]
                if old_id != new_id:
                    old_new_id_map[old_id] = new_id

        await async_exchange.publish(
            routing_key=routing_key_by_service[service],
            message=to_json_aoi_bytes(MessageFactory.create_reservation_import_initial_request_message(
                user_email,
                old_new_id_map
            ))
        )


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
                for prop in decoded_message.body:
                    await collection.find_one_and_update(
                        {"_id": int(prop)},
                        {"$set": {"recommended_price": decoded_message.body[prop]}}
                    )
            print("Price recommendation response processed")
        except Exception as e:
            print("Error while processing message:", e)