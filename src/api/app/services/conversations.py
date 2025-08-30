from uuid import uuid4
from typing import List
from datetime import datetime

from fastapi import HTTPException, status as http_status

from app.core.logger import logger

from app.db.postgres import get_db

from app.repositories.conversations import Repository
from app.repositories.config import Repository as ConfigRepository

from app.models.utils import Event
from app.models.configs import Model as Config
from app.models.user_login import UserDetails, Role
from app.models.conversations import Model, Request, Response, Conversation


class Service:
    def __init__(self, repo: Repository):
        self.repo = repo
        self.config_repo = ConfigRepository(self.repo.db)

    def create(self, user_details: UserDetails, body: Request) -> Response:
        conversations = [
            Conversation.model_validate(conv) for conv in (body.conversations or [])
        ]
        model = Model(
            recruiter_id=user_details.id,
            applicant_id=body.applicant_id,
            conversations=conversations,
        )  # type: ignore
        table = self.repo.get_by_recruiter_and_applicant(
            model.recruiter_id, model.applicant_id
        )
        if table:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="Conversation already exists",
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

    def update_conversation(
        self, user_details: UserDetails, applicant_id: int, event: Event, role: Role
    ) -> Model:
        repo = Repository(get_db())
        config_repo = ConfigRepository(repo.db)
        conversation = Conversation(
            sender_id=event.sender_id,
            content=event.content,  # type: ignore
            role=role,
            ts=event.timestamp,
            mid=event.mid,
            msg_type=event.msg_type,  # type: ignore
        )
        table = repo.get_by_recruiter_and_applicant(user_details.id, applicant_id)
        if not table:
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
            table = repo.create(
                Model(
                    recruiter_id=user_details.id,
                    applicant_id=applicant_id,
                    conversations=[conversation],
                )  # type: ignore
            )
        else:
            model = Model.model_validate(table)
            if model.recruiter_id != user_details.id:
                raise HTTPException(
                    status_code=http_status.HTTP_401_UNAUTHORIZED,
                    detail="Not authorized",
                )
            table = repo.update_conversations(
                recruiter_id=user_details.id,
                applicant_id=applicant_id,
                conversation=conversation,
            )
        repo.close()
        config_repo.close()
        logger.info(
            f"[update_conversation] Updated conversation for applicant {applicant_id} by recruiter {user_details.id}"
        )
        return Model.model_validate(table)

    def get_history(
        self, user_details: UserDetails, applicant_id: int
    ) -> List[Conversation]:
        repo = Repository(get_db())
        config_repo = ConfigRepository(repo.db)
        table = repo.get_by_recruiter_and_applicant(user_details.id, applicant_id)
        if not table:
            config = config_repo.get_by_recruiter_and_applicant(
                user_details.id, applicant_id
            )
            if not config:
                config = Config(
                    recruiter_id=user_details.id,
                    applicant_id=applicant_id,
                )  # type: ignore
                config = config_repo.create(config)
            table = repo.create(
                Model(
                    recruiter_id=user_details.id,
                    applicant_id=applicant_id,
                    conversations=[],
                )  # type: ignore
            )
        repo.close()
        config_repo.close()
        model = Model.model_validate(table)
        if model.conversations:
            return model.conversations
        return []

    def delete(self, applicant_id: int, recruiter_id: int) -> None:
        repo = Repository(get_db())
        logger.info(f"[delete] Deleting applicant {applicant_id}")
        repo.delete(recruiter_id=recruiter_id, applicant_id=applicant_id)
        repo.close()
