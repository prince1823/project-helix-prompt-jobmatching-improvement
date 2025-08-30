import os
import json
from datetime import datetime
from typing import Dict, Any, List

import shortuuid
from openai import AzureOpenAI
from fastapi import HTTPException

from app.db.postgres import get_db

from app.core import constants
from app.core.config import config
from app.core.logger import logger
from app.core.authorization import get_user_details

from app.models.llm import MatchingJobs, AcceptanceModel
from app.models.user_login import UserDetails
from app.models.utils import Event, UpdatedBy
from app.models.applicants import Status as ApplicantStatus
from app.models.job_mandates import Model as JobMandates, LatestJob
from app.models.job_mandate_applicants import Status as JobMandateApplicantsStatus
from app.models.job_mandate_questions import (
    QualifyingCriteria,
    QuestionType,
    Model as JobMandateQuestions,
)

from app.repositories.config import Repository as ConfigsRepositiry
from app.repositories.applicants import Repository as ApplicantsRepository
from app.repositories.job_mandates import Repository as JobMandatesRepository
from app.repositories.job_mandate_applicants import (
    Repository as JobMandateApplicantsRepository,
)
from app.repositories.job_mandate_questions import (
    Repository as JobMandateQuestionsRepository,
)

from app.services.util_service import send_message
from app.services.configs import Service as ConfigsService
from app.services.applicants import Service as ApplicantsService
from app.services.job_mandates import Service as JobMandatesService
from app.services.job_mandate_questions import Service as JobMandateQuestionsService
from app.services.job_mandate_applicants import Service as JobMandateApplicantsService


class JobService:
    """
    Service class for handling text-based interactions with applicants.

    This service provides functionality for:
    - Text translation using Azure OpenAI
    - Extracting and processing applicant details
    - Intent classification and handling
    - Managing conversation flow and responses
    - Handling interruptions and follow-ups

    """

    def parse_job(self, event: Dict[str, Any], key: str) -> None:
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
        logger.info(f"[parse_job_flow.parse_event] Processing event with key: {key}")
        logger.debug(f"[parse_job_flow.parse_event] Event keys: {list(event.keys())}")

        try:
            recruiter_id = str(event.get("receiver_id"))
            applicant_id = int(event.get("sender_id", 0))
            user_details = get_user_details(x_user_id=recruiter_id, db=get_db())
            job_mandate_questions_repo = JobMandateQuestionsRepository(get_db())
            job_mandate_questions_service = JobMandateQuestionsService(
                job_mandate_questions_repo
            )
            # Extract IDs from event
            logger.info(
                f"[parse_job_flow.parse_event] Processing message from applicant {applicant_id} to recruiter {recruiter_id}"
            )
            latest_job = self.get_latest_job(applicant_id)
            if (
                latest_job.job_mandate_applicant_status
                == JobMandateApplicantsStatus.CRITERIA_SUCCESS
            ):
                try:
                    subjective_questions_answered = (
                        job_mandate_questions_service.get_by_question_type(
                            applicant_id=applicant_id,
                            job_mandate_id=latest_job.job_mandate.job_id,
                            question_type=QuestionType.SUBJECTIVE,
                        )
                    )
                except HTTPException as e:
                    subjective_questions_answered = []
                if len(latest_job.job_mandate.subjective_questions) > len(  # type: ignore
                    subjective_questions_answered
                ):
                    self.process_subjective_response(
                        event=event,
                        user_details=user_details,
                        job_mandate=latest_job.job_mandate,
                        subjective_questions_answered=subjective_questions_answered,
                    )
            elif (
                latest_job.job_mandate_applicant_status
                == JobMandateApplicantsStatus.USER_ACCEPTED
            ):
                try:
                    qualifying_questions_answered = (
                        job_mandate_questions_service.get_by_question_type(
                            applicant_id=applicant_id,
                            job_mandate_id=latest_job.job_mandate.job_id,
                            question_type=QuestionType.OBJECTIVE,
                        )
                    )
                except HTTPException as e:
                    qualifying_questions_answered = []
                self.process_qualifying_response(
                    event=event,
                    user_details=user_details,
                    job_mandate=latest_job.job_mandate,
                    qualifying_questions_answered=qualifying_questions_answered,
                )
            elif (
                latest_job.job_mandate_applicant_status
                == JobMandateApplicantsStatus.OFFERED
            ):
                self.process_offered_job(
                    event=event,
                    user_details=user_details,
                    applicant_id=applicant_id,
                    job_mandate=latest_job.job_mandate,
                )
            elif (
                latest_job.job_mandate_applicant_status
                == JobMandateApplicantsStatus.MATCHED
            ):
                self.offer_new_job(user_details=user_details, applicant_id=applicant_id)
            else:
                try:
                    self.get_matching_jobs(
                        user_details=user_details, applicant_id=applicant_id
                    )
                    self.offer_new_job(user_details=user_details, applicant_id=applicant_id)
                except Exception as e:
                    response_event = Event(
                        chat_id=f"{applicant_id}@s.whatsapp.net",
                        content=constants.NO_JOB_OFFERS_MESSAGE,
                        msg_type="text",
                        receiver_id=applicant_id,
                        sender_id=user_details.id,
                        timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        mid=shortuuid.uuid(),
                    )
                    send_message(
                        user_details=user_details,
                        applicant_id=applicant_id,
                        event=response_event,
                        key=f"{user_details.id}_{applicant_id}",
                    )
            job_mandate_questions_repo.close()
        except Exception as e:
            logger.error(
                f"[parse_job_flow.parse_event] Failed to process event with key {key}: {e}",
                exc_info=True,
            )
            raise

    def get_matching_jobs(
        self, user_details: UserDetails, applicant_id: int
    ) -> MatchingJobs:
        response_event = Event(
            mid=shortuuid.uuid(),
            timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            chat_id=f"{applicant_id}@s.whatsapp.net",
            sender_id=user_details.id,
            receiver_id=applicant_id,
            msg_type="text",
            content=constants.JOB_MATCHING_MESSAGE,
        )
        send_message(
            user_details=user_details,
            applicant_id=applicant_id,
            event=response_event,
            key=f"{user_details.id}_{applicant_id}",
        )
        applicants_repo = ApplicantsRepository(get_db())
        applicants_service = ApplicantsService(applicants_repo)
        job_mandates_repo = JobMandatesRepository(get_db())
        job_mandates_service = JobMandatesService(job_mandates_repo)
        job_mandate_applicants_repo = JobMandateApplicantsRepository(get_db())
        job_mandate_applicants_service = JobMandateApplicantsService(
            job_mandate_applicants_repo
        )

        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        )

        # Prepare the LLM schema for structured output
        logger.debug("[TextService.get_matching_jobs] Setting up LLM schema")
        llm_schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "MatchingJobsSchema",
                "schema": MatchingJobs.model_json_schema(),
            },
        }

        # Get system prompt and conversation history
        system_prompt = config["llm"]["mandate_matching"]["prompt"]
        logger.debug("[TextService.get_basic_details] Fetching conversation history")
        # Get applicant details
        logger.debug("[TextService.get_matching_jobs] Retrieving applicant details")
        applicant = applicants_service.get_applicant_by_recruiter_and_applicant(
            user_details, applicant_id=applicant_id
        )

        job_mandates = job_mandates_service.get_active_jobs()

        completion = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "applicant_details": applicant.details.model_dump(
                                exclude_none=True
                            )
                            if applicant.details
                            else None,
                            "job_descriptions": [
                                job_mandate.model_dump(exclude_none=True)
                                for job_mandate in job_mandates
                            ],
                        }
                    ),
                },
            ],
            temperature=0,
            response_format=llm_schema,  # type: ignore
        )
        content = completion.choices[0].message.content or ""
        logger.debug("[TextService.get_matching_jobs] Processing AI response")
        matching_jobs = MatchingJobs.model_validate(json.loads(content))
        if matching_jobs.job_ids:
            job_mandates = job_mandate_applicants_service.create_many(
                user_details, applicant_id, matching_jobs.job_ids
            )
            applicants_service.update_status(
                user_details=user_details,
                applicant_id=applicant_id,
                status=ApplicantStatus.MANDATE_MATCHING,
            )
        applicants_repo.close()
        job_mandates_repo.close()
        job_mandate_applicants_repo.close()
        return matching_jobs

    def offer_new_job(self, applicant_id: int, user_details: UserDetails):
        applicants_repo = ApplicantsRepository(get_db())
        applicants_service = ApplicantsService(applicants_repo)
        job_mandates_repo = JobMandatesRepository(get_db())
        job_mandates_service = JobMandatesService(job_mandates_repo)
        job_mandate_applicants_repo = JobMandateApplicantsRepository(get_db())
        job_mandate_applicants_service = JobMandateApplicantsService(
            job_mandate_applicants_repo
        )
        try:
            matched = job_mandate_applicants_service.get_by_applicant_id_and_status(
                applicant_id, JobMandateApplicantsStatus.MATCHED
            )
        except HTTPException as e:
            matched = None
        if matched:
            logger.info(
                f"[parse_job_flow.parse_event] Job found for applicant {applicant_id}: {matched}"
            )
            job_information = job_mandates_service.get_job_information_by_id(
                job_id=matched.job_mandate_id
            )
            logger.info(
                f"[parse_job_flow.parse_event] Job information: {job_information}"
            )
            response_structure = constants.JOB_OFFER_MESSAGE.format(
                job_information.description
            )
            logger.info(
                f"[parse_job_flow.parse_event] Job information found: {job_information}"
            )
            job_mandate_applicants_service.update_status(
                user_details=user_details,
                applicant_id=applicant_id,
                job_mandate_id=matched.job_mandate_id,
                status=JobMandateApplicantsStatus.OFFERED,
            )
            send_event = Event(
                chat_id=f"{applicant_id}@s.whatsapp.net",
                content=response_structure,
                msg_type="text",
                receiver_id=applicant_id,
                sender_id=user_details.id,
                timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                mid=shortuuid.uuid(),
            )
            send_message(
                user_details=user_details,
                applicant_id=applicant_id,
                event=send_event,
                key=f"{user_details.id}_{applicant_id}",
            )
        else:
            logger.warning(
                f"[JobService.offer_new_job] No job information found for applicant {applicant_id}"
            )
            # Handle case where no job information is found
            applicants_service.update_status(
                user_details=user_details,
                applicant_id=applicant_id,
                status=ApplicantStatus.NO_MATCHES,
            )
            send_event = Event(
                chat_id=f"{applicant_id}@s.whatsapp.net",
                content=constants.NO_JOB_OFFERS_MESSAGE,
                msg_type="text",
                receiver_id=applicant_id,
                sender_id=user_details.id,
                timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                mid=shortuuid.uuid(),
            )
            send_message(
                user_details=user_details,
                applicant_id=applicant_id,
                event=send_event,
                key=f"{user_details.id}_{applicant_id}",
            )
        applicants_repo.close()
        job_mandates_repo.close()
        job_mandate_applicants_repo.close()

    def parse_acceptance(self, content: str) -> bool:
        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        )

        # Prepare the LLM schema for structured output
        logger.debug("[TextService.get_matching_jobs] Setting up LLM schema")
        llm_schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "MatchingJobsSchema",
                "schema": AcceptanceModel.model_json_schema(),
            },
        }

        # Get system prompt and conversation history
        system_prompt = config["llm"]["user_response_acceptance"]["prompt"]

        completion = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "applicant_response": content,
                        }
                    ),
                },
            ],
            temperature=0,
            response_format=llm_schema,  # type: ignore
        )
        content = completion.choices[0].message.content or ""
        logger.debug("[TextService.get_matching_jobs] Processing AI response")
        acceptance = AcceptanceModel.model_validate(json.loads(content))
        return acceptance.response_text

    def process_offered_job(
        self,
        event: dict,
        user_details: UserDetails,
        applicant_id: int,
        job_mandate: JobMandates,
    ) -> None:
        job_mandate_applicants_repo = JobMandateApplicantsRepository(get_db())
        job_mandate_applicants_service = JobMandateApplicantsService(
            job_mandate_applicants_repo
        )
        success: bool = self.parse_acceptance(event["content"])
        if success:
            job_mandate_applicants_service.update_status(
                user_details=user_details,
                applicant_id=applicant_id,
                job_mandate_id=job_mandate.job_id,
                status=JobMandateApplicantsStatus.USER_ACCEPTED,
            )
            response_event = Event(
                mid=event["mid"],
                timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                chat_id=event["chat_id"],
                receiver_id=event["sender_id"],
                sender_id=event["receiver_id"],
                msg_type="text",
                content=constants.ASK_QUALIFYING_CRITERIA_MESSAGE.format(
                    job_mandate.job_information.title
                ),
            )
            send_message(
                user_details=user_details,
                applicant_id=applicant_id,
                event=response_event,
                key=f"{user_details.id}_{applicant_id}",
            )
            response_event = Event(
                mid=event["mid"],
                timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                chat_id=event["chat_id"],
                receiver_id=event["sender_id"],
                sender_id=event["receiver_id"],
                msg_type="text",
                content=job_mandate.qualifying_criteria[0].question,
            )
            send_message(
                user_details=user_details,
                applicant_id=applicant_id,
                event=response_event,
                key=f"{user_details.id}_{applicant_id}",
            )
        else:
            job_mandate_applicants_service.update_status(
                user_details=user_details,
                applicant_id=applicant_id,
                job_mandate_id=job_mandate.job_id,
                status=JobMandateApplicantsStatus.USER_REJECTED,
            )
            self.offer_new_job(applicant_id=applicant_id, user_details=user_details)
        job_mandate_applicants_repo.close()

    def parse_qualifying_response(
        self, content: str, question: QualifyingCriteria
    ) -> bool:
        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        )

        # Prepare the LLM schema for structured output
        logger.debug("[TextService.get_matching_jobs] Setting up LLM schema")
        llm_schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "MatchingJobsSchema",
                "schema": AcceptanceModel.model_json_schema(),
            },
        }

        # Get system prompt and conversation history
        system_prompt = config["llm"]["evaluate_qualifying_criteria"]["prompt"]

        completion = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question.question,
                            "answer_key": [
                                item.model_dump() for item in question.answers
                            ],
                            "applicant_response": content,
                        }
                    ),
                },
            ],
            temperature=0,
            response_format=llm_schema,  # type: ignore
        )
        content = completion.choices[0].message.content or ""
        logger.debug("[TextService.get_matching_jobs] Processing AI response")
        acceptance = AcceptanceModel.model_validate(json.loads(content))
        return acceptance.response_text

    def send_interview_details(
        self,
        event: dict,
        user_details: UserDetails,
        applicant_id: int,
        job_mandate: JobMandates,
    ):
        applicants_repo = ApplicantsRepository(get_db())
        applicants_service = ApplicantsService(applicants_repo)
        configs_repo = ConfigsRepositiry(get_db())
        configs_service = ConfigsService(configs_repo)
        job_mandate_applicants_repo = JobMandateApplicantsRepository(get_db())
        job_mandate_applicants_service = JobMandateApplicantsService(
            job_mandate_applicants_repo
        )

        content = f"Congratulations! You have been shortlisted for the job position. Find the interview details below. We will call you soon."
        response_event = Event(
            mid=event["mid"],
            timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            chat_id=event["chat_id"],
            receiver_id=event["sender_id"],
            sender_id=event["receiver_id"],
            msg_type="text",
            content=content,
        )
        send_message(
            user_details=user_details,
            applicant_id=applicant_id,
            event=response_event,
            key=f"{user_details.id}_{applicant_id}",
        )
        interview_details = job_mandate.job_information.interview_process
        documents = "\n".join(interview_details.documents)
        response_event.content = f"Number of interviews: {interview_details.rounds}\nDocuments Required: {documents}\nJob starting: {interview_details.start_date}"
        send_message(
            user_details=user_details,
            applicant_id=applicant_id,
            event=response_event,
            key=f"{user_details.id}_{applicant_id}",
        )
        job_mandate_applicants_service.update_status(
            user_details=user_details,
            applicant_id=applicant_id,
            job_mandate_id=job_mandate.job_id,
            status=JobMandateApplicantsStatus.SHORTLISTED,
        )
        configs_service.update_enabled(
            user_details=user_details,
            applicant_ids=[applicant_id],
            enabled=False,
            updated_by=UpdatedBy.SYSTEM,
        )
        applicants_service.update_status(
            user_details=user_details,
            applicant_id=applicant_id,
            status=ApplicantStatus.SHORTLISTED,
        )
        configs_repo.close()
        applicants_repo.close()
        job_mandate_applicants_repo.close()

    def process_qualifying_response(
        self,
        event: dict,
        user_details: UserDetails,
        job_mandate: JobMandates,
        qualifying_questions_answered: List[JobMandateQuestions],
    ):
        job_mandate_applicants_repo = JobMandateApplicantsRepository(get_db())
        job_mandate_applicants_service = JobMandateApplicantsService(
            job_mandate_applicants_repo
        )
        job_mandate_questions_repo = JobMandateQuestionsRepository(get_db())
        job_mandate_questions_service = JobMandateQuestionsService(
            job_mandate_questions_repo
        )
        recruiter_id = str(event.get("receiver_id"))
        applicant_id = int(event.get("sender_id", 0))
        applicant_response = event["content"]
        current_question_order_id = len(qualifying_questions_answered)
        current_question = job_mandate.qualifying_criteria[current_question_order_id]
        pass_ = self.parse_qualifying_response(applicant_response, current_question)
        job_mandate_question_model = JobMandateQuestions(
            job_mandate_id=job_mandate.job_id,
            recruiter_id=recruiter_id,
            applicant_id=applicant_id,
            question_id=current_question.id,
            question_type=QuestionType.OBJECTIVE,
            question_details=current_question,
            applicant_response=applicant_response,
            status=pass_,
        )  # type: ignore
        job_mandate_questions_service.create(model=job_mandate_question_model)
        if not pass_:
            response_event = Event(
                mid=shortuuid.uuid(),
                timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                chat_id=f"{applicant_id}@s.whatsapp.net",
                sender_id=user_details.id,
                receiver_id=applicant_id,
                msg_type="text",
                content=constants.QUALIFYING_CRITERIA_FAILED,
            )
            send_message(
                user_details=user_details,
                applicant_id=applicant_id,
                event=response_event,
                key=f"{user_details.id}_{applicant_id}",
            )
            job_mandate_applicants_service.update_status(
                user_details=user_details,
                applicant_id=applicant_id,
                job_mandate_id=job_mandate.job_id,
                status=JobMandateApplicantsStatus.CRITERIA_FAILED,
            )
            self.offer_new_job(applicant_id=applicant_id, user_details=user_details)
            return
        if current_question_order_id + 1 < len(job_mandate.qualifying_criteria):
            # check conditions
            response_event = Event(
                mid=event["mid"],
                timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                chat_id=event["chat_id"],
                receiver_id=event["sender_id"],
                sender_id=event["receiver_id"],
                msg_type="text",
                content=job_mandate.qualifying_criteria[
                    current_question_order_id + 1
                ].question,
            )
            send_message(
                user_details=user_details,
                applicant_id=applicant_id,
                event=response_event,
                key=f"{recruiter_id}_{applicant_id}",
            )
        else:
            if job_mandate.subjective_questions:
                job_mandate_applicants_service.update_status(
                    user_details=user_details,
                    applicant_id=applicant_id,
                    job_mandate_id=job_mandate.job_id,
                    status=JobMandateApplicantsStatus.CRITERIA_SUCCESS,
                )
                content = job_mandate.subjective_questions[0].question
                response_event = Event(
                    mid=event["mid"],
                    timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    chat_id=event["chat_id"],
                    receiver_id=event["sender_id"],
                    sender_id=event["receiver_id"],
                    msg_type="text",
                    content=content,
                )
                send_message(
                    user_details=user_details,
                    applicant_id=applicant_id,
                    event=response_event,
                    key=f"{recruiter_id}_{applicant_id}",
                )
            else:
                self.send_interview_details(
                    event=event,
                    user_details=user_details,
                    applicant_id=applicant_id,
                    job_mandate=job_mandate,
                )
        job_mandate_applicants_repo.close()
        job_mandate_questions_repo.close()

    def process_subjective_response(
        self,
        event: dict,
        user_details: UserDetails,
        job_mandate: JobMandates,
        subjective_questions_answered: List[JobMandateQuestions],
    ):
        job_mandate_questions_repo = JobMandateQuestionsRepository(get_db())
        job_mandate_questions_service = JobMandateQuestionsService(
            job_mandate_questions_repo
        )
        recruiter_id = str(event.get("receiver_id"))
        applicant_id = int(event.get("sender_id", 0))
        applicant_response = event["content"]
        current_question_order_id = len(subjective_questions_answered)
        current_question = job_mandate.subjective_questions[current_question_order_id]  # type: ignore
        job_mandate_question_model = JobMandateQuestions(
            job_mandate_id=job_mandate.job_id,
            recruiter_id=recruiter_id,
            applicant_id=applicant_id,
            question_id=current_question.id,
            question_type=QuestionType.SUBJECTIVE,
            question_details=current_question,
            applicant_response=applicant_response,
        )  # type: ignore
        job_mandate_questions_service.create(model=job_mandate_question_model)
        if current_question_order_id + 1 < len(job_mandate.subjective_questions):  # type: ignore
            response_event = Event(
                mid=event["mid"],
                timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                chat_id=event["chat_id"],
                receiver_id=event["sender_id"],
                sender_id=event["receiver_id"],
                msg_type="text",
                content=job_mandate.subjective_questions[  # type: ignore
                    current_question_order_id + 1
                ].question,
            )
            send_message(
                user_details=user_details,
                applicant_id=applicant_id,
                event=response_event,
                key=f"{recruiter_id}_{applicant_id}",
            )
        else:
            self.send_interview_details(
                event=event,
                user_details=user_details,
                applicant_id=applicant_id,
                job_mandate=job_mandate,
            )
        job_mandate_questions_repo.close()

    def get_latest_job(self, applicant_id: int) -> LatestJob:
        job_mandates_repo = JobMandatesRepository(get_db())
        job_mandates_service = JobMandatesService(job_mandates_repo)
        job_mandate_applicants_repo = JobMandateApplicantsRepository(get_db())
        job_mandate_applicants_service = JobMandateApplicantsService(
            job_mandate_applicants_repo
        )
        try:
            criteria_success = (
                job_mandate_applicants_service.get_by_applicant_id_and_status(
                    applicant_id=applicant_id,
                    status=JobMandateApplicantsStatus.CRITERIA_SUCCESS,
                )
            )
        except HTTPException as e:
            logger.error(
                f"[parse_job_flow.parse_event] Error fetching criteria success: {e}"
            )
            criteria_success = None
        if criteria_success:
            job_mandate = job_mandates_service.get_by_id(
                criteria_success.job_mandate_id
            )
            return LatestJob(
                job_mandate=job_mandate,
                job_mandate_applicant_status=JobMandateApplicantsStatus.CRITERIA_SUCCESS,
            )
        try:
            user_accepted = (
                job_mandate_applicants_service.get_by_applicant_id_and_status(
                    applicant_id=applicant_id,
                    status=JobMandateApplicantsStatus.USER_ACCEPTED,
                )
            )
        except HTTPException as e:
            logger.error(
                f"[parse_job_flow.parse_event] Error fetching criteria success: {e}"
            )
            user_accepted = None
        if user_accepted:
            job_mandate = job_mandates_service.get_by_id(user_accepted.job_mandate_id)
            return LatestJob(
                job_mandate=job_mandate,
                job_mandate_applicant_status=JobMandateApplicantsStatus.USER_ACCEPTED,
            )
        try:
            offered = job_mandate_applicants_service.get_by_applicant_id_and_status(
                applicant_id=applicant_id, status=JobMandateApplicantsStatus.OFFERED
            )
        except HTTPException as e:
            logger.error(
                f"[parse_job_flow.parse_event] Error fetching criteria success: {e}"
            )
            offered = None
        if offered:
            job_mandate = job_mandates_service.get_by_id(offered.job_mandate_id)
            return LatestJob(
                job_mandate=job_mandate,
                job_mandate_applicant_status=JobMandateApplicantsStatus.OFFERED,
            )
        try:
            matched = job_mandate_applicants_service.get_by_applicant_id_and_status(
                applicant_id=applicant_id, status=JobMandateApplicantsStatus.MATCHED
            )
        except HTTPException as e:
            logger.error(
                f"[parse_job_flow.parse_event] Error fetching criteria success: {e}"
            )
            matched = None
        if matched:
            job_mandate = job_mandates_service.get_by_id(matched.job_mandate_id)
            return LatestJob(
                job_mandate=job_mandate,
                job_mandate_applicant_status=JobMandateApplicantsStatus.MATCHED,
            )
        logger.warning(
            f"[parse_job_flow.parse_event] No job mandate found for applicant {applicant_id}"
        )
        return LatestJob(
            job_mandate=job_mandates_service.get_by_id(1),
            job_mandate_applicant_status=None,
        )


logger.info("[parse_job_flow] Creating global text service instance")
job_service = JobService()
