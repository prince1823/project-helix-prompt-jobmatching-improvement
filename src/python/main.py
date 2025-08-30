import json
import threading
from datetime import datetime

import shortuuid
from kafka import KafkaConsumer

from schema import init_db
from configs import config
from my_logger import logger
from models import LanguageEnum
from exceptions import ErrorMessages, MyException
from services.util_service import send_message, producer, redis_buffer_manager
from redis_handler import redis_client


def consume_messages():
    """
    Consumes messages from the Kafka input topic and processes them.
    Buffers messages in Redis using SETEX with TTL, aggregating content inside the stored JSON value.
    """
    try:
        from services import audio_service, document_service, db_service

        REDIS_TTL = config["redis"]["redis_ttl"]
        consumer = KafkaConsumer(
            config["kafka"]["ingest"]["topic"],
            bootstrap_servers=config["kafka"]["brokers"],
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            group_id=config["kafka"]["ingest"]["group_id"],
            value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        )
        logger.info(
            f"[consume_messages] Consumer started for topic: {config['kafka']['ingest']['topic']} on brokers: {config['kafka']['brokers']}"
        )

        for message in consumer:
            try:
                event = message.value
                db_service.store_conversation(topic="ingest", event=event)
                key = message.key.decode("utf-8")
                logger.info(
                    f"[consume_messages] Received message: {event} with key: {key}"
                )

                # Handle ChatPresence: reset expiry only if key exists, no buffering
                if event.get("event_type") == "ChatPresence":
                    if redis_client.exists(key):
                        redis_client.expire(key, REDIS_TTL)
                    continue  # Skip further processing

                match event["msg_type"]:
                    case "document":
                        # Process documents immediately, no buffering
                        document_service.save_documents(event, key=key)

                    case "audio":
                        # Transcribe audio before buffering
                        transcript = audio_service.sarvam_translate(event["content"])
                        if "error" in transcript:
                            logger.error(
                                f"[consume_messages] Transcription error: {transcript['error']}"
                            )
                            raise MyException(
                                block="sarvam_translate",
                                error_code=ErrorMessages.TRANSCRIPTION_ERROR,
                                error_message=str(transcript),
                                error_type=transcript.get("error", "Unknown"),
                                timestamp=datetime.now().isoformat(),
                            )
                        event["content"] = transcript["transcript"]
                        event["locale"] = transcript["language_code"]

                        redis_buffer_manager(key, event, REDIS_TTL)

                    case "text":
                        redis_buffer_manager(key, event, REDIS_TTL)
                    case _:
                        raise MyException(
                            block="Invalid case match",
                            error_code=ErrorMessages.MEDIA_NOT_SUPPORTED,
                            error_message=event.get("content", ""),
                            error_type=event.get("msg_type", ""),
                            timestamp=datetime.now().isoformat(),
                        )
            except MyException as me:
                logger.error(f"[consume_messages] Custom exception occurred: {me}")
                producer.send(
                    topic=config["kafka"]["failed"]["topic"],
                    key=key.encode("utf-8") if key else None,
                    value={
                        "error_code": me.error_code,
                        "error_message": me.error_message,
                        "error_type": me.error_type,
                        "timestamp": me.timestamp,
                        "block": me.block,
                        "event": event,
                    },
                )
                for recruiter_config in config["whatsapp"]:
                    if recruiter_config["recruiter_id"] == event["receiver_id"]:
                        send_message(
                            response={
                                "chat_id": f"{recruiter_config['recruiter_id']}@s.whatsapp.net",
                                "content": f"user {event['sender_id']} is facing issue: {me.error_code}",
                                "msg_type": "text",
                                "receiver_id": event["receiver_id"],
                                "sender_id": event["receiver_id"],
                                "timestamp": datetime.now().strftime(
                                    "%Y-%m-%dT%H:%M:%SZ"
                                ),
                                "mid": shortuuid.uuid(),
                            },
                            key=key,
                            locale=event.get("locale", LanguageEnum.ENGLISH),
                            admin=True,
                        )
                        break

            except Exception as e:
                logger.error(f"[consume_messages] Error consuming messages: {e}")
                producer.send(
                    topic=config["kafka"]["failed"]["topic"],
                    key=key.encode("utf-8") if key else None,
                    value={
                        "error_code": "UNKNOWN_ERROR",
                        "error_message": e.args[0] if e.args else str(e),
                        "error_type": e.__class__.__name__,
                        "timestamp": datetime.now().isoformat(),
                        "block": "main_consumer",
                        "event": event,
                    },
                )

    except KeyboardInterrupt:
        consumer.close()
    except Exception as e:
        logger.error(f"[consume_messages] Error consuming messages: {e}")


def consume_admin_messages():
    """
    Consumes messages from the Kafka admin topic and processes them.
    This function initializes a Kafka consumer and listens for messages indefinitely.
    """
    try:
        consumer = KafkaConsumer(
            config["kafka"]["admin"]["topic"],
            bootstrap_servers=config["kafka"]["brokers"],
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            group_id=config["kafka"]["admin"]["group_id"],
            value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        )
        logger.info(
            f"[consume_admin_messages] Consumer started for topic: {config['kafka']['admin']['topic']} on brokers: {config['kafka']['brokers']}"
        )
        from services import command_service

        for message in consumer:
            try:
                event = message.value
                key = message.key.decode("utf-8")
                logger.info(
                    f"[consume_admin_messages] Received message: {event} with key: {key}"
                )
                command_service.parse_command(event, key)
            except MyException as me:
                logger.error(
                    f"[consume_admin_messages] Custom exception occurred: {me}"
                )
                producer.send(
                    topic=config["kafka"]["failed"]["topic"],
                    key=key.encode("utf-8") if key else None,
                    value={
                        "error_code": me.error_code,
                        "error_message": me.error_message,
                        "error_type": me.error_type,
                        "timestamp": me.timestamp,
                        "block": me.block,
                        "event": event,
                    },
                )
                for recruiter_config in config["whatsapp"]:
                    if recruiter_config["recruiter_id"] == event["receiver_id"]:
                        send_message(
                            response={
                                "chat_id": f"{recruiter_config['recruiter_id']}@s.whatsapp.net",
                                "content": f"user {event['sender_id']} is facing issue: {me.error_code}",
                                "msg_type": "text",
                                "receiver_id": event["receiver_id"],
                                "sender_id": event["receiver_id"],
                                "timestamp": datetime.now().strftime(
                                    "%Y-%m-%dT%H:%M:%SZ"
                                ),
                                "mid": event.get("mid", shortuuid.uuid()),
                            },
                            key=key,
                            locale=event.get("locale", LanguageEnum.ENGLISH),
                            admin=True,
                        )
                        break
            except Exception as e:
                logger.error(f"[consume_admin_messages] Error consuming messages: {e}")
                producer.send(
                    topic=config["kafka"]["failed"]["topic"],
                    key=key.encode("utf-8") if key else None,
                    value={
                        "error_code": "UNKNOWN_ERROR",
                        "error_message": e.args[0] if e.args else str(e),
                        "error_type": e.__class__.__name__,
                        "timestamp": datetime.now().isoformat(),
                        "block": "main_consumer",
                        "event": event,
                    },
                )
    except KeyboardInterrupt:
        consumer.close()
    except Exception as e:
        logger.error(f"[consume_admin_messages] Error consuming messages: {e}")


if __name__ == "__main__":
    logger.info("Initializing the database...")
    init_db()

    logger.info("Starting threads...")
    admin_thread = threading.Thread(target=consume_admin_messages)
    message_thread = threading.Thread(target=consume_messages)

    admin_thread.start()
    message_thread.start()

    admin_thread.join()
    message_thread.join()
