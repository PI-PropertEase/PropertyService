import json
import pika
from ProjectUtils.MessagingService.queue_definitions import channel, QUEUE_NAME


def map_new_user(ch, method, properties, body):

    print(body)


channel.basic_consume(queue=QUEUE_NAME, on_message_callback=map_new_user, auto_ack=True)
