import json
from aio_pika import connect_robust, ExchangeType
from ProjectUtils.MessagingService.queue_definitions import (
    channel,
    USER_QUEUE_NAME,
    EXCHANGE_NAME,
    USER_QUEUE_ROUTING_KEY,
)

# TODO: fix this in the future
channel.close()  # don't use the channel from this file, we need to use an async channel


async def consume(loop):
    connection = await connect_robust(loop=loop)

    channel = await connection.channel()

    queue = await channel.declare_queue(USER_QUEUE_NAME, durable=True)

    await queue.bind(exchange=EXCHANGE_NAME, routing_key=USER_QUEUE_ROUTING_KEY)

    await queue.consume(callback=consume_message)

    return connection


async def consume_message(message):
    async with message.process():
        print(message.body)
