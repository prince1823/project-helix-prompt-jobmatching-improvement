from datetime import datetime
from typing import Optional, List, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.user_login import Role
from app.models.requests import APIRequest, SuccessResponse


class Annotation(BaseModel):
    annotator_id: str = Field(..., description="")
    ts: str = Field(..., description="")
    content: str = Field(..., description="")
    rating: bool = Field(..., description="")


class Conversation(BaseModel):
    sender_id: int = Field(
        ...,
        description="The unique identifier for the user",
        ge=911000000000,
        le=919999999999,
    )
    role: Role = Field(..., description="The role of the user in the conversation")
    ts: str = Field(..., description="")
    content: str = Field(..., description="")
    mid: Optional[str] = Field(..., description="")
    msg_type: Literal["text", "image", "video", "audio", "document"] = Field(
        ..., description="The type of message sent by the user"
    )


class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = Field(
        None,
        description="The unique identifier for the conversation",
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
    conversations: List[Conversation] = Field(..., description="")
    annotations: Optional[List[Annotation]] = Field(None, description="")
    created_at: datetime = Field(
        default=datetime.now(), description="The timestamp when the user was created"
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="The timestamp when the user was last updated"
    )


class Request(BaseModel):
    applicant_id: int = Field(
        ...,
        description="The unique identifier for the user",
        ge=911000000000,
        le=919999999999,
    )
    conversations: List[Conversation] = Field(..., description="")
    annotations: Optional[List[Annotation]] = Field(..., description="")


class RequestBody(APIRequest):
    request: Request


class Response(SuccessResponse):
    data: List[Model]
