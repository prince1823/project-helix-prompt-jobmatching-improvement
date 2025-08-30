import re
from datetime import datetime

import shortuuid

from app.core.logger import logger
from app.core.authorization import get_user_details
from app.core.exception import MyException, ErrorMessages
from app.core.constants import CONTACTS_CHAT_DISABLE_SUCCESS

from app.models.applicants import Model
from app.models.utils import Commands, UpdatedBy, Event
from app.models.user_login import UserDetails

from app.db.postgres import get_db

from app.repositories.config import Repository as ConfigRepository
from app.repositories.documents import Repository as DocumentRepository
from app.repositories.applicants import Repository as ApplicantRepository
from app.repositories.conversations import Repository as ConversationRepository
from app.repositories.whatsmeow_contacts import Repository as WhatsAppContactsRepository
from app.repositories.job_mandate_questions import (
    Repository as JobMandateQuestionsRepository,
)
from app.repositories.job_mandate_applicants import (
    Repository as JobMandateApplicantsRepository,
)

from app.services.configs import Service as ConfigService
from app.services.documents import Service as DocumentService
from app.services.applicants import Service as ApplicantService
from app.services.conversations import Service as ConversationService
from app.services.whatsmeow_contacts import Service as WhatsAppContactsService
from app.services.job_mandate_questions import Service as JobMandateQuestionsService
from app.services.job_mandate_applicants import Service as JobMandateApplicantsService


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
                return self.disable_chat(event, key, UpdatedBy.USER)
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
            from app.services.util_service import send_message

            pattern_number = r"\b(91\d{10})\b"
            pattern_contacts = r"\bcontacts\b"
            content = ""
            if re.search(pattern_contacts, event["content"].lower()):
                whatsmeow_contacts_repo = WhatsAppContactsRepository(get_db())
                whatsmeow_contacts_service = WhatsAppContactsService(
                    whatsmeow_contacts_repo
                )
                matches = whatsmeow_contacts_service.get_contacts(event["receiver_id"])
                whatsmeow_contacts_repo.close()
            else:
                matches = re.findall(pattern_number, event["content"])
            content = CONTACTS_CHAT_DISABLE_SUCCESS.format(len(matches))
            users = [
                Model(recruiter_id=event["receiver_id"], applicant_id=match)  # type: ignore
                for match in matches
            ]
            recruiter_id = users[0].recruiter_id
            applicants = [user.applicant_id for user in users]
            user_details = get_user_details(x_user_id=str(recruiter_id), db=get_db())
            config_repo = ConfigRepository(get_db())
            config_service = ConfigService(config_repo)
            config_service.update_enabled(
                user_details=user_details,
                applicant_ids=applicants,
                enabled=False,
                updated_by=UpdatedBy.USER,
            )
            config_repo.close()
            logger.info(f"[cmd_disable_chat] disable chat for {event} successfull.")
            response_event = Event(
                chat_id=event["chat_id"],
                content=content,
                msg_type="text",
                receiver_id=recruiter_id,
                sender_id=recruiter_id,
                timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                mid=shortuuid.uuid(),
            )
            send_message(
                user_details=user_details,
                applicant_id=recruiter_id,
                event=response_event,
                key=key,
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
            from app.services.util_service import send_message, pydantic_to_xlsx_bytes

            user_details = get_user_details(x_user_id=event["receiver_id"], db=get_db())
            applicant_repo = ApplicantRepository(get_db())
            applicant_service = ApplicantService(applicant_repo)
            response = applicant_service.get_all(user_details=user_details)
            applicant_repo.close()
            users = response.data
            if users:
                users_bytes = pydantic_to_xlsx_bytes(users)
                document_repo = DocumentRepository(get_db())
                document_service = DocumentService(document_repo)
                blob_url = document_service.azure_upload_file(
                    {
                        "content": users_bytes,
                        "file_name": f"{users[0].recruiter_id}.xlsx",
                        "mime_type": "application/vnd.openxmlformatsofficedocument.spreadsheetml.sheet",
                    },
                    return_url=True,
                )
                document_repo.close()
                response_event = Event(
                    chat_id=event["chat_id"],
                    content=str(blob_url),
                    msg_type="text",
                    receiver_id=user_details.id,
                    sender_id=user_details.id,
                    timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    mid=shortuuid.uuid(),
                )
                send_message(
                    user_details=user_details,
                    applicant_id=user_details.id,
                    event=response_event,
                    key=key,
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

    def reset_applicant(self, user_details: UserDetails, event: dict):
        from app.services.util_service import send_message

        recruiter_id = int(event["receiver_id"])
        applicant_id = int(event["sender_id"])

        applicant_repo = ApplicantRepository(get_db())
        applicant_service = ApplicantService(applicant_repo)
        applicant_service.delete(
            recruiter_id=recruiter_id,
            applicant_id=applicant_id,
        )
        applicant_repo.close()

        conversation_repo = ConversationRepository(get_db())
        conversation_service = ConversationService(conversation_repo)
        conversation_service.delete(
            recruiter_id=recruiter_id,
            applicant_id=applicant_id,
        )
        conversation_repo.close()

        documents_repo = DocumentRepository(get_db())
        documents_service = DocumentService(documents_repo)
        documents_service.delete(
            recruiter_id=recruiter_id,
            applicant_id=applicant_id,
        )
        documents_repo.close()

        job_mandate_questions_repo = JobMandateQuestionsRepository(get_db())
        job_mandate_questions_service = JobMandateQuestionsService(
            job_mandate_questions_repo
        )
        job_mandate_questions_service.delete(
            recruiter_id=recruiter_id,
            applicant_id=applicant_id,
        )
        job_mandate_questions_repo.close()

        job_mandate_applicants_repo = JobMandateApplicantsRepository(get_db())
        job_mandate_applicants_service = JobMandateApplicantsService(
            job_mandate_applicants_repo
        )
        job_mandate_applicants_service.delete(
            recruiter_id=recruiter_id,
            applicant_id=applicant_id,
        )
        job_mandate_applicants_repo.close()

        config_repo = ConfigRepository(get_db())
        config_service = ConfigService(config_repo)
        config_service.delete(
            recruiter_id=recruiter_id,
            applicant_id=applicant_id,
        )
        config_repo.close()


command_service = CommandService()
