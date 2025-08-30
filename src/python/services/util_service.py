import json
from io import BytesIO
from typing import List
from datetime import datetime

import pandas as pd

from configs import config
from my_logger import logger
from exceptions import MyException, ErrorMessages
from models import Applicant, LanguageEnum
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers=config["kafka"]["brokers"],
    value_serializer=lambda x: json.dumps(x).encode("utf-8"),
)


def send_message(
    response: dict,
    key: str,
    locale: LanguageEnum = LanguageEnum.ENGLISH,
    admin: bool = False,
):
    """
    Sends a response message to the Kafka output topic.
    :param response: The response message to be sent.
    """
    try:
        logger.info(
            f"[send_message] Sending message: {response} with key: {key} in locale: {locale} to Kafka topic: {config['kafka']['output']['topic']}"
        )
        if locale != LanguageEnum.ENGLISH:
            from services import text_service

            translated_response_msg = text_service.translate_text(
                response["content"], locale
            )
            if translated_response_msg:
                response["content"] = translated_response_msg

        if "content" in response and not admin:
            response["llm_version"] = config["llm"]["text"]["version"]
            from services import db_service  # type: ignore

            db_service.update_response(response)
            db_service.store_conversation(topic="output", event=response)
        producer.send(
            topic=config["kafka"]["output"]["topic"],
            key=key.encode("utf-8") if key else None,
            value=response,
        )
        logger.info(
            f"[send_message] Message {response} sent to Kafka topic: {config['kafka']['output']['topic']} with key: {key}"
        )
    except Exception as e:
        logger.error(f"[send_message] Error sending message to Kafka: {e}")
        raise MyException(
            block="send_message",
            error_code=ErrorMessages.KAFKA_MESSAGE_SEND_FAILED,
            error_message=str(e),
            error_type=type(e).__name__,
            timestamp=datetime.now().isoformat(),
        )


def pydantic_to_xlsx_bytes(pydantic_objects: List[Applicant]) -> bytes:
    """
    Convert list of Pydantic objects to XLSX byte array
    :param pydantic_objects: List of Pydantic model instances
    :return bytes: XLSX file as byte array
    """
    try:
        if not pydantic_objects:
            df = pd.DataFrame()
        else:
            data = [obj.model_dump() for obj in pydantic_objects]
            df = pd.DataFrame(data)
            df.drop(
                ["locale", "created_at", "updated_at", "response"], axis=1, inplace=True
            )
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Data")
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        logger.error(f"[pydantic_to_xlsx_bytes] Error saving document: {e}")
        raise MyException(
            block="pydantic_to_xlsx_bytes",
            error_code=ErrorMessages.REPORT_GENERATION_FAILED,
            error_message=str(e),
            error_type=type(e).__name__,
            timestamp=datetime.now().isoformat(),
        )


def completion_validator(db_user: Applicant) -> bool:
    """
    validates the applicant if all the details are collected
    :parm Applicant:Applicant objects
    :return bool
    """
    completed = True
    for key_, value in db_user.__dict__.items():
        if value is None:
            logger.info(f"[extract_user_details] {key_} value is not set.")
            if key_ == "notice_period":
                if not db_user.currently_employed:
                    logger.info(
                        f"[extract_user_details] {key_} value is not set because user is currently not employed."
                    )
                    continue
            completed = False
            break
    return completed


def applicant_completion_data(result: Applicant) -> str:
    return (
        f"Applicant {result.name}: {result.applicant_id} completed basic details with recruiter {result.recruiter_id}.\n"
        f"Email: {result.email or 'N/A'}\n"
        f"Age: {result.age}\n"
        f"gender: {result.gender}\n"
        f"postal_code: {result.postal_code}\n"
        f"languages: {result.languages}\n"
        f"Education: {result.highest_education_qualification or 'N/A'}\n"
        f"Experience: {result.years_experience or 0} yrs\n"
        f"work_preferences: {result.work_preferences}\n"
        f"monthly_salary_expectation: {result.monthly_salary_expectation}\n"
        f"Currently Employed: {'Yes' if result.currently_employed else 'No'}\n"
        f"City: {result.city or 'N/A'}\n"
        f"Has 2-Wheeler: {'Yes' if result.has_2_wheeler else 'No'}\n"
    )


def redis_buffer_manager(key: str, event: dict, REDIS_TTL: any) -> None:
    from redis_handler import redis_client
    # update content in Redis
    msg_buffer = redis_client.get(f"{key}:latest")
    if msg_buffer:
        logger.info(
            f"[redis_buffer_manager] Found existing buffer for key: {key}, updating content."
        )
        events = json.loads(msg_buffer.decode("utf-8"))
        events.append(event)
        updated_events = json.dumps(events).encode("utf-8")
        redis_client.setex(key, REDIS_TTL, updated_events)
        redis_client.set(f"{key}:latest", updated_events)
    else:
        logger.info(
            f"[redis_buffer_manager] No existing buffer found for key: {key}, creating new buffer."
        )
        raw_json = json.dumps([event]).encode("utf-8")
        redis_client.setex(key, REDIS_TTL, raw_json)
        redis_client.set(f"{key}:latest", raw_json)
