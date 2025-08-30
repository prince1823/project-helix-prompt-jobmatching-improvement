from uuid import uuid4
from datetime import datetime

from pydantic_core import ValidationError
from fastapi import status as http_status, HTTPException

from app.core.config import config
from app.core.logger import logger

from app.repositories.list_actions import Repository
from app.repositories.config import Repository as ConfigsRepository
from app.repositories.applicants import Repository as ApplicantsRepository
from app.repositories.recruiter_lists import Repository as ListsRepository
from app.repositories.action_details import Repository as ActionsRepository

from app.models.configs import Model as Config
from app.models.user_login import UserDetails, Role
from app.models.applicants import Model as Applicant, Request as ApplicantRequest
from app.models.recruiter_lists import Model as ListModel
from app.models.action_details import Model as DetailModel, Status as DetailStatus
from app.models.list_actions import (
    Actions,
    CancelResponse,
    ListActionStatusItem,
    Model,
    Request,
    Response,
    SendItem,
    SendRequest,
    SendResponse,
    StatusResponse,
    Status,
)

from app.services.redis_service import Service as RedisService
from app.services.applicants import Service as ApplicantsService


class Service:
    def __init__(self, repo: Repository):
        self.repo = repo
        self.lists_repo = ListsRepository(repo.db)
        self.config_repo = ConfigsRepository(repo.db)
        self.applicants_repo = ApplicantsRepository(repo.db)
        self.actions_repo = ActionsRepository(repo.db)
        self.redis_service = RedisService(config["redis"]["schedule_send"]["db"])

    def create(
        self, user_details: UserDetails, id: int, action_type: Actions, body: Request
    ) -> Response:
        # to-do handle duplicate or conflicting db actions
        model = Model(
            list_id=id,
            action_type=action_type,
            applicants=body.request.applicants or [],
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
        admin = False
        if user_details.role == Role.ADMIN:
            admin = True
        tables = self.repo.get_all(id=user_details.id, admin=admin)
        if not tables:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="No actions found",
            )
        return Response(
            data=[Model.model_validate(table) for table in tables],
            mid=uuid4(),
            ts=datetime.now(),
        )

    def get(self, user_details: UserDetails, id: int) -> Response:
        table = self.repo.get(id=id)
        if not table:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Action not found",
            )
        model = Model.model_validate(table)
        _list = self.lists_repo.get(id=model.list_id)
        if _list:
            if (
                _list.recruiter_id != user_details.id
                and user_details.role != Role.ADMIN
            ):  # type: ignore
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to access this action",
                )
        return Response(
            data=[model],
            mid=uuid4(),
            ts=datetime.now(),
        )

    def get_by_list(self, user_details: UserDetails, id: int) -> Response:
        if user_details.role == Role.ADMIN:
            tables = self.repo.get_by_list(id=id, admin=True)
        else:
            tables = self.repo.get_by_list(id=id)
        if not tables:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="No actions found",
            )
        return Response(
            data=[Model.model_validate(table) for table in tables],
            mid=uuid4(),
            ts=datetime.now(),
        )

    def get_by_list_status(
        self, user_details: UserDetails, id: int, status: Status
    ) -> Response:
        if user_details.role == Role.ADMIN:
            tables = self.repo.get_by_list_status(id=id, status=status, admin=True)
        else:
            tables = self.repo.get_by_list_status(id=id, status=status)
        if not tables:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="No actions found",
            )
        return Response(
            data=[Model.model_validate(table) for table in tables],
            mid=uuid4(),
            ts=datetime.now(),
        )

    def get_by_list_type(
        self, user_details: UserDetails, id: int, action_type: Actions
    ) -> Response:
        if user_details.role == Role.ADMIN:
            tables = self.repo.get_by_list_type(
                id=id, action_type=action_type, admin=True
            )
        else:
            tables = self.repo.get_by_list_type(id=id, action_type=action_type)
        if not tables:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="No actions found",
            )
        return Response(
            data=[Model.model_validate(table) for table in tables],
            mid=uuid4(),
            ts=datetime.now(),
        )

    def get_by_list_status_type(
        self, user_details: UserDetails, id: int, status: Status, action_type: Actions
    ) -> Response:
        if user_details.role == Role.ADMIN:
            tables = self.repo.get_by_list_status_type(
                id=id, status=status, action_type=action_type, admin=True
            )
        else:
            tables = self.repo.get_by_list_status_type(
                id=id, status=status, action_type=action_type
            )
        if not tables:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="No actions found",
            )
        return Response(
            data=[Model.model_validate(table) for table in tables],
            mid=uuid4(),
            ts=datetime.now(),
        )

    # to-do add to applicant tags
    def add(self, user_details: UserDetails, id: int, body: Request) -> StatusResponse:
        _list = self.lists_repo.get(id=id)
        _list = ListModel.model_validate(_list)
        if not _list:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="List not found",
            )
        if _list.recruiter_id != user_details.id and user_details.role != Role.ADMIN:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this list",
            )
        no_change = set(_list.applicants).intersection(  # type: ignore
            set(body.request.applicants or [])
        )
        added = set(body.request.applicants or []) - no_change
        failed = []
        for applicant_id in list(added):
            applicant_service = ApplicantsService(self.applicants_repo)
            try:
                exists = applicant_service.get_by_recruiter_and_applicant(
                    user_details=user_details, applicant_id=applicant_id
                )
            except HTTPException as e:
                if e.status_code == http_status.HTTP_404_NOT_FOUND:
                    exists = None
                else:
                    raise
            if exists:
                applicant_service.update_tags(
                    user_details=user_details,
                    applicant_id=applicant_id,
                    tags=[_list.list_name],
                )
            else:
                applicant = ApplicantRequest(
                    applicant_id=applicant_id, tags=[_list.list_name]
                )
                try:
                    applicant_service.create(user_details=user_details, body=applicant)
                except HTTPException as e:
                    if e.status_code == http_status.HTTP_422_UNPROCESSABLE_ENTITY:
                        added.remove(applicant_id)
                        failed.append(applicant_id)
                    else:
                        raise
        data = []
        if no_change:
            data.append(
                ListActionStatusItem(
                    status=Status.NO_CHANGE, applicants=list(no_change)
                )
            )
        if added:
            data.append(
                ListActionStatusItem(status=Status.COMPLETED, applicants=list(added))
            )
        if failed:
            data.append(ListActionStatusItem(status=Status.FAILED, applicants=failed))
        updated = list(set(_list.applicants).union(added))  # type: ignore
        update = self.lists_repo.update(id=id, applicants=updated)
        if update is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="List not found",
            )
        model = Model(
            list_id=id,
            action_type=Actions.ADD,
            applicants=body.request.applicants,
            updated_by=str(user_details.id),
            status=Status.COMPLETED if added else Status.NO_CHANGE,
        )  # type: ignore
        self.repo.create(model=model)
        return StatusResponse(
            data=data,
            mid=uuid4(),
            ts=datetime.now(),
        )

    # to-do remove from applicant tags
    def remove(
        self, user_details: UserDetails, id: int, body: Request
    ) -> StatusResponse:
        _list = self.lists_repo.get(id=id)
        _list = ListModel.model_validate(_list)
        if not _list:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="List not found",
            )
        if _list.recruiter_id != user_details.id and user_details.role != Role.ADMIN:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this list",
            )
        updated = set(_list.applicants).intersection(set(body.request.applicants or []))  # type: ignore
        no_change = set(body.request.applicants or []) - updated
        new_list = set(_list.applicants) - updated  # type: ignore
        for applicant_id in list(updated):
            exists = self.applicants_repo.get_by_recruiter_and_applicant(
                recruiter_id=user_details.id, applicant_id=applicant_id
            )
            if exists:
                applicant = Applicant.model_validate(exists)
                if applicant.tags and (_list.list_name in applicant.tags):
                    applicant.tags.remove(_list.list_name)
                    self.applicants_repo.update_tags(
                        recruiter_id=user_details.id,
                        applicant_id=applicant_id,
                        tags=applicant.tags,
                    )
        data = [
            ListActionStatusItem(status=Status.NO_CHANGE, applicants=list(no_change)),
            ListActionStatusItem(status=Status.COMPLETED, applicants=list(updated)),
        ]
        update = self.lists_repo.update(id=id, applicants=list(new_list))
        if update is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="List not found",
            )
        model = Model(
            list_id=id,
            action_type=Actions.REMOVE,
            applicants=body.request.applicants or [],
            updated_by=str(user_details.id),
            status=Status.COMPLETED if updated else Status.NO_CHANGE,
        )  # type: ignore
        self.repo.create(model=model)
        return StatusResponse(
            data=data,
            mid=uuid4(),
            ts=datetime.now(),
        )

    def disable(
        self, user_details: UserDetails, id: int, body: Request
    ) -> StatusResponse:
        table = self.lists_repo.get(id=id)
        if not table:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="List not found",
            )
        _list = ListModel.model_validate(table)
        if _list.recruiter_id != user_details.id and user_details.role != Role.ADMIN:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this list",
            )
        updated = []
        no_change = []
        for applicant in body.request.applicants:
            config = self.config_repo.get_by_recruiter_and_applicant(
                recruiter_id=user_details.id, applicant_id=applicant
            )
            if not config:
                try:
                    config = Config(
                        recruiter_id=user_details.id,
                        applicant_id=applicant,
                        enabled=False,
                        updated_by=str(user_details.id),
                    )  # type: ignore
                except ValidationError as e:
                    no_change.append(applicant)
                    continue
                self.config_repo.create(config)
                updated.append(applicant)
            elif Config.model_validate(config).enabled:
                self.config_repo.update_enabled(
                    recruiter_id=user_details.id,
                    applicant_id=applicant,
                    enabled=False,
                    updated_by=str(user_details.id),
                )
                updated.append(applicant)
            else:
                no_change.append(applicant)
        data = [
            ListActionStatusItem(status=Status.NO_CHANGE, applicants=list(no_change)),
            ListActionStatusItem(status=Status.COMPLETED, applicants=list(updated)),
        ]
        model = Model(
            list_id=id,
            action_type=Actions.DISABLE,
            applicants=body.request.applicants or [],
            updated_by=str(user_details.id),
            status=Status.COMPLETED,
        )  # type: ignore
        self.repo.create(model=model)
        return StatusResponse(
            data=data,
            mid=uuid4(),
            ts=datetime.now(),
        )

    def send(
        self, user_details: UserDetails, id: int, body: SendRequest
    ) -> SendResponse:
        table = self.lists_repo.get(id=id)
        if not table:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="List not found",
            )
        _list = ListModel.model_validate(table)
        if _list.recruiter_id != user_details.id and user_details.role != Role.ADMIN:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this list",
            )
        model = Model(
            list_id=id,
            action_type=Actions.SEND,
            applicants=body.request.applicants or [],
            updated_by=str(user_details.id),
            status=Status.INITIATED,
        )  # type: ignore
        action = self.repo.create(model=model)
        action = Model.model_validate(action)
        if body.request.additional_config:
            content = body.request.additional_config.get("template_message", "")
            self.redis_service.schedule_send(
                action_id=action.id,  # type: ignore
                recruiter_id=user_details.id,
                applicants=body.request.applicants or [],
                content=content,
            )
        else:
            self.redis_service.schedule_send(
                action_id=action.id,  # type: ignore
                recruiter_id=user_details.id,
                applicants=body.request.applicants or [],
            )
        return SendResponse(
            mid=body.mid,
            ts=datetime.now(),
            data=[
                SendItem(
                    action_id=str(action.id),
                    status="SCHEDULED",
                    status_url=f"/api/v1/list-action/{action.id}/status",
                )
            ],
        )

    def nudge(self, user_details: UserDetails, id: int, body: Request) -> SendResponse:
        table = self.lists_repo.get(id=id)
        if not table:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="List not found",
            )
        _list = ListModel.model_validate(table)
        if _list.recruiter_id != user_details.id and user_details.role != Role.ADMIN:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this list",
            )
        model = Model(
            list_id=id,
            action_type=Actions.NUDGE,
            applicants=body.request.applicants or [],
            updated_by=str(user_details.id),
            status=Status.INITIATED,
        )  # type: ignore
        table = self.repo.create(model=model)
        model = Model.model_validate(table)
        logger.info(f"Creating nudge for action {model.model_dump()}")
        applicants = self.applicants_repo.get_by_recruiter_and_applicants(
            recruiter_id=user_details.id,
            applicant_ids=model.applicants,
        )
        applicants = [Applicant.model_validate(applicant) for applicant in applicants]
        logger.info(f"Found applicants for nudge: {applicants}")
        for applicant in applicants:
            if applicant.response:
                logger.info(
                    f"Scheduling nudge for applicant {applicant.applicant_id}, content: {applicant.response}, action_id: {model.id}, recruiter_id: {user_details.id}"
                )
                self.redis_service.schedule_send(
                    action_id=model.id,  # type: ignore
                    recruiter_id=user_details.id,
                    applicants=[applicant.applicant_id],  # type: ignore
                    content=applicant.response,
                )
        return SendResponse(
            mid=body.mid,
            ts=datetime.now(),
            data=[
                SendItem(
                    action_id=str(model.id),
                    status="SCHEDULED",
                    status_url=f"/api/v1/list-action/{model.id}/status",
                )
            ],
        )

    def cancel(
        self, user_details: UserDetails, id: int, action_id: int
    ) -> CancelResponse:
        table = self.lists_repo.get(id=id)
        if not table:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="List not found",
            )
        _list = ListModel.model_validate(table)
        if _list.recruiter_id != user_details.id and user_details.role != Role.ADMIN:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this list",
            )
        details = self.actions_repo.get_all(id=action_id)
        details = [DetailModel.model_validate(detail) for detail in details]
        for detail in details:
            if detail.status == DetailStatus.SCHEDULED:
                self.redis_service.cancel_action(applicant_id=detail.applicant_id)
            if detail.status not in [
                DetailStatus.COMPLETED,
                DetailStatus.CANCELLED,
                DetailStatus.FAILED,
            ]:
                self.actions_repo.update(id=detail.id, status=DetailStatus.CANCELLED)  # type: ignore
        action = self.repo.get(id=action_id)
        action = Model.model_validate(action)
        if action.status not in [Status.COMPLETED, Status.CANCELLED, Status.FAILED]:
            self.repo.update(id=action.id, status=Status.CANCELLED)  # type: ignore
        details = self.actions_repo.get_all(id=action_id)
        details = [DetailModel.model_validate(detail) for detail in details]
        return CancelResponse(
            mid=uuid4(),
            ts=datetime.now(),
            data=details,
        )
