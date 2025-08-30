from enum import StrEnum
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.requests import APIRequest, SuccessResponse


class Role(StrEnum):
    ADMIN = "ADMIN"
    ANNOTATOR = "ANNOTATOR"
    VIEWER = "VIEWER"
    RECRUITER = "RECRUITER"
    SYSTEM = "SYSTEM"
    APPLICANT = "APPLICANT"


class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = Field(
        None,
        description="The unique identifier for the user login",
    )
    username: str = Field(
        ...,
        description="The username of the user",
    )
    password: str = Field(
        ...,
        description="The password of the user",
    )
    role: Role = Field(
        ...,
        description="The role of the user",
    )
    created_at: datetime = Field(
        default=datetime.now(),
        description="The timestamp when the user login was created",
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="The timestamp when the user login was last updated"
    )


class UserDetails(BaseModel):
    id: int = Field(
        ...,
        description="The unique identifier for the user",
        ge=911000000000,
        le=919999999999,
    )
    role: Role = Field(..., description="The role of the user")


class CreateRequest(BaseModel):
    username: str = Field(..., description="The username for the user login")
    password: str = Field(..., description="The password for the user login")
    role: Role = Field(..., description="The role of the user")


class Request(APIRequest):
    request: CreateRequest


class Response(SuccessResponse):
    data: List[Model]
