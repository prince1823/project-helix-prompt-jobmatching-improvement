from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field

from app.models.requests import APIRequest, SuccessResponse


class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = Field(
        default=None, description="Unique identifier for the document"
    )
    applicant_id: int = Field(description="ID of the applicant")
    recruiter_id: int = Field(description="ID of the recruiter")
    file_paths: List[str] = Field(
        ..., description="List of file paths for the documents"
    )
    updated_at: datetime = Field(default=datetime.now())


class Request(APIRequest):
    request: Model


class Response(SuccessResponse):
    data: List[Model]


class Document(BaseModel):
    applicant_id: int = Field(description="ID of the applicant")
    file_paths: List[str] = Field(..., description="File paths for the document")
