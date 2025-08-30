from enum import StrEnum
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.llm import ApplicantDetails
from app.models.requests import APIRequest, SuccessResponse


class Status(StrEnum):
    NOT_INITIATED = "NOT_INITIATED"
    INITIATED = "INITIATED"
    DETAILS_IN_PROGRESS = "DETAILS_IN_PROGRESS"
    # AWAITING_RESUME = "AWAITING_RESUME"
    DETAILS_COMPLETED = "DETAILS_COMPLETED"
    MANDATE_MATCHING = "MANDATE_MATCHING"
    SHORTLISTED = "SHORTLISTED"
    NO_MATCHES = "NO_MATCHES"
    PLACED = "PLACED"
    RETIRED = "RETIRED"


class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = Field(
        None,
        description="The unique identifier for the applicant",
    )
    applicant_id: int = Field(
        ...,
        description="The unique identifier for the user",
        ge=911000000000,
        le=919999999999,
    )
    recruiter_id: int = Field(
        ...,
        description="The unique identifier for the recruiter",
        ge=911000000000,
        le=919999999999,
    )
    details: Optional[ApplicantDetails] = Field(
        default=None,
        description="Additional details about the applicant in JSON format",
    )
    status: Status = Field(
        default=Status.NOT_INITIATED,
        description="The current status of the user's workflow",
    )
    created_at: datetime = Field(
        default=datetime.now(),
        description="The timestamp when the user was created",
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="The timestamp when the user was last updated"
    )
    response: Optional[str] = Field(
        default=None, description="The last response to the applicant"
    )
    tags: Optional[List[str]] = Field(
        default_factory=list,
        description="A list of tags associated with the applicant",
    )


class Request(BaseModel):
    applicant_id: int
    details: Optional[ApplicantDetails] = None
    status: Optional[Status] = Status.NOT_INITIATED
    tags: Optional[List[str]] = None


class RequestBody(APIRequest):
    request: Request


class Response(SuccessResponse):
    data: List[Model]


class ApplicantStatusItem(BaseModel):
    status: str
    applicants: List[int]
