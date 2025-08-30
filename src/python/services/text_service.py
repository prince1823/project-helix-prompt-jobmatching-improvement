import os
import json
from datetime import datetime

import shortuuid
from openai import AzureOpenAI
from pydantic import ValidationError

from constants import *
from configs import config
from my_logger import logger
from exceptions import MyException, ErrorMessages
from services.util_service import send_message
from models import (
    LanguageEnum,
    Locale,
    Applicant,
    LLMResponse,
    LocaleUpdate,
    UserWorkflowStatus,
    DisabledBy,
)


class TextService:
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        )

    def infer_user_locale(self, message: str) -> LanguageEnum:
        """
        Infers the user's locale from the message using OpenAI's language model.
        :param message: The message from the user.
        :return: The inferred locale as a string.
        """
        try:
            logger.info(
                f"[infer_user_locale] Inferring user locale from message: {message}"
            )
            locale_schema = {
                "type": "json_schema",
                "json_schema": {
                    "name": "locale_schema",
                    "schema": Locale.model_json_schema(),
                },
            }
            user_response = self.client.chat.completions.create(
                model=config["llm"]["text"]["model"],
                temperature=config["llm"]["text"]["temperature"],
                messages=[
                    {"role": "system", "content": config["llm"]["text"]["locale"]},
                    {"role": "user", "content": message},
                ],
                response_format=locale_schema,  # type: ignore
            )
            return Locale(**json.loads(user_response.choices[0].message.content)).locale  # type: ignore
        except Exception as e:
            logger.error(f"[infer_user_locale] Error inferring user locale: {e}")
            raise MyException(
                block="infer_user_locale",
                error_code=ErrorMessages.LOCALE_INFERENCE_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )

    def translate_text(self, text: str, target_language: str) -> str | None:
        """
        Translates the given text to the specified language using OpenAI's translation model.
        :param text: The text to be translated.
        :return: The translated text.
        """
        try:
            logger.info(
                f"[translate_text] Translating text: {text} to target language: {target_language}"
            )
            response = self.client.chat.completions.create(
                model=config["llm"]["text"]["model"],
                temperature=config["llm"]["text"]["temperature"],
                messages=[
                    {
                        "role": "system",
                        "content": config["llm"]["text"]["translate"].format(
                            target_language
                        ),
                    },
                    {"role": "user", "content": text},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"[translate_text] Error translating text: {e}")
            raise MyException(
                block="translate_text",
                error_code=ErrorMessages.TEXT_TRANSLATION_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )

    def update_user_locale(self, event: dict, key: str) -> None:
        """
        Updates the locale for the user
        :param event: Dict containing sender_id, receiver_id, chat_id and content
        :param key: key for kafka message
        """
        try:
            locale_schema = {
                "type": "json_schema",
                "json_schema": {
                    "name": "ApplicantSchema",
                    "schema": LocaleUpdate.model_json_schema(),
                },
            }
            user_response = self.client.chat.completions.create(
                model=config["llm"]["text"]["model"],
                temperature=config["llm"]["text"]["temperature"],
                messages=[
                    {
                        "role": "system",
                        "content": config["llm"]["text"]["locale_update"],
                    },
                    {"role": "user", "content": f"User message: {event['content']}"},
                ],
                response_format=locale_schema,  # type: ignore
            )
            update_locale = LocaleUpdate(
                **json.loads(user_response.choices[0].message.content)  # type: ignore
            )  # type: ignore
            logger.info(f"[update_user_locale] Update locale response: {update_locale}")
            if update_locale.update:
                applicant = Applicant(
                    applicant_id=event["sender_id"],
                    recruiter_id=event["receiver_id"],
                    locale=update_locale.locale,
                )
                from services import db_service

                applicant_in_db = db_service.update_user_in_db(applicant)
                logger.info(
                    f"[update_user_locale] Updated applicant in database: {applicant_in_db.__dict__}"
                )
                send_message(
                    response={
                        "chat_id": event["chat_id"],
                        "content": LOCALE_UPDATED,
                        "msg_type": "text",
                        "receiver_id": event["sender_id"],
                        "sender_id": event["receiver_id"],
                        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "mid": shortuuid.uuid(),
                    },
                    key=key,
                    locale=applicant.locale,  # type: ignore
                )  # type: ignore
                return applicant_in_db
        except MyException as me:
            logger.error(f"[update_user_locale] MyException occurred: {me}")
            raise me
        except Exception as e:
            logger.error(f"[update_user_locale] Error retrieving user: {e}")
            raise MyException(
                block="update_user_locale",
                error_code=ErrorMessages.USER_LOCALE_UPDATE_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )

    def extract_user_details(self, event: dict, key: str) -> None:
        """
        Extracts user details from the event and updates the user in the database.
        :param user_info: A dictionary containing user information.
        :param event: A dictionary containing the event data.
        :param key: The key for the Kafka message.
        """
        try:
            if event["sender_id"] == event["receiver_id"]:
                return
            user = Applicant(
                applicant_id=event["sender_id"], recruiter_id=event["receiver_id"]
            )
            from services import db_service

            user = db_service.get_user_in_db(user, key)
            if not user:
                logger.info(
                    f"[extract_user_details] User not returned from database, either an error occured or details already completed."
                )
                return
            logger.info(
                f"[extract_user_details] Update user locale if needed: {event['content']}"
            )
            updated_locale = self.update_user_locale(event, key)
            if updated_locale:
                user = Applicant(**updated_locale.__dict__)
            user_info = user.model_dump(exclude_none=True)  # type: ignore
            logger.info(f"[extract_user_details] User info: {user_info}")
            user_info.pop("applicant_id", None)
            user_info.pop("recruiter_id", None)
            user_info.pop("created_at", None)
            user_info.pop("updated_at", None)
            logger.info(
                f"[extract_user_details] Extracting user details from event: {event['content']}, user_info: {user_info}"
            )
            llm_schema = {
                "type": "json_schema",
                "json_schema": {
                    "name": "ApplicantSchema",
                    "schema": LLMResponse.model_json_schema(),
                },
            }
            user_response = self.client.chat.completions.create(
                model=config["llm"]["text"]["model"],
                temperature=config["llm"]["text"]["temperature"],
                messages=[
                    {
                        "role": "system",
                        "content": config["llm"]["text"]["extract_details"],
                    },
                    {
                        "role": "user",
                        "content": f"User message: {event['content']}, Current User details: {user_info}",
                    },
                ],
                response_format=llm_schema,  # type: ignore
            )
            data = LLMResponse(
                **json.loads(user_response.choices[0].message.content)  # type: ignore
            ).model_dump(exclude_none=True)  # type: ignore
            data["applicant_id"] = event["sender_id"]
            data["recruiter_id"] = event["receiver_id"]
            data["locale"] = user_info["locale"]
            data["user_workflow_status"] = UserWorkflowStatus.DETAILS_IN_PROGRESS
            response = data["response"]
            logger.info(f"[extract_user_details] Extracted user details: {data}")
            updated_user = Applicant(**data)
            from services import db_service, command_service
            from services.util_service import completion_validator

            db_user = db_service.update_user_in_db(updated_user)
            logger.info(
                f"[extract_user_details] Updated user in database: {db_user.__dict__}"
            )
            send_message(
                response={
                    "chat_id": event["chat_id"],
                    "content": response,
                    "msg_type": "text",
                    "receiver_id": event["sender_id"],
                    "sender_id": event["receiver_id"],
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "mid": shortuuid.uuid(),
                },
                key=key,
                locale=user_info["locale"],
            )
            if completion_validator(db_user):
                logger.info(
                    f"[extract_user_details] All details captured, disabling bot on this chat."
                )
                updated_user = Applicant(
                    applicant_id=event["sender_id"],
                    recruiter_id=event["receiver_id"],
                    user_workflow_status=UserWorkflowStatus.DETAILS_COMPLETED,
                )
                db_user = db_service.update_user_in_db(updated_user)
                for i in config["whatsapp"]:
                    if i["recruiter_id"] == event["receiver_id"]:
                        command_service.disable_chat(
                            {
                                "content": f"/disable {event['sender_id']}",
                                "sender_id": event["receiver_id"],
                                "receiver_id": event["receiver_id"],
                                "chat_id": f"{i['recruiter_id']}@s.whatsapp.net",
                            },
                            key,
                            DisabledBy.SYSTEM,
                        )
                        break
        except MyException as me:
            logger.error(f"[extract_user_details] MyException occurred: {me}")
            raise me
        except ValidationError as ve:
            logger.error(f"[extract_user_details] Validation error: {ve}")
            validation_response = self.client.chat.completions.create(
                model=config["llm"]["text"]["model"],
                temperature=config["llm"]["text"]["temperature"],
                messages=[
                    {"role": "system", "content": config["llm"]["text"]["validation"]},
                    {"role": "user", "content": f"Error message: {ve}"},
                ],
            )
            data = validation_response.choices[0].message.content  # type: ignore
            send_message(
                response={
                    "chat_id": event["chat_id"],
                    "content": data,
                    "msg_type": "text",
                    "receiver_id": event["sender_id"],
                    "sender_id": event["receiver_id"],
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "mid": shortuuid.uuid(),
                },
                key=key,
                locale=user_info["locale"],
            )
        except Exception as e:
            logger.error(f"[extract_user_details] Error extracting user details: {e}")
            raise MyException(
                block="extract_user_details",
                error_code=ErrorMessages.USER_DETAIL_EXTRACTION_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )

    def parse_user(self, event: dict, key: str) -> None:
        """
        Parses the user details from the event and call appropriate service
        :param event: A dictionary containing the event data.
        :param key: The key for the Kafka message.
        """
        try:
            logger.info(f"[parse_user] Parsing user details from event: {event}")
            # get user details from the database
            user = Applicant(
                applicant_id=event["sender_id"], recruiter_id=event["receiver_id"]
            )
            from services import db_service

            user_workflow_status = db_service.get_user_status_in_db(user)
            user.user_workflow_status = user_workflow_status
            if user_workflow_status == UserWorkflowStatus.NOT_INITIATED:
                logger.info(
                    f"[parse_user] User not found in database, creating new user."
                )
                send_message(  # type: ignore
                    response={
                        "chat_id": event["chat_id"],
                        "content": INTRODUCTION_MESSAGE,
                        "msg_type": "text",
                        "receiver_id": event["sender_id"],
                        "sender_id": event["receiver_id"],
                        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "mid": shortuuid.uuid(),
                    },
                    key=key,
                    locale=event.get("locale", LanguageEnum.ENGLISH),
                )
                db_user = db_service.get_user_in_db(user, key)
            if user_workflow_status == UserWorkflowStatus.INITIATED:
                logger.info(f"[parse_user] User already initiated, extracting details.")
                user = db_service.get_user_in_db(user, key)
                user.locale = self.infer_user_locale(event["content"])  # type: ignore
                db_service.update_user_in_db(user)  # type: ignore
                self.extract_user_details(event, key)
            if user_workflow_status == UserWorkflowStatus.DETAILS_IN_PROGRESS:
                logger.info(
                    f"[parse_user] User details in progress, extracting details."
                )
                self.extract_user_details(event, key)
            if user_workflow_status == UserWorkflowStatus.DETAILS_COMPLETED:
                logger.info(
                    f"[parse_user] User details already completed, no action needed."
                )
                user = db_service.get_user_in_db(user, key)  # type: ignore
        except MyException as me:
            logger.error(f"[parse_user] MyException occurred: {me}")
            raise me
        except Exception as e:
            logger.error(f"[parse_user] Error parsing user details: {e}")
            raise MyException(
                block="parse_user",
                error_code=ErrorMessages.USER_PARSING_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )


text_service = TextService()
