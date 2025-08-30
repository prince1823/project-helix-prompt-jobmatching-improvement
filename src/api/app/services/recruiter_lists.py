from uuid import uuid4
from datetime import datetime

from fastapi import HTTPException, status as http_status

from app.db.postgres import get_db

from app.core.logger import logger

from app.repositories.recruiter_lists import Repository
from app.repositories.applicants import Repository as ApplicantsRepository

from app.models.user_login import UserDetails
from app.models.applicants import Request as ApplicantRequest
from app.models.recruiter_lists import Model, Request, Response, Status, NameRequest

from app.services.applicants import Service as ApplicantsService


class Service:
    def __init__(self, repo: Repository):
        self.repo = repo

    def create(self, user_details: UserDetails, body: Request) -> Response:
        table = self.repo.get_by_name(id=user_details.id, name=body.request.list_name)
        if table:
            logger.error(
                f"List with name {body.request.list_name} already exists for recruiter {user_details.id}"
            )
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="List name already exists",
            )
        applicants_repo = ApplicantsRepository(get_db())
        applicant_service = ApplicantsService(applicants_repo)
        applicants = set(body.request.applicants or [])
        for applicant_id in body.request.applicants or []:
            try:
                exists = applicant_service.get_by_recruiter_and_applicant(
                    user_details=user_details, applicant_id=applicant_id
                )
            except HTTPException as e:
                if e.status_code == http_status.HTTP_404_NOT_FOUND:
                    logger.warning(
                        f"Applicant {applicant_id} not found for recruiter {user_details.id}"
                    )
                    exists = None
                else:
                    raise
            if exists:
                logger.info(
                    f"Applicant {applicant_id} found for recruiter {user_details.id}"
                )
                applicant_service.update_tags(
                    user_details=user_details,
                    applicant_id=applicant_id,
                    tags=[body.request.list_name],
                )
            else:
                applicant = ApplicantRequest(
                    applicant_id=applicant_id, tags=[body.request.list_name]
                )
                try:
                    applicant_service.create(user_details=user_details, body=applicant)
                except HTTPException as e:
                    if e.status_code == http_status.HTTP_422_UNPROCESSABLE_ENTITY:
                        logger.warning(
                            f"Applicant {applicant_id} could not be created for recruiter {user_details.id}"
                        )
                        applicants.remove(applicant_id)
                    else:
                        raise
                logger.info(
                    f"Applicant {applicant_id} created for recruiter {user_details.id}"
                )
        applicants_repo.close()
        model = Model(
            recruiter_id=user_details.id,
            list_name=body.request.list_name,
            list_description=body.request.list_description,
            applicants=list(applicants),
            updated_by=str(user_details.id),
        )  # type: ignore
        table = self.repo.create(model)
        model = Model.model_validate(table)
        return Response(
            data=[model],
            mid=body.mid,
            ts=datetime.now(),
        )

    def get_all(self, user_details: UserDetails) -> Response:
        if user_details.role == "ADMIN":
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

    def get(self, user_details: UserDetails, list_id: int) -> Response:
        table = self.repo.get(list_id)
        if not table:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail="No list found"
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

    def get_by_name(self, user_details: UserDetails, body: NameRequest) -> Response:
        table = self.repo.get_by_name(user_details.id, body.request.list_name)
        if not table:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail="No list found"
            )
        model = Model.model_validate(table)
        if model.recruiter_id != user_details.id:
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED, detail="Not authorized"
            )
        return Response(
            data=[model],
            mid=body.mid,
            ts=datetime.now(),
        )

    def get_by_status(self, user_details: UserDetails, status: Status) -> Response:
        if user_details.role == "ADMIN":
            tables = self.repo.get_by_status(user_details.id, status, admin=True)
        else:
            tables = self.repo.get_by_status(user_details.id, status)
        if not tables:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail="No lists found"
            )
        return Response(
            data=[Model.model_validate(table) for table in tables],
            mid=uuid4(),
            ts=datetime.now(),
        )
