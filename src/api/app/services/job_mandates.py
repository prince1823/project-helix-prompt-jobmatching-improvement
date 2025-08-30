from typing import List

from pydantic_core import ValidationError
from fastapi import HTTPException, status as http_status

from app.core.logger import logger

from app.models.job_mandate_questions import QualifyingCriteria
from app.models.job_mandates import (
    JobInformation,
    MatchingFilters,
    Model,
    Status,
    SubjectiveQuestions,
)

from app.repositories.job_mandates import Repository


class Service:
    def __init__(self, repo: Repository):
        self.repo = repo

    def get_by_id(self, job_id: int) -> Model:
        """
        Fetch the detail information  for a specific job.
        """
        try:
            table = self.repo.get_by_job_id(job_id)
            if not table:
                logger.debug(
                    f"[JobMandateService.get_job_information_by_id] Job not found for id: {job_id}"
                )
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="Job not found",
                )
            model = Model.model_validate(table)
            logger.debug(f"[JobMandateService.get_by_id] Job Mandate: {model}")
            return model
        except ValidationError as e:
            logger.error(
                f"[JobMandateService.get_by_id] Validation error: {e.errors()}"
            )
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {e.errors()}",
            )

    def get_job_information_by_id(self, job_id: int) -> JobInformation:
        """
        Fetch the detail information  for a specific job.
        """
        try:
            table = self.repo.get_by_job_id(job_id)
            if not table:
                logger.debug(
                    f"[JobMandateService.get_job_information_by_id] Job not found for id: {job_id}"
                )
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="Job not found",
                )
            model = Model.model_validate(table)
            logger.debug(
                f"[JobMandateService.get_job_information_by_id] Job information: {model.job_information}"
            )
            return model.job_information
        except ValidationError as e:
            logger.error(
                f"[JobMandateService.get_job_information_by_id] Validation error: {e.errors()}"
            )
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {e.errors()}",
            )

    def get_qualifying_criteria_by_id(self, job_id: int) -> List[QualifyingCriteria]:
        """
        Show jobs to the applicant based on their filtering criteria.
        This function fetches matching jobs for the given job_id.
        """
        try:
            table = self.repo.get_by_job_id(job_id)
            if not table:
                logger.debug(
                    f"[JobMandateService.get_qualifying_criteria_by_id] Job not found for id: {job_id}"
                )
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="Job not found",
                )
            model = Model.model_validate(table)
            logger.debug(
                f"[JobMandateService.get_qualifying_criteria_by_id] Qualifying criteria: {model.qualifying_criteria}"
            )
            return model.qualifying_criteria
        except ValidationError as e:
            logger.error(
                f"[JobMandateService.get_qualifying_criteria_by_id] Validation error: {e.errors()}"
            )
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {e.errors()}",
            )

    def get_subjective_criteria_by_id(self, job_id: int) -> List[SubjectiveQuestions]:
        """
        Show jobs to the applicant based on their filtering criteria.
        This function fetches matching jobs for the given job_id.
        """
        try:
            table = self.repo.get_by_job_id(job_id)
            if not table:
                logger.debug(
                    f"[JobMandateService.get_subjective_criteria_by_id] Job not found for id: {job_id}"
                )
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="Job not found",
                )
            model = Model.model_validate(table)
            logger.debug(
                f"[JobMandateService.get_subjective_criteria_by_id] Subjective criteria: {model.subjective_questions}"
            )
            return model.subjective_questions if model.subjective_questions else []
        except ValidationError as e:
            logger.error(
                f"[JobMandateService.get_subjective_criteria_by_id] Validation error: {e.errors()}"
            )
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {e.errors()}",
            )

    def get_active_jobs(self) -> List[MatchingFilters]:
        """
        Fetch all job mandates.
        """
        try:
            tables = self.repo.get_by_status(status=Status.ACTIVE)
            if not tables:
                logger.debug(
                    f"[JobMandateService.get_active_jobs] No job mandates found"
                )
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="No job mandates found",
                )
            models = [Model.model_validate(table) for table in tables]
            matching_filters = []
            for model in models:
                filtering_criteria = model.filtering_criteria
                matching_filters.append(
                    MatchingFilters(
                        job_id=model.job_id,
                        location=filtering_criteria.locations,
                        experience=filtering_criteria.experience,
                        type_of_experience=filtering_criteria.type_of_experience,
                        age=filtering_criteria.age,
                        gender=filtering_criteria.gender,
                        education_level=filtering_criteria.education_level,
                        salary_max=model.job_information.benefits.monthly_pay.max,
                    )
                )
            logger.debug(
                f"[JobMandateService.get_active_jobs] Found {len(matching_filters)} active jobs"
            )
            return matching_filters
        except ValidationError as e:
            logger.error(
                f"[JobMandateService.get_active_jobs] Validation error: {e.errors()}"
            )
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {e.errors()}",
            )
