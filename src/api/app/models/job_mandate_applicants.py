from enum import StrEnum
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Status(StrEnum):
    MATCHED = "matched"
    OFFERED = "offered"
    USER_ACCEPTED = "accepted"
    USER_REJECTED = "rejected"
    CRITERIA_FAILED = "failed"
    CRITERIA_SUCCESS = "success"
    SHORTLISTED = "shortlisted"


class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = Field(
        None, description="The unique identifier for the job mandate applicant"
    )
    job_mandate_id: int = Field(
        ..., description="The unique identifier for the job mandate"
    )
    recruiter_id: int = Field(
        ..., description="The unique identifier for the recruiter"
    )
    applicant_id: int = Field(
        ..., description="The unique identifier for the applicant"
    )
    status: Status = Field(
        Status.MATCHED,
        description="The current status of the applicant",
    )
    rank: int = Field(
        ..., description="The rank of the job mandate applicant based on the criteria"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="The creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="The update timestamp"
    )
