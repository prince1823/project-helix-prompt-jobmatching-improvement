from typing import List

from pydantic import ValidationError
from fastapi import HTTPException, status as http_status

from app.core.logger import logger

from app.db.postgres import get_db

from app.models.user_login import UserDetails
from app.models.job_mandate_questions import Model, QuestionType

from app.repositories.job_mandate_questions import Repository


class Service:
    def __init__(self, repo: Repository):
        self.repo = repo

    def create(self, model: Model) -> Model:
        try:
            table = self.repo.get_by_id(
                job_id=model.job_mandate_id,
                applicant_id=model.applicant_id,
                recruiter_id=model.recruiter_id,
                question_id=model.question_id,
            )
            if table:
                logger.debug("Record already exists")
                raise HTTPException(
                    status_code=http_status.HTTP_409_CONFLICT,
                    detail="Record already exists",
                )
            table = self.repo.create(model)
            if table:
                model = Model.model_validate(table)
                logger.debug(f"Created record: {model}")
                return model
            else:
                raise HTTPException(
                    status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create record",
                )
        except ValidationError as e:
            logger.error(f"Error creating record: {e}")
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Invalid data provided",
            )

    def get(self, id: int) -> Model:
        try:
            table = self.repo.get(id)
            if not table:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="Record not found",
                )
            Model.model_validate(table)
            return Model.model_validate(table)
        except ValidationError as e:
            logger.error(f"Error fetching record: {e}")
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Invalid data provided",
            )

    def get_all(self) -> list[Model]:
        try:
            tables = self.repo.get_all()
            if not tables:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="No records found",
                )
            return [Model.model_validate(table) for table in tables]
        except ValidationError as e:
            logger.error(f"Error fetching records: {e}")
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Invalid data provided",
            )

    def get_by_id(
        self,
        user_details: UserDetails,
        applicant_id: int,
        job_id: int,
        question_id: str,
    ) -> Model:
        try:
            table = self.repo.get_by_id(
                recruiter_id=user_details.id,
                applicant_id=applicant_id,
                job_id=job_id,
                question_id=question_id,
            )
            if not table:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="Record not found",
                )
            return Model.model_validate(table)
        except ValidationError as e:
            logger.error(f"Error fetching record: {e}")
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Invalid data provided",
            )

    def get_by_question_type(
        self, job_mandate_id: int, applicant_id: int, question_type: QuestionType
    ) -> List[Model]:
        try:
            tables = self.repo.get_by_question_type(
                job_mandate_id, applicant_id, question_type
            )
            if not tables:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="No records found",
                )
            return [Model.model_validate(table) for table in tables]
        except ValidationError as e:
            logger.error(f"Error fetching records: {e}")
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Invalid data provided",
            )

    def update_status(
        self,
        user_detail: UserDetails,
        job_mandate_id: int,
        applicant_id: int,
        question_id: str,
        status: bool,
        applicant_response: str,
    ) -> Model:
        try:
            table = self.repo.get_by_id(
                recruiter_id=user_detail.id,
                applicant_id=applicant_id,
                job_id=job_mandate_id,
                question_id=question_id,
            )
            if not table:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="Record not found",
                )
            updates = self.repo.update_status(
                job_mandate_id, applicant_id, question_id, status, applicant_response
            )
            if updates != 1:
                raise HTTPException(
                    status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update status",
                )
            table = self.repo.get_by_id(
                recruiter_id=user_detail.id,
                applicant_id=applicant_id,
                job_id=job_mandate_id,
                question_id=question_id,
            )
            return Model.model_validate(table)
        except Exception as e:
            logger.error(f"Error updating status: {e}")
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update status",
            )

    def delete(self, applicant_id: int, recruiter_id: int) -> None:
        repo = Repository(get_db())
        logger.info(f"[delete] Deleting applicant {applicant_id}")
        repo.delete(recruiter_id=recruiter_id, applicant_id=applicant_id)
        repo.close()
