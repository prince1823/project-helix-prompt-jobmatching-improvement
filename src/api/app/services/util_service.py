import json
from io import BytesIO
from typing import List
from datetime import datetime

import pandas as pd
from kafka import KafkaProducer

from app.core.config import config
from app.core.logger import logger
from app.core.exception import MyException, ErrorMessages

from app.db.postgres import get_db

from app.models.utils import Event
from app.models.applicants import Model
from app.models.user_login import UserDetails, Role

from app.repositories.applicants import Repository as ApplicantsRepository
from app.repositories.conversations import Repository as ConversationRepository


producer = KafkaProducer(
    bootstrap_servers=config["kafka"]["brokers"],
    value_serializer=lambda x: json.dumps(x).encode("utf-8"),
)


def send_message(
    user_details: UserDetails,
    applicant_id: int,
    event: Event,
    key: str,
):
    """
    Sends a response message to the Kafka output topic.
    :param response: The response message to be sent.
    """
    try:
        logger.info(
            f"[send_message] Sending message: {event.model_dump()} with key: {key} to Kafka topic: {config['kafka']['output']['topic']}"
        )
        from app.services.applicants import Service as ApplicantService
        from app.services.conversations import Service as ConversationService

        applicant_repo = ApplicantsRepository(get_db())
        applicant_service = ApplicantService(applicant_repo)
        conversation_repo = ConversationRepository(get_db())
        conversation_service = ConversationService(conversation_repo)
        if event.content and (event.receiver_id != event.sender_id):
            logger.info(
                f"[send_message] Updating response for applicant {applicant_id} by recruiter {user_details.id}"
            )
            # Update response
            applicant_service.update_response(
                user_details=user_details,
                applicant_id=applicant_id,
                response=event.content,
            )
            applicant_repo.close()
            logger.info(
                f"[send_message] Updated response for applicant {applicant_id} by recruiter {user_details.id}"
            )
            # update conversation
            conversation_service.update_conversation(
                user_details=user_details,
                applicant_id=applicant_id,
                event=event,
                role=Role.RECRUITER,
            )
            conversation_repo.close()
        response_event = event.model_dump(exclude_none=True)
        response_event["receiver_id"] = str(event.receiver_id)
        response_event["sender_id"] = str(event.sender_id)
        producer.send(
            topic=config["kafka"]["output"]["topic"],
            key=key.encode("utf-8"),
            value=response_event,
        )
        logger.info(
            f"[send_message] Message {response_event} sent to Kafka topic: {config['kafka']['output']['topic']} with key: {key}"
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


def pydantic_to_xlsx_bytes(pydantic_objects: List[Model]) -> bytes:
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
