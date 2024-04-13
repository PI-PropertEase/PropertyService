import json
from aio_pika import connect_robust, ExchangeType
from ProjectUtils.MessagingService.queue_definitions import (
    channel,
    USER_QUEUE_NAME,
    EXCHANGE_NAME,
    USER_QUEUE_ROUTING_KEY,
    WRAPPER_TO_APP_QUEUE,
    WRAPPER_TO_APP_ROUTING_KEY
)
from ProjectUtils.MessagingService.schemas import MessageType, from_json
from PropertyService.database import collection

# TODO: fix this in the future
channel.close()  # don't use the channel from this file, we need to use an async channel


async def consume(loop):
    connection = await connect_robust(host="rabbit_mq" ,loop=loop)

    channel = await connection.channel()

    users_queue = await channel.declare_queue(USER_QUEUE_NAME, durable=True)

    wrappers_queue = await channel.declare_queue(WRAPPER_TO_APP_QUEUE, durable=True)

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
                await import_properties(decoded_message.body)
        except Exception as e:
            print("Error while processing message:", e)


async def import_properties(properties):
    print("IMPORT_PROPERTIES_RESPONSE - importing properties...")
    for prop in properties:
        num_prop_same_address = await collection.count_documents(
            {"address": prop.get("address"), "user_email": prop.get("user_email")}
        )
        if num_prop_same_address > 0:
            continue  # don't import properties that already exist for this user
        await collection.insert_one(prop)
