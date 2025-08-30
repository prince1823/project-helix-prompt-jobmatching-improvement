import json
from datetime import datetime

import redis
import shortuuid
from kafka import KafkaConsumer

from app.db.postgres import get_db

from app.core.config import config
from app.core.logger import logger
from app.core.authorization import get_user_details
from app.core.exception import ErrorMessages, MyException

from app.models.utils import Event

from app.services.util_service import send_message, producer
from app.services.documents import Service as DocumentService
from app.services.redis_service import Service as RedisService

from app.repositories.documents import Repository as Repository


class Service:
    def __init__(self):
        self.output_consumer = KafkaConsumer(
            config["kafka"]["ingest"]["topic"],
            bootstrap_servers=config["kafka"]["brokers"],
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            group_id=config["kafka"]["ingest"]["group_id"],
            value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        )
        self.redis_client = redis.Redis(
            host=config["redis"]["host"],
            port=config["redis"]["port"],
            db=config["redis"]["multiline"]["db"],
        )
        self.redis_ttl = config["redis"]["multiline"]["ttl"]

    def consume_candidate_messages(self):
        """
        Consumes messages from the Kafka input topic and processes them.
        This function initializes a Kafka consumer and listens for messages indefinitely.
        """
        try:
            logger.info(
                "[consume_messages] Starting Kafka consumer on %s",
                self.output_consumer.config["group_id"],
            )
            for message in self.output_consumer:
                try:
                    key = message.key.decode("utf-8")
                    event = message.value
                    user_details = get_user_details(
                        x_user_id=str(event["receiver_id"]), db=get_db()
                    )
                    logger.debug(f"[consume_messages] Received message: {event}")
                    if event.get("event_type") == "ChatPresence":
                        if self.redis_client.exists(key):
                            self.redis_client.expire(key, self.redis_ttl)
                        continue  # Skip further processing
                    redis_service = RedisService(config["redis"]["multiline"]["db"])
                    match event["msg_type"]:
                        case "document":
                            document_repository = Repository(get_db())
                            document_service = DocumentService(document_repository)
                            # Process documents immediately, no buffering
                            doc_event = Event(
                                mid=event.get("mid", shortuuid.uuid()),
                                timestamp=event.get(
                                    "timestamp",
                                    datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                                ),
                                chat_id=event["chat_id"],
                                sender_id=event["sender_id"],
                                receiver_id=event["receiver_id"],
                                content=event["content"],
                                msg_type=event["msg_type"],
                                mime_type=event.get("mime_type", None),
                            )
                            document_service.process_document(doc_event)
                            document_repository.close()
                        case "audio":
                            from app.services.audio_service import audio_service

                            # Transcribe audio before buffering
                            transcript = audio_service.sarvam_translate(
                                event["content"]
                            )
                            if not transcript:
                                logger.error(
                                    "[consume_messages] Transcription failed: No transcript returned"
                                )
                            else:
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
                                redis_service.multi_line_handler(
                                    key, event, self.redis_ttl
                                )
                        case "text":
                            redis_service.multi_line_handler(key, event, self.redis_ttl)
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
                    response_event = Event(
                        mid=shortuuid.uuid(),
                        chat_id=f"{event['receiver_id']}@s.whatsapp.net",
                        content=f"user {event['sender_id']} is facing issue: {me.error_code}",
                        msg_type="text",
                        receiver_id=event["receiver_id"],
                        sender_id=event["receiver_id"],
                        timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    )
                    for recruiter_config in config["whatsapp"]:
                        if recruiter_config["recruiter_id"] == event["receiver_id"]:
                            send_message(
                                user_details=user_details,
                                applicant_id=event["sender_id"],
                                event=response_event,
                                key=key,
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
            self.output_consumer.close()
        except Exception as e:
            logger.error(f"[consume_messages] Error consuming messages: {e}")

    def consume_admin_messages(self):
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
            from app.services.command_service import command_service

            for message in consumer:
                try:
                    event = message.value
                    user_details = get_user_details(
                        x_user_id=str(event["receiver_id"]), db=get_db()
                    )
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
                    response_event = Event(
                        mid=shortuuid.uuid(),
                        chat_id=f"{event['receiver_id']}@s.whatsapp.net",
                        content=f"user {event['sender_id']} is facing issue: {me.error_code}",
                        msg_type="text",
                        receiver_id=event["receiver_id"],
                        sender_id=event["receiver_id"],
                        timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    )
                    for recruiter_config in config["whatsapp"]:
                        if recruiter_config["recruiter_id"] == event["receiver_id"]:
                            send_message(
                                user_details=user_details,
                                applicant_id=event["sender_id"],
                                event=response_event,
                                key=key,
                            )
                            break
                except Exception as e:
                    logger.error(
                        f"[consume_admin_messages] Error consuming messages: {e}"
                    )
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
