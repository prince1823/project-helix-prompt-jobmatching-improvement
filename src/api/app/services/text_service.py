import os
import json
from datetime import datetime
from typing import Optional, Dict, Any

import shortuuid
from openai import AzureOpenAI
from fastapi import HTTPException

from app.db.postgres import get_db

from app.core.constants import *
from app.core.config import config
from app.core.logger import logger
from app.core.authorization import get_user_details
from app.core.exception import MyException, ErrorMessages

from app.services.job_service import job_service
from app.services.util_service import send_message
from app.services.documents import Service as DocumentService
from app.services.applicants import Service as ApplicantService
from app.services.conversations import Service as ConversationService

from app.models.utils import Event
from app.models.user_login import UserDetails, Role
from app.models.applicants import Model as ApplicantModel, Status as ApplicantStatus
from app.models.llm import (
    BasicDetails,
    BasicDetailsSteps,
    IntentModel,
    InterruptModel,
    IntentEnum,
)

from app.repositories.documents import Repository as DocumentRepository
from app.repositories.applicants import Repository as ApplicantsRepository
from app.repositories.conversations import Repository as ConversationRepository


class TextService:
    """
    Service class for handling text-based interactions with applicants.

    This service provides functionality for:
    - Text translation using Azure OpenAI
    - Extracting and processing applicant details
    - Intent classification and handling
    - Managing conversation flow and responses
    - Handling interruptions and follow-ups

    Attributes:
        config: Application configuration settings
        client: Azure OpenAI client instance
        config_repo: Configuration repository
        applicant_repo: Applicants repository
        applicant_service: Applicants service
        conversation_repo: Conversations repository
        conversation_service: Conversations service
    """

    def __init__(self):
        """
        Initialize the TextService with database session and required dependencies.

        Args:
            db (Session): SQLAlchemy database session

        Raises:
            Exception: If Azure OpenAI configuration is missing or invalid
        """
        logger.info("[TextService.__init__] Initializing TextService")

        try:
            self.config = config
            # Initialize Azure OpenAI client
            logger.debug("[TextService.__init__] Setting up Azure OpenAI client")
            self.client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
                azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            )
        except Exception as e:
            logger.error(
                f"[TextService.__init__] Failed to initialize TextService: {e}"
            )
            raise

    def translate_text(self, text: str, target_language: str) -> Optional[str]:
        """
        Translates the given text to the specified language using Azure OpenAI's translation model.

        Args:
            text (str): The text to be translated
            target_language (str): The target language for translation

        Returns:
            Optional[str]: The translated text, or None if translation fails

        Raises:
            MyException: If translation process fails with specific error details
        """
        logger.info(
            f"[TextService.translate_text] Starting translation - Text length: {len(text)}, Target: {target_language}"
        )

        try:
            logger.debug(
                f"[TextService.translate_text] Input text: {text[:100]}..."
                if len(text) > 100
                else f"[TextService.translate_text] Input text: {text}"
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

            translated_text = response.choices[0].message.content
            logger.info(
                f"[TextService.translate_text] Translation completed successfully"
            )
            logger.debug(
                f"[TextService.translate_text] Translated text: {translated_text[:100]}..."
                if translated_text and len(translated_text) > 100
                else f"[TextService.translate_text] Translated text: {translated_text}"
            )

            return translated_text

        except Exception as e:
            logger.error(
                f"[TextService.translate_text] Translation failed: {e}", exc_info=True
            )
            raise MyException(
                block="translate_text",
                error_code=ErrorMessages.TEXT_TRANSLATION_FAILED,
                error_message=str(e),
                error_type=type(e).__name__,
                timestamp=datetime.now().isoformat(),
            )

    def get_basic_details(
        self, user_details: UserDetails, applicant: ApplicantModel, content: str
    ) -> None:
        """
        Extracts and updates basic applicant details using AI analysis of conversation.

        This method uses Azure OpenAI to analyze the conversation history and extract
        relevant applicant information such as name, contact details, experience, etc.
        It then updates the applicant record and sends an appropriate response.

        Args:
            user_details (UserDetails): User id and role object
            applicant (ApplicantModel): The applicant model instance
            content (str): The latest message content from the applicant

        Raises:
            Exception: If AI processing or database operations fail
        """
        logger.info(
            f"[TextService.get_basic_details] Processing basic details for applicant {applicant.applicant_id}"
        )

        try:
            # Initialize a new Azure OpenAI client for this operation
            logger.debug(
                "[TextService.get_basic_details] Initializing Azure OpenAI client"
            )
            client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
                azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            )

            # Prepare the LLM schema for structured output
            logger.debug("[TextService.get_basic_details] Setting up LLM schema")
            llm_schema = {
                "type": "json_schema",
                "json_schema": {
                    "name": "ApplicantSchema",
                    "schema": BasicDetails.model_json_schema(),
                },
            }

            # Get system prompt and conversation history
            system_prompt = self.config["llm"]["gather_basic_details"]["prompt"]
            logger.debug(
                "[TextService.get_basic_details] Fetching conversation history"
            )
            conversation_repo = ConversationRepository(get_db())
            conversation_service = ConversationService(conversation_repo)
            history = conversation_service.get_history(
                user_details, applicant_id=applicant.applicant_id
            )
            conversation_repo.close()
            history = [{"role": i.role, "content": i.content} for i in history]

            # Prepare current applicant data
            current_data = (
                applicant.details.model_dump(exclude_none=True)
                if applicant.details
                else {}
            )
            logger.debug(
                f"[TextService.get_basic_details] Current data keys: {list(current_data.keys()) if current_data else 'None'}"
            )

            # Make AI completion request
            logger.info(
                "[TextService.get_basic_details] Sending request to Azure OpenAI"
            )
            completion = client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "conversation_history": history[-10:],
                                "current_data": current_data,
                                "latest_user_message": content,
                            }
                        ),
                    },
                ],
                temperature=0,
                response_format=llm_schema,  # type: ignore
            )

            # Parse AI response
            content = completion.choices[0].message.content or ""
            logger.debug("[TextService.get_basic_details] Processing AI response")
            data = BasicDetails.model_validate(json.loads(content))

            # Update applicant details
            logger.info("[TextService.get_basic_details] Updating applicant details")
            applicant_repo = ApplicantsRepository(get_db())
            applicant_service = ApplicantService(applicant_repo)
            applicant_service.update_details(
                user_details=user_details,
                applicant_id=applicant.applicant_id,
                details=data.updated_data.model_dump(exclude_none=True),
            )

            # Update applicant status based on completeness
            new_status = (
                ApplicantStatus.DETAILS_COMPLETED
                if data.next_step == BasicDetailsSteps.REQUEST_RESUME
                else ApplicantStatus.INITIATED
                if data.next_step == BasicDetailsSteps.ASK_AGE
                else ApplicantStatus.DETAILS_IN_PROGRESS
            )
            if new_status == ApplicantStatus.DETAILS_COMPLETED:
                document_repo = DocumentRepository(get_db())
                document_service = DocumentService(document_repo)
                try:
                    document = document_service.get_by_recruiter_applicant(
                        user_details=user_details,
                        recruiter_id=user_details.id,
                        applicant_id=applicant.applicant_id,
                    )
                except HTTPException as e:
                    document = None
                if document:
                    data.response_to_user = ALL_DETAILS_RESUME_RECEIVED
            # Create event for conversation tracking
            logger.debug("[TextService.get_basic_details] Creating conversation event")
            event = Event(
                chat_id=f"{applicant.applicant_id}@s.whatsapp.net",
                content=data.response_to_user,
                msg_type="text",
                receiver_id=applicant.applicant_id,
                sender_id=user_details.id,
                timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                mid=shortuuid.uuid(),
            )

            # update status if required
            if applicant.status != new_status:
                logger.info(
                    f"[TextService.get_basic_details] Updating applicant status to: {new_status}"
                )

                applicant_service.update_status(
                    user_details=user_details,
                    applicant_id=applicant.applicant_id,
                    status=new_status,
                )
            applicant_repo.close()

            # Send message response
            logger.debug("[TextService.get_basic_details] Sending message response")
            send_message(
                user_details=user_details,
                applicant_id=applicant.applicant_id,
                event=event,
                key=f"{user_details.id}_{applicant.applicant_id}",
            )
            if new_status == ApplicantStatus.DETAILS_COMPLETED:
                try:
                    matching_jobs = job_service.get_matching_jobs(
                        user_details, applicant.applicant_id
                    )
                    job_service.offer_new_job(
                        user_details=user_details, applicant_id=applicant.applicant_id
                    )
                except Exception as e:
                    event = Event(
                        chat_id=f"{applicant.applicant_id}@s.whatsapp.net",
                        content=NO_JOB_OFFERS_MESSAGE,
                        msg_type="text",
                        receiver_id=applicant.applicant_id,
                        sender_id=user_details.id,
                        timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        mid=shortuuid.uuid(),
                    )
                    send_message(
                        user_details=user_details,
                        applicant_id=applicant.applicant_id,
                        event=event,
                        key=f"{user_details.id}_{applicant.applicant_id}",
                    )
            logger.info(
                f"[TextService.get_basic_details] Successfully processed basic details for applicant {applicant.applicant_id}"
            )

        except Exception as e:
            logger.error(
                f"[TextService.get_basic_details] Failed to process basic details for applicant {applicant.applicant_id}: {e}",
                exc_info=True,
            )
            raise

    def extract_intent(self, applicant: ApplicantModel, content: str) -> IntentEnum:
        """
        Extracts the intent from the applicant's message using AI classification.

        This method analyzes the applicant's message content and current status
        to determine the intent behind their communication (e.g., job inquiry,
        interruption, follow-up question, etc.).

        Args:
            applicant (ApplicantModel): The applicant model instance
            content (str): The message content to analyze

        Returns:
            IntentEnum: The classified intent of the message

        Raises:
            Exception: If AI processing fails or response parsing fails
        """
        logger.info(
            f"[TextService.extract_intent] Extracting intent for applicant {applicant.applicant_id}"
        )
        logger.debug(
            f"[TextService.extract_intent] Applicant status: {applicant.status}, Content length: {len(content)}"
        )

        try:
            # Initialize Azure OpenAI client
            logger.debug(
                "[TextService.extract_intent] Initializing Azure OpenAI client"
            )
            client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
                azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            )

            # Prepare LLM schema for intent classification
            llm_schema = {
                "type": "json_schema",
                "json_schema": {
                    "name": "ApplicantSchema",
                    "schema": IntentModel.model_json_schema(),
                },
            }

            system_prompt = self.config["llm"]["extract_intent"]["prompt"]

            # history = self.conversation_service.get_history(
            #     user_details, applicant_id=applicant.applicant_id
            # )
            # history = [{"role": i.role, "content": i.content} for i in history]
            # Prepare current applicant data

            user_data = {
                "details": applicant.details.model_dump(exclude_none=True)
                if applicant.details
                else {},
                "status": applicant.status.value,
                "last_recruiter_message": applicant.response
                if applicant.response
                else "",
            }
            # Make AI completion request for intent extraction
            logger.debug(
                "[TextService.extract_intent] Sending intent extraction request to Azure OpenAI"
            )
            completion = client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "user_data": user_data,
                                "latest_user_message": content,
                            }
                        ),
                    },
                ],
                temperature=0,
                response_format=llm_schema,  # type: ignore
            )

            # Parse response
            content = completion.choices[0].message.content or ""
            data = IntentModel.model_validate(json.loads(content))

            logger.info(
                f"[TextService.extract_intent] Intent extracted successfully: {data.classification} for applicant {applicant.applicant_id}"
            )
            return data.classification

        except Exception as e:
            logger.error(
                f"[TextService.extract_intent] Failed to extract intent for applicant {applicant.applicant_id}: {e}",
                exc_info=True,
            )
            raise

    def interrupt_handler(
        self, user_details: UserDetails, applicant: ApplicantModel, content: str
    ) -> None:
        """
        Handles interruption messages from applicants during the conversation flow.

        This method processes messages that interrupt the normal flow of conversation,
        such as questions about the process, clarifications, or concerns. It generates
        appropriate responses using AI and updates the conversation history.

        Args:
            user_details (Any): User/recruiter details object
            applicant (ApplicantModel): The applicant model instance
            content (str): The interruption message content

        Raises:
            Exception: If AI processing or message sending fails
        """
        logger.info(
            f"[TextService.interrupt_handler] Handling interruption for applicant {applicant.applicant_id}"
        )
        logger.debug(
            f"[TextService.interrupt_handler] Interruption content length: {len(content)}"
        )

        try:
            # Initialize Azure OpenAI client
            logger.debug(
                "[TextService.interrupt_handler] Initializing Azure OpenAI client"
            )
            client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
                azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            )

            # Prepare LLM schema for interrupt handling
            llm_schema = {
                "type": "json_schema",
                "json_schema": {
                    "name": "ApplicantSchema",
                    "schema": InterruptModel.model_json_schema(),
                },
            }
            system_prompt = self.config["llm"]["interrupt_handler"]["prompt"]

            # Get conversation history and current data
            logger.debug(
                "[TextService.interrupt_handler] Fetching conversation context"
            )
            conversation_repo = ConversationRepository(get_db())
            conversation_service = ConversationService(conversation_repo)
            history = conversation_service.get_history(
                user_details, applicant_id=applicant.applicant_id
            )
            conversation_repo.close()
            history = [{"role": i.role, "content": i.content} for i in history]
            current_data = (
                applicant.details.model_dump(exclude_none=True)
                if applicant.details
                else {}
            )
            latest_job = job_service.get_latest_job(applicant.applicant_id)

            # Make AI completion request
            logger.debug(
                "[TextService.interrupt_handler] Sending interrupt handling request to Azure OpenAI"
            )
            completion = client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "CONVERSATION_HISTORY": history[-10:],
                                "APPLICANT_DETAILS": current_data,
                                "JOB_CONTEXT": latest_job.job_mandate.job_information.description,
                                "LATEST_USER_MESSAGE": content,
                            }
                        ),
                    },
                ],
                temperature=0,
                response_format=llm_schema,  # type: ignore
            )

            # Parse response
            content = completion.choices[0].message.content or ""
            data = InterruptModel.model_validate(json.loads(content))

            # Create event for conversation tracking
            event = Event(
                chat_id=f"{applicant.applicant_id}@s.whatsapp.net",
                content=data.response_text,
                msg_type="text",
                receiver_id=applicant.applicant_id,
                sender_id=user_details.id,
                timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                mid=shortuuid.uuid(),
            )

            # Send response message
            logger.debug(
                "[TextService.interrupt_handler] Sending interrupt response message"
            )
            send_message(
                user_details=user_details,
                applicant_id=applicant.applicant_id,
                event=event,
                key=f"{user_details.id}_{applicant.applicant_id}",
            )

            logger.info(
                f"[TextService.interrupt_handler] Successfully handled interruption for applicant {applicant.applicant_id}"
            )

        except Exception as e:
            logger.error(
                f"[TextService.interrupt_handler] Failed to handle interruption for applicant {applicant.applicant_id}: {e}",
                exc_info=True,
            )
            raise

    def follow_up_handler(self, applicant: ApplicantModel, content: str) -> None:
        """
        Handles follow-up messages from applicants after initial application processing.

        This method processes follow-up queries, administrative messages, and
        post-application communications. Currently a placeholder for future implementation.

        Args:
            user_details (Any): User/recruiter details object
            applicant (ApplicantModel): The applicant model instance
            content (str): The follow-up message content

        Note:
            This method is currently not implemented and serves as a placeholder
            for future follow-up handling functionality.
        """
        logger.info(
            f"[TextService.follow_up_handler] Processing follow-up for applicant {applicant.applicant_id}"
        )
        logger.debug(
            f"[TextService.follow_up_handler] Follow-up content length: {len(content)}"
        )

        # TODO: Implement follow-up handling logic
        logger.warning(
            "[TextService.follow_up_handler] Follow-up handler not yet implemented"
        )
        pass

    def parse_intent(
        self,
        intent: IntentEnum,
        user_details: UserDetails,
        applicant: ApplicantModel,
        event: dict,
        key: str,
    ) -> None:
        """
        Parses the intent of an applicant's message and routes it to appropriate handlers.

        This method acts as a dispatcher that:
        1. Extracts the intent from the message using AI
        2. Routes the message to the appropriate handler based on intent
        3. Handles special cases like greeting messages from non-initiated applicants

        Intent routing:
        - INTERRUPT -> interrupt_handler()
        - FOLLOW_UP_* or BROADCASTS_* -> follow_up_handler()
        - SIMPLE_AFFIRMATIONS_* (for NOT_INITIATED) -> treated as JOB_INQUIRY
        - JOB_INQUIRY_INITIAL_CONTACT -> get_basic_details()

        Args:
            user_details (Any): User/recruiter details object
            applicant (ApplicantModel): The applicant model instance
            content (str): The message content to analyze and route

        Raises:
            Exception: If intent extraction or handling fails
        """
        logger.info(
            f"[TextService.parse_intent] Parsing intent for applicant {applicant.applicant_id}"
        )
        logger.debug(
            f"[TextService.parse_intent] Applicant status: {applicant.status}, Content: {event['content'][:50]}..."
        )

        try:
            # Route based on intent
            if intent == IntentEnum.INTERRUPT:
                logger.debug("[TextService.parse_intent] Routing to interrupt handler")
                self.interrupt_handler(user_details, applicant, event["content"])

            elif intent in [
                IntentEnum.BROADCASTS_ADVERTISEMENTS_ADMINISTRATIVE_MESSAGES,
            ]:
                logger.debug("[TextService.parse_intent] Routing to follow-up handler")
                self.follow_up_handler(applicant, event["content"])

            elif intent in [
                IntentEnum.JOB_INQUIRY_INITIAL_CONTACT,
                IntentEnum.APPLICATION_SUBMISSION,
                IntentEnum.SIMPLE_AFFIRMATIONS_REJECTIONS_GREETINGS,
                IntentEnum.FOLLOW_UP_POST_APPLICATION_QUERIES,
            ]:
                # Handle based on applicant status
                if applicant.status == ApplicantStatus.NOT_INITIATED:
                    logger.info(
                        "[TextService.parse_event] Sending introduction message to new applicant"
                    )

                    # Send introduction message for new applicants
                    introduction_event = Event(
                        chat_id=event["chat_id"],
                        content=INTRODUCTION_MESSAGE,
                        msg_type="text",
                        receiver_id=event["sender_id"],
                        sender_id=event["receiver_id"],
                        timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        mid=shortuuid.uuid(),
                    )
                    logger.debug(
                        "[TextService.parse_event] Sending introduction message"
                    )
                    send_message(
                        user_details=user_details,
                        applicant_id=applicant.applicant_id,
                        event=introduction_event,
                        key=key,
                    )
                    applicant_repo = ApplicantsRepository(get_db())
                    applicant_service = ApplicantService(applicant_repo)
                    applicant_service.update_status(
                        user_details=user_details,
                        applicant_id=applicant.applicant_id,
                        status=ApplicantStatus.INITIATED,
                    )
                    applicant_repo.close()
                elif applicant.status in [
                    ApplicantStatus.INITIATED,
                    ApplicantStatus.DETAILS_IN_PROGRESS,
                    # ApplicantStatus.AWAITING_RESUME,
                ]:
                    logger.debug(
                        "[TextService.parse_intent] Routing to basic details handler"
                    )
                    self.get_basic_details(user_details, applicant, event["content"])

                elif applicant.status in [
                    ApplicantStatus.DETAILS_COMPLETED,
                    ApplicantStatus.MANDATE_MATCHING,
                ]:
                    # logger.info(
                    #     f"[TextService.parse_event] No action needed for applicant status: {applicant.status}"
                    # )
                    # matching_jobs = self.get_matching_jobs(
                    #     user_details, applicant.applicant_id
                    # )
                    logger.debug(f"[TextService.parse_event] Processing job flow with")
                    job_service.parse_job(event, key)

            logger.info(
                f"[TextService.parse_intent] Successfully processed intent {intent} for applicant {applicant.applicant_id}"
            )

        except Exception as e:
            logger.error(
                f"[TextService.parse_intent] Failed to parse intent for applicant {applicant.applicant_id}: {e}",
                exc_info=True,
            )
            raise

    def parse_event(self, event: Dict[str, Any], key: str) -> None:
        """
        Parses incoming WhatsApp events and processes them based on applicant status.

        This is the main entry point for processing incoming messages from applicants.
        It handles different applicant statuses and routes messages accordingly:

        - NOT_INITIATED: Sends introduction message
        - INITIATED/DETAILS_IN_PROGRESS: Processes message through intent parsing

        Args:
            event (Dict[str, Any]): Dictionary containing the WhatsApp event data with keys:
                - receiver_id: The recruiter/user ID receiving the message
                - sender_id: The applicant ID sending the message
                - content: The message content
                - chat_id: WhatsApp chat identifier
                - locale: Language locale (optional)
            key (str): Kafka message key for routing

        Raises:
            Exception: If user/applicant retrieval or message processing fails
        """
        logger.info(f"[TextService.parse_event] Processing event with key: {key}")
        logger.debug(f"[TextService.parse_event] Event keys: {list(event.keys())}")

        try:
            # Extract IDs from event
            recruiter_id = str(event.get("receiver_id"))
            applicant_id = int(event.get("sender_id", 0))

            logger.info(
                f"[TextService.parse_event] Processing message from applicant {applicant_id} to recruiter {recruiter_id}"
            )

            # Get user details
            logger.debug("[TextService.parse_event] Retrieving user details")
            user_details = get_user_details(x_user_id=recruiter_id, db=get_db())

            # Get applicant details
            logger.debug("[TextService.parse_event] Retrieving applicant details")
            applicant_repo = ApplicantsRepository(get_db())
            applicant_service = ApplicantService(applicant_repo)
            applicant = applicant_service.get_applicant_by_recruiter_and_applicant(
                user_details, applicant_id=applicant_id
            )
            applicant_repo.close()

            user_event = Event(
                chat_id=event["chat_id"],
                content=event["content"],
                msg_type=event["msg_type"],
                receiver_id=event["receiver_id"],
                sender_id=event["sender_id"],
                timestamp=event.get(
                    "timestamp", datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                ),
                mid=event.get("mid", shortuuid.uuid()),
            )
            conversation_repo = ConversationRepository(get_db())
            conversation_service = ConversationService(conversation_repo)
            conversation_service.update_conversation(
                user_details, applicant_id, user_event, role=Role.APPLICANT
            )
            conversation_repo.close()
            logger.info(
                f"[TextService.parse_event] Applicant status: {applicant.status}"
            )

            # Process message through intent parsing for active applicants
            intent: IntentEnum = self.extract_intent(applicant, event["content"])
            self.parse_intent(intent, user_details, applicant, event, key)

            logger.info(
                f"[TextService.parse_event] Successfully processed event for applicant {applicant_id}"
            )

        except Exception as e:
            logger.error(
                f"[TextService.parse_event] Failed to process event with key {key}: {e}",
                exc_info=True,
            )
            raise


# Global service instance for text processing
# This instance is initialized with the default database session
logger.info("[TextService] Creating global text service instance")
text_service = TextService()
