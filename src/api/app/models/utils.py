from enum import StrEnum
from typing import Optional, Literal

from pydantic import BaseModel, Field


class LanguageEnum(StrEnum):
    ENGLISH = "en-IN"
    HINDI = "hi-IN"
    BENGALI = "bn-IN"
    GUJARATI = "gu-IN"
    KANNADA = "kn-IN"
    MALAYALAM = "ml-IN"
    MARATHI = "mr-IN"
    ODIA = "od-IN"
    PUNJABI = "pa-IN"
    TAMIL = "ta-IN"
    TELUGU = "te-IN"


class SavedContactsModel(BaseModel):
    our_jid: str = Field(
        ...,
        description="The JID of the contact in our system",
    )
    their_jid: str = Field(
        ...,
        description="The JID of the contact in their system",
    )
    first_name: Optional[str] = Field(
        default=None, description="The first name of the contact"
    )
    full_name: Optional[str] = Field(
        default=None, description="The full name of the contact"
    )
    push_name: Optional[str] = Field(
        default=None, description="The push name of the contact"
    )
    business_name: Optional[str] = Field(
        default=None, description="The business name of the contact"
    )


class Event(BaseModel):
    mid: str = Field(..., description="Message ID")
    timestamp: str = Field(..., description="The timestamp of the event")
    chat_id: str = Field(
        ...,
        description="The unique identifier for the chat",
    )
    receiver_id: int = Field(
        ...,
        description="The unique identifier for the receiver",
        ge=911000000000,
        le=919999999999,
    )
    sender_id: int = Field(
        ...,
        description="The unique identifier for the sender",
        ge=911000000000,
        le=919999999999,
    )
    msg_type: Literal["typing", "text", "document", "audio"] = Field(
        ..., description="The type of event"
    )
    content: Optional[str] = Field(default=None, description="Content of the event")
    mime_type: Optional[str] = Field(
        default=None, description="MIME type of the content, e.g., 'application/pdf'"
    )


class Commands(StrEnum):
    ENABLE = "/enable"
    DISABLE = "/disable"
    EXPORT = "/export"


class UpdatedBy(StrEnum):
    SYSTEM = "system"
    USER = "recruiter"


class Locale(BaseModel):
    locale: LanguageEnum = Field(
        ..., description="The locale in which to converse with the user, e.g., 'en-IN'"
    )


class LocaleUpdate(BaseModel):
    update: bool = Field(..., description="Whether to update the locale or not")
    locale: Optional[LanguageEnum] = Field(
        ..., description="The locale in which to converse with the user, e.g., 'en-IN'"
    )
