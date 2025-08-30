from enum import StrEnum
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.action_details import Model as ActionModel
from app.models.requests import APIRequest, SuccessResponse


class Actions(StrEnum):
    ADD = "ADD"
    REMOVE = "REMOVE"
    NUDGE = "NUDGE"
    SEND = "SEND"
    DISABLE = "DISABLE"


class Status(StrEnum):
    INITIATED = "INITIATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    NO_CHANGE = "NO_CHANGE"


class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = Field(
        None,
        description="The unique identifier for the list action",
    )
    list_id: int = Field(
        ...,
        description="The unique identifier for the recruiter list",
    )
    action_type: Actions = Field(
        ..., description="Type of action performed on the recruiter list"
    )
    applicants: List[int] = Field(
        ...,
        description="The unique identifiers for the applicants involved in the action",
    )
    status: Status = Field(
        default=Status.INITIATED, description="Status of the list action"
    )
    created_at: datetime = Field(
        default=datetime.now(),
        description="The timestamp when the action was created",
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="The timestamp when the action was last updated"
    )
    updated_by: Optional[str] = Field(
        default="SYSTEM", description="User who last updated the action"
    )


class ListActionSendItem(BaseModel):
    applicants: List[int] = Field(
        ..., examples=[[911244567890, 919012345678, 915678901234]]
    )
    additional_config: Optional[dict] = Field(
        default=None,
        examples=[
            {
                "template_message": "Hello, this is a test message.",
                "template_id": "12345",
            }
        ],
    )


class SendRequest(APIRequest):
    request: ListActionSendItem


class ListActionItem(BaseModel):
    applicants: List[int] = Field(
        ..., examples=[[911244567890, 919012345678, 915678901234]]
    )


class Request(APIRequest):
    request: ListActionItem


class ListActionStatusItem(BaseModel):
    status: Status
    applicants: List[int]


class StatusResponse(SuccessResponse):
    data: List[ListActionStatusItem]


class SendItem(BaseModel):
    action_id: str
    status: str
    status_url: str


class SendResponse(SuccessResponse):
    data: List[SendItem]


class Response(SuccessResponse):
    data: List[Model]


class CancelResponse(SuccessResponse):
    data: List[ActionModel]
