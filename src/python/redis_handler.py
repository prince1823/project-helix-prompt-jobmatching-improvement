import json
from datetime import datetime
from my_logger import logger
import redis
from configs import config
import shortuuid
from services import text_service
from services.util_service import send_message


REDIS_HOST = config["redis"]["redis_host"]
REDIS_PORT = config["redis"]["redis_port"]
REDIS_DB = config["redis"]["redis_db"]
redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


def handle_redis_expiry():
    pubsub = redis_client.pubsub()
    # redis_client.config_set('notify-keyspace-events', 'Ex')
    pubsub.psubscribe(config["redis"]["subscribe_pattern"])

    for message in pubsub.listen():
        logger.info(f"[handle_redis_expiry] Received message: {message}")
        if message["type"] == "pmessage":
            expired_key = message["data"]
            if isinstance(expired_key, bytes):
                expired_key = expired_key.decode("utf-8")
            logger.info(f"[handle_redis_expiry] Expired key: {expired_key}")
            try:
                expired_key = f"{expired_key}:latest"
                event = redis_client.get(expired_key)
                if event:
                    logger.info(
                        f"[handle_redis_expiry] Found event for expired key: {expired_key}"
                    )
                    events = json.loads(event.decode("utf-8"))
                    logger.info(
                        f"[handle_redis_expiry] Processing expired key: {expired_key} using backup key"
                    )
                    concat_event_content = "\n".join([i["content"] for i in events])
                    event = events[0]
                    event["content"] = concat_event_content
                    logger.info(
                        f"[handle_redis_expiry] final event content: {event.get('content', '')}"
                    )
                    # Send typing indicator message
                    send_message(
                        response={
                            "chat_id": event["chat_id"],
                            "msg_type": "typing",
                            "receiver_id": event["sender_id"],
                            "sender_id": event["receiver_id"],
                            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "mid": shortuuid.uuid(),
                        },
                        key=expired_key,
                    )
                    text_service.parse_user(event, expired_key)

                    # Clean up the backup key after processing
                    redis_client.delete(expired_key)
                else:
                    logger.warning(
                        f"[handle_redis_expiry] No backup event found for expired key: {expired_key}"
                    )

            except Exception as e:
                logger.error(
                    f"[handle_redis_expiry] Error processing expired key {expired_key}: {e}"
                )


if __name__ == "__main__":
    handle_redis_expiry()
