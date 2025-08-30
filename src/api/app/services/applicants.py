import json
from uuid import uuid4
from datetime import datetime

from shortuuid import uuid
from pydantic_core import ValidationError
from fastapi import HTTPException, status as http_status

from app.core.logger import logger

from app.db.postgres import get_db

from app.repositories.applicants import Repository
from app.repositories.config import Repository as ConfigRepository

from app.models.llm import ApplicantDetails
from app.models.utils import Event, UpdatedBy
from app.models.configs import Model as Config
from app.models.user_login import UserDetails, Role
from app.models.applicants import Model, Request, Response, Status

from app.services.util_service import send_message


class Service:
    def __init__(self, repo: Repository):
        self.repo = repo
        self.config_repo = ConfigRepository(self.repo.db)

    def create(self, user_details: UserDetails, body: Request) -> Response:
        try:
            model = Model(
                recruiter_id=user_details.id,
                applicant_id=body.applicant_id,
                details=body.details,
                status=body.status,
                tags=body.tags,
            )  # type: ignore
        except ValidationError as e:
            logger.error(f"Validation error while creating applicant: {e}")
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=e.errors(),
            )
        table = self.repo.get_by_recruiter_and_applicant(
            model.recruiter_id, model.applicant_id
        )
        if table:
            logger.error(f"Applicant already exists: {table}")
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="Applicant already exists",
            )
        config = self.config_repo.get_by_recruiter_and_applicant(
            model.recruiter_id, model.applicant_id
        )
        if not config:
            logger.info(
                f"Creating config for recruiter {model.recruiter_id} and applicant {model.applicant_id}"
            )
            config = Config(
                recruiter_id=model.recruiter_id,
                applicant_id=model.applicant_id,
            )  # type: ignore
            self.config_repo.create(config)
        table = self.repo.create(model)
        logger.info(f"Created applicant: {table.__dict__}")
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

    # def get_by_recruiter_and_applicants(self, user_details: UserDetails, body: Request) -> Response:
    #     applicant_ids = body.applicant_ids
    #     tables = self.repo.get_by_recruiter_and_applicants(user_details.id, applicant_ids)
    #     if not tables:
    #         raise HTTPException(
    #             status_code=http_status.HTTP_404_NOT_FOUND, detail="No applicants found"
    #         )
    #     models = [Model.model_validate(table) for table in tables]
    #     return Response(
    #         data=models,
    #         mid=uuid4(),
    #         ts=datetime.now(),
    #     )

    def get_by_status(self, user_details: UserDetails, status: Status) -> Response:
        admin = False
        if user_details.role == Role.ADMIN:
            admin = True
        tables = self.repo.get_by_status(user_details.id, status, admin=admin)
        if not tables:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail="No applicants found"
            )
        models = [Model.model_validate(table) for table in tables]
        return Response(
            data=models,
            mid=uuid4(),
            ts=datetime.now(),
        )

    def get_applicant_by_recruiter_and_applicant(
        self, user_details: UserDetails, applicant_id: int
    ) -> Model:
        repo = Repository(get_db())
        config_repo = ConfigRepository(get_db())
        table = repo.get_applicant_by_recruiter_and_not_status(
            user_details.id, applicant_id, status=Status.RETIRED
        )
        # If recruiter and applicant pair do not exist, check if applicant exists for other recruiters
        if not table:
            table = repo.get_applicant_by_not_status(
                applicant_id, status=Status.RETIRED
            )
            # if applicant does not exist for other recruiters
            if not table:
                model = Model(
                    recruiter_id=user_details.id,
                    applicant_id=applicant_id,
                )  # type: ignore
                # check config first for FK
                config = config_repo.get_by_recruiter_and_applicant(
                    user_details.id, applicant_id
                )
                if not config:
                    config = Config(
                        recruiter_id=user_details.id,
                        applicant_id=applicant_id,
                    )  # type: ignore
                    config = config_repo.create(config)
                table = repo.create(model)
            # if applicant exists for other recruiters
            else:
                existing = Model.model_validate(table)
                # if applicant exists for other recruiters in completed state,
                # disable for new recruiter
                if existing.status == Status.DETAILS_COMPLETED:
                    config_repo.update_enabled(
                        recruiter_id=user_details.id,
                        applicant_id=applicant_id,
                        enabled=False,
                        updated_by=UpdatedBy.SYSTEM,
                    )
                    if existing.details:
                        content = existing.details.model_dump(exclude_none=True)
                    event = Event(
                        mid=uuid(),
                        timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        chat_id=f"{user_details.id}@s.whatsapp.net",
                        receiver_id=user_details.id,
                        sender_id=user_details.id,
                        msg_type="text",
                        content=json.dumps(content),
                    )
                    send_message(
                        user_details=user_details,
                        applicant_id=applicant_id,
                        event=event,
                        key=f"{existing.recruiter_id}_{existing.applicant_id}",
                    )
                else:
                    # if applicant exists for other recruiters in progress state,
                    # disable for old recruiter, copy existing details
                    updated_existing = repo.update_status(
                        recruiter_id=existing.recruiter_id,
                        applicant_id=existing.applicant_id,
                        status=Status.RETIRED,
                    )
                    config_repo.update_enabled(
                        recruiter_id=existing.recruiter_id,
                        applicant_id=applicant_id,
                        enabled=False,
                        updated_by=UpdatedBy.SYSTEM,
                    )
                    existing.id = None
                    existing.recruiter_id = user_details.id
                    table = repo.create(existing)
        repo.close()
        config_repo.close()
        # send message with completion data to new recruiter
        model = Model.model_validate(table)
        return model

    def update_details(
        self, user_details: UserDetails, applicant_id: int, details: dict
    ) -> Model:
        repo = Repository(get_db())
        table = repo.get_applicant_by_recruiter_and_not_status(
            user_details.id, applicant_id, status=Status.RETIRED
        )
        if not table:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail="Applicant not found"
            )
        model = Model.model_validate(table)
        existing_details = (
            model.details.model_dump(exclude_none=True) if model.details else {}
        )
        for item in details:
            existing_details[item] = details[item]
        model.details = ApplicantDetails.model_validate(existing_details)
        table = repo.update_details(
            recruiter_id=user_details.id,
            applicant_id=applicant_id,
            details=model.details,
        )
        repo.close()
        return Model.model_validate(table)

    def update_response(
        self, user_details: UserDetails, applicant_id: int, response: str
    ) -> Model:
        logger.info(
            f"[update_response] Updating response for applicant {applicant_id} by recruiter {user_details.id}"
        )
        repo = Repository(get_db())
        config_repo = ConfigRepository(get_db())
        table = repo.get_by_recruiter_and_applicant(
            recruiter_id=user_details.id, applicant_id=applicant_id
        )
        if not table:
            logger.error(f"Applicant not found: {applicant_id}")
            self.create(
                user_details=user_details, body=Request(applicant_id=applicant_id)
            )
        table = repo.update_response(
            recruiter_id=user_details.id, applicant_id=applicant_id, response=response
        )
        repo.close()
        config_repo.update_counter(
            recruiter_id=user_details.id, applicant_id=applicant_id
        )
        config_repo.close()
        logger.info(
            f"[update_response] Updated response and message count for applicant {applicant_id} by recruiter {user_details.id}"
        )
        repo.close()
        config_repo.close()
        return Model.model_validate(table)

    def update_status(
        self, user_details: UserDetails, applicant_id: int, status: Status
    ) -> Model:
        repo = Repository(get_db())
        logger.info(
            f"[update_status] Updating status for applicant {applicant_id} by recruiter {user_details.id}"
        )
        table = repo.update_status(
            recruiter_id=user_details.id, applicant_id=applicant_id, status=status
        )
        logger.info(
            f"[update_status] Status updated to {status} for applicant {applicant_id} by recruiter {user_details.id}: {table.__dict__}"
        )
        repo.close()
        return Model.model_validate(table)

    def update_tags(
        self, user_details: UserDetails, applicant_id: int, tags: list[str]
    ) -> Model:
        repo = Repository(get_db())
        table = repo.get_by_recruiter_and_applicant(
            recruiter_id=user_details.id, applicant_id=applicant_id
        )
        if not table:
            logger.error(f"Applicant not found: {applicant_id}")
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail="Applicant not found"
            )
        model = Model.model_validate(table)
        updated_tags = list(set(model.tags or [] + tags))
        logger.info(
            f"Updating tags for applicant {applicant_id} by recruiter {user_details.id}: {updated_tags}"
        )
        table = repo.update_tags(
            recruiter_id=user_details.id, applicant_id=applicant_id, tags=updated_tags
        )
        repo.close()
        return Model.model_validate(table)

    def get_applicant_status(
        self, user_details: UserDetails, applicant_id: int
    ) -> Status:
        repo = Repository(get_db())
        table = repo.get_by_recruiter_and_applicant(
            recruiter_id=user_details.id, applicant_id=applicant_id
        )
        if not table:
            table = repo.get_applicant_by_recruiter_and_not_status(
                recruiter_id=user_details.id,
                applicant_id=applicant_id,
                status=Status.RETIRED,
            )
            repo.close()
            if not table:
                return Status.NOT_INITIATED
            else:
                model = Model.model_validate(table)
                return model.status
        else:
            repo.close()
            model = Model.model_validate(table)
            return model.status

    def delete(self, applicant_id: int, recruiter_id: int) -> None:
        repo = Repository(get_db())
        logger.info(f"[delete] Deleting applicant {applicant_id}")
        repo.delete(recruiter_id=recruiter_id, applicant_id=applicant_id)
        repo.close()
