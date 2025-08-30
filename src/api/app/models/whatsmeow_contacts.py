from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

from app.models.requests import SuccessResponse


class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    our_jid: str = Field(..., alias="jid")
    their_jid: str = Field(..., alias="jid")
    first_name: Optional[str] = Field(..., alias="firstName")
    full_name: Optional[str] = Field(..., alias="fullName")
    push_name: Optional[str] = Field(..., alias="pushName")
    business_name: Optional[str] = Field(..., alias="businessName")


class Response(SuccessResponse):
    data: List[Model]
