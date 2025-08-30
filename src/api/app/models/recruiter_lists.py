from enum import StrEnum
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.requests import APIRequest, SuccessResponse


class Status(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = Field(
        None,
        description="The unique identifier for the recruiter list",
    )
    recruiter_id: int = Field(
        ...,
        description="The unique identifier for the recruiter",
        ge=911000000000,
        le=919999999999,
    )
    list_name: str = Field(..., description="Name of the recruiter list")
    list_description: Optional[str] = Field(
        default=None, description="Description of the recruiter list"
    )
    applicants: Optional[List[int]] = Field(
        default=None, description="List of applicant IDs in the recruiter list"
    )
    created_at: datetime = Field(
        default=datetime.now(),
        description="The timestamp when the recruiter list was created",
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="The timestamp when the recruiter list was last updated",
    )
    updated_by: Optional[str] = Field(
        default="SYSTEM", description="User who last updated the recruiter list"
    )
    status: Status = Field(
        default=Status.ACTIVE, description="Status of the recruiter list"
    )


class CreateRequest(BaseModel):
    list_name: str = Field(..., examples=["Mumbai Drive 2025"])
    list_description: Optional[str] = Field(
        None,
        examples=[
            "Curated list of senior software engineering candidates for Q4 hiring initiatives"
        ],
    )
    applicants: Optional[List[int]] = Field(
        ..., examples=[[911244567890, 919012345678, 915678901234]]
    )


class Request(APIRequest):
    request: CreateRequest


class NameRequestItem(BaseModel):
    list_name: str = Field(..., examples=["Mumbai Drive 2025"])


class NameRequest(APIRequest):
    request: NameRequestItem


class Response(SuccessResponse):
    data: List[Model]
