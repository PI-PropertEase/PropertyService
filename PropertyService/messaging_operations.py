import json
from aio_pika import connect_robust, ExchangeType, Message
from ProjectUtils.MessagingService.queue_definitions import (
    channel,
    USER_QUEUE_NAME,
    EXCHANGE_NAME,
    USER_QUEUE_ROUTING_KEY,
    WRAPPER_TO_APP_QUEUE,
    WRAPPER_TO_APP_ROUTING_KEY,
    WRAPPER_ZOOKING_ROUTING_KEY
)
from PropertyService.database import collection

from ProjectUtils.MessagingService.schemas import to_json_aoi_bytes, MessageFactory, MessageType, from_json, Service
from ProjectUtils.MessagingService.queue_definitions import routing_key_by_service

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

    await users_queue.bind(exchange=EXCHANGE_NAME, routing_key=USER_QUEUE_ROUTING_KEY)

    await wrappers_queue.bind(
        exchange=EXCHANGE_NAME, routing_key=WRAPPER_TO_APP_ROUTING_KEY
    )

    await users_queue.consume(callback=consume_user_message)

    await wrappers_queue.consume(callback=consume_wrappers_message)

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