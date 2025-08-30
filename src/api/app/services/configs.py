from uuid import uuid4
from typing import List
from datetime import datetime

from fastapi import HTTPException, status as http_status

from app.core.logger import logger
from app.db.postgres import get_db

from app.repositories.config import Repository

from app.models.utils import UpdatedBy
from app.models.user_login import UserDetails, Role
from app.models.configs import Model, Request, Response


class Service:
    def __init__(self, repo: Repository):
        self.repo = repo

    def create(self, user_details: UserDetails, body: Request) -> Response:
        model = Model(
            recruiter_id=user_details.id,
            applicant_id=body.applicant_id,
        )  # type: ignore
        table = self.repo.get_by_recruiter_and_applicant(
            model.recruiter_id, model.applicant_id
        )
        if table:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="List name already exists",
            )
        table = self.repo.create(model)
        return Response(
            data=[Model.model_validate(table)],
            mid=uuid4(),
            ts=datetime.now(),
        )

    def get_all(self, user_details: UserDetails) -> Response:
        if user_details.role == Role.ADMIN:
            tables = self.repo.get_all(user_details.id, admin=True)
        else:
            tables = self.repo.get_all(user_details.id)
        if not tables:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail="No lists found"
            )
        data = [Model.model_validate(table) for table in tables]
        return Response(
            data=data,
            mid=uuid4(),
            ts=datetime.now(),
        )

    def get(self, user_details: UserDetails, applicant_id: int) -> Response:
        table = self.repo.get(applicant_id)
        if not table:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail="No applicant found"
            )
        model = Model.model_validate(table)
        if model.recruiter_id != user_details.id:
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED, detail="Not authorized"
            )
        return Response(
            data=[model],
            mid=uuid4(),
            ts=datetime.now(),
        )

    def get_by_recruiter_and_applicant(
        self, user_details: UserDetails, applicant_id: int
    ) -> Response:
        table = self.repo.get_by_recruiter_and_applicant(user_details.id, applicant_id)
        if not table:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail="No applicant found"
            )
        model = Model.model_validate(table)
        if model.recruiter_id != user_details.id:
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED, detail="Not authorized"
            )
        return Response(
            data=[model],
            mid=uuid4(),
            ts=datetime.now(),
        )

    def update_enabled(
        self,
        user_details: UserDetails,
        applicant_ids: List[int],
        enabled: bool,
        updated_by: UpdatedBy,
    ) -> List[Model]:
        repo = Repository(get_db())
        updated = (
            str(user_details.id)
            if updated_by == UpdatedBy.USER
            else UpdatedBy.SYSTEM.value
        )
        updates = []
        for applicant_id in applicant_ids:
            table = repo.get_by_recruiter_and_applicant(user_details.id, applicant_id)
            if not table:
                model = Model(
                    recruiter_id=user_details.id,
                    applicant_id=applicant_id,
                    enabled=enabled,
                    updated_by=updated,
                )  # type: ignore
                table = repo.create(model)
            table = repo.update_enabled(
                recruiter_id=user_details.id,
                applicant_id=applicant_id,
                enabled=enabled,
                updated_by=updated,
            )
            updates.append(Model.model_validate(table))
        repo.close()
        return updates

    def delete(self, applicant_id: int, recruiter_id: int) -> None:
        repo = Repository(get_db())
        logger.info(f"[delete] Deleting applicant {applicant_id}")
        repo.delete(recruiter_id=recruiter_id, applicant_id=applicant_id)
        repo.close()
