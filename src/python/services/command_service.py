import re
from datetime import datetime

import shortuuid

from my_logger import logger
from exceptions import MyException, ErrorMessages
from models import Commands, DisabledBy, LanguageEnum, Applicant, LanguageEnum
from constants import CHAT_DISABLE_SUCCESS, CONTACTS_CHAT_DISABLE_SUCCESS


class CommandService:
    def __init__(self) -> None:
        pass

    def parse_command(self, event: dict, key: str) -> bool:
        """
        Export all the records against the recruiter in an xlsx link
        :param event: Dictionary containing 'chat_id', 'receiver_id', 'sender_id'.
        :param key: partitioning key for kafka message
        """
        try:
            if event["content"].startswith(Commands.DISABLE):
                return self.disable_chat(event, key, DisabledBy.USER)
            elif event["content"].startswith(Commands.EXPORT):
                return self.export_data(event, key)
            else:
                return False
        except MyException as me:
            logger.error(f"[parse_command] MyException occurred: {me}")
            raise me
        except Exception as e:
            logger.error(f"[parse_command] Error parsing command: {e}")
            raise MyException(
                block="parse_command",
                error_code=ErrorMessages.COMMAND_PARSING_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )

    def disable_chat(self, event: dict, key: str, disabled_by: str) -> bool:
        """
        Disable chat for all phone numbers mentioned and contacts
        :param event: Dictionary containing 'chat_id', 'receiver_id', 'sender_id' and 'locale'.
        :param key: partitioning key for kafka message
        """
        try:
            logger.info(f"[cmd_disable_chat] disabling chats for {event}")
            from services import db_service
            from services.util_service import send_message

            pattern_number = r"\b(91\d{10})\b"
            pattern_contacts = r"\bcontacts\b"
            content = ""
            if re.search(pattern_contacts, event["content"].lower()):
                matches = db_service.get_contacts(event["receiver_id"])
                content = CONTACTS_CHAT_DISABLE_SUCCESS.format(len(matches))
            else:
                matches = re.findall(pattern_number, event["content"])
                content = CHAT_DISABLE_SUCCESS.format(matches)
            users = [
                Applicant(recruiter_id=event["receiver_id"], applicant_id=match)
                for match in matches
            ]
            recruiter_id = users[0].recruiter_id
            applicants = [user.applicant_id for user in users]
            db_service.disable_chat(recruiter_id, applicants, disabled_by)
            logger.info(f"[cmd_disable_chat] disable chat for {event} successfull.")
            send_message(
                response={
                    "chat_id": event["chat_id"],
                    "content": content,
                    "msg_type": "text",
                    "receiver_id": event["receiver_id"],
                    "sender_id": event["receiver_id"],
                    "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "mid": shortuuid.uuid(),
                },
                key=key,
                locale=event.get("locale", LanguageEnum.ENGLISH),
                admin=True,
            )
            return True
        except MyException as me:
            logger.error(f"[cmd_disable_chat] MyException occurred: {me}")
            raise me
        except Exception as e:
            logger.error(f"[cmd_disable_chat] Error disabling chat: {e}")
            raise MyException(
                block="cmd_disable_chat",
                error_code=ErrorMessages.CHAT_DISABLE_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )

    def export_data(self, event: dict, key: str):
        """
        Export all the records against the recruiter in an xlsx link
        :param event: Dictionary containing 'chat_id', 'receiver_id', 'sender_id' and 'locale'.
        :param key: partitioning key for kafka message
        """
        try:
            logger.info(f"[export_recruiter_report] ")
            from services import db_service
            from services import document_service
            from services import send_message, pydantic_to_xlsx_bytes

            users = db_service.get_users(
                Applicant(
                    recruiter_id=event["receiver_id"], applicant_id=event["sender_id"]
                )
            )
            if users:
                users_bytes = pydantic_to_xlsx_bytes(users)
                blob_url = document_service.azure_upload_file(
                    {
                        "content": users_bytes,
                        "file_name": f"{users[0].recruiter_id}.xlsx",
                        "mime_type": "application/vnd.openxmlformatsofficedocument.spreadsheetml.sheet",
                    },
                    return_url=True,
                )
                send_message(
                    response={
                        "chat_id": event["chat_id"],
                        "content": blob_url,
                        "msg_type": "text",
                        "receiver_id": event["receiver_id"],
                        "sender_id": event["receiver_id"],
                        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "mid": shortuuid.uuid(),
                    },
                    key=key,
                    locale=event.get("locale", LanguageEnum.ENGLISH),
                    admin=True,
                )
            return True
        except MyException as me:
            logger.error(f"[export_recruiter_report] MyException occurred: {me}")
            raise me
        except Exception as e:
            logger.error(f"[export_recruiter_report] Error saving document: {e}")
            raise MyException(
                block="export_recruiter_report",
                error_code=ErrorMessages.DATA_EXPORT_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )


command_service = CommandService()
