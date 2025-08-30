from enum import StrEnum
from uuid import UUID, uuid4
from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class ErrorCodes(StrEnum):
    _400 = "BAD_REQUEST"
    _401 = "UNAUTHORIZED"
    _403 = "FORBIDDEN"
    _404 = "NOT_FOUND"
    _409 = "CONFLICT"
    _422 = "UNPROCESSABLE_ENTITY"
    _429 = "TOO_MANY_REQUESTS"
    _500 = "INTERNAL_SERVER_ERROR"
    _503 = "SERVICE_UNAVAILABLE"


class ErrorObject(BaseModel):
    code: ErrorCodes = Field(..., description="Error code indicating the type of error")
    message: str = Field(..., description="Detailed error message")
    details: Optional[List[Dict[str, Any]]] = Field(
        None, description="Additional details about the error"
    )


class ErrorResponse(BaseModel):
    mid: UUID = Field(uuid4(), description="Message ID (must be UUID4)")
    ts: datetime = Field(
        datetime.now(), description="Request timestamp in UNIX milliseconds"
    )
    error: ErrorObject = Field(
        ...,
        description="Error details including code, message, and details",
    )


class SuccessResponse(BaseModel):
    mid: UUID = Field(uuid4(), description="Message ID (must be UUID4)")
    ts: datetime = Field(
        datetime.now(), description="Request timestamp in UNIX milliseconds"
    )
    data: Optional[List[Dict[str, Any]]] = Field(
        None, description="Optional data returned with the success response"
    )


class APIRequest(BaseModel):
    mid: UUID = Field(uuid4(), description="Message ID (must be UUID4)")
    ts: datetime = Field(datetime.now(), description="Request timestamp in ISO format")
    request: Optional[Dict[str, Any]] = Field(None, description="Body of the request")  # type: ignore
