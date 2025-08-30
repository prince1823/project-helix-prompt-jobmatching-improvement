from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field

from app.models.utils import LanguageEnum
from app.models.requests import SuccessResponse, APIRequest


class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = Field(
        None,
        description="The unique identifier for the configuration",
    )
    recruiter_id: int = Field(
        ...,
        description="The unique identifier for the recruiter",
        ge=911000000000,
        le=919999999999,
    )
    applicant_id: int = Field(
        ...,
        description="The unique identifier for the user",
        ge=911000000000,
        le=919999999999,
    )
    enabled: bool = Field(
        default=True, description="Indicates if the configuration is enabled"
    )
    locale: Optional[LanguageEnum] = Field(
        default=None, description="Locale supported by the user"
    )
    message_count: int = Field(
        default=0, description="Total messages based on particular chat"
    )
    created_at: datetime = Field(
        default=datetime.now(),
        description="The timestamp when the user was created",
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="The timestamp when the user was last updated"
    )
    updated_by: Optional[str] = Field(
        default="SYSTEM", description="User who last updated the configuration"
    )
    additional_config: Optional[dict] = Field(
        default=None, description="Additional configuration in JSON format"
    )


class Request(BaseModel):
    applicant_id: int = Field(
        ...,
        description="The unique identifier for the user",
        ge=911000000000,
        le=919999999999,
    )
    enabled: Optional[bool] = True
    locale: Optional[LanguageEnum] = LanguageEnum.ENGLISH
    additional_config: Optional[dict] = None


class RequestBody(APIRequest):
    request: Request


class Response(SuccessResponse):
    data: List[Model]
