from enum import StrEnum
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Status(StrEnum):
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    SCHEDULED = "SCHEDULED"
    FAILED = "FAILED"
    NO_CHANGE = "NO_CHANGE"


class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = Field(
        None,
        description="The unique identifier for the action details",
    )
    action_id: int = Field(
        ..., description="The unique identifier of action job on the recruiter list"
    )
    applicant_id: int = Field(
        ...,
        description="The unique identifier for the applicant involved in the action",
        ge=911000000000,
        le=919999999999,
    )
    status: Status = Field(
        default=Status.SCHEDULED,
        description="Status of the list action",
    )
    additional_config: Optional[dict] = Field(
        default=None,
        description="The content of the action details",
    )
    created_at: datetime = Field(
        default=datetime.now(),
        description="The timestamp when the action was created",
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="The timestamp when the action was last updated"
    )
    scheduled_at: Optional[datetime] = Field(
        default=None,
        description="The timestamp when the action is scheduled to be executed",
    )
