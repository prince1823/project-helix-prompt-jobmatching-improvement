from enum import StrEnum
from datetime import datetime
from typing import Optional, List, Literal

from pydantic import BaseModel, Field, EmailStr
from pydantic_extra_types.language_code import LanguageName


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


class UserWorkflowStatus(StrEnum):
    NOT_INITIATED = "NOT_INITIATED"
    INITIATED = "INITIATED"
    DETAILS_IN_PROGRESS = "DETAILS_IN_PROGRESS"
    DETAILS_COMPLETED = "DETAILS_COMPLETED"
    RETIRED = "RETIRED"


class Applicant(BaseModel):
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
    user_workflow_status: UserWorkflowStatus = Field(
        default=UserWorkflowStatus.NOT_INITIATED,
        description="The current status of the user's workflow in the recruitment process",
    )
    locale: Optional[LanguageEnum] = Field(
        default=LanguageEnum.ENGLISH,
        description="The locale in which to converse with the user, e.g., 'en-IN'",
    )
    name: Optional[str] = Field(default=None, description="The name of the user")
    email: Optional[EmailStr] = Field(
        default=None, description="The email address of the user"
    )
    age: Optional[int] = Field(
        default=None, description="The age of the user", ge=18, le=65
    )
    gender: Optional[Literal["male", "female", "other"]] = Field(
        default=None, description="The gender of the user"
    )
    city: Optional[str] = Field(
        default=None, description="The city where the user resides"
    )
    postal_code: Optional[int] = Field(
        default=None,
        description="The PIN/Postal code of the user",
        ge=100000,
        le=999999,
    )
    languages: Optional[List[LanguageName]] = Field(
        default=None, description="The languages spoken by the user"
    )
    highest_education_qualification: Optional[
        Literal["10th", "12th", "Diploma", "Graduate", "Post Graduate", "Other"]
    ] = Field(default=None, description="The highest qualification of the user")
    years_experience: Optional[int] = Field(
        default=None,
        description="The relative experience the user has in their field",
        ge=0,
        le=50,
    )
    work_preferences: Optional[str] = Field(
        default=None,
        description="The work preferences the user may have. For example, role, industry, location, etc.",
    )
    currently_employed: Optional[bool] = Field(
        default=None,
        description="Whether the user is currently employed or not. When can they join? Whether they have a 2 wheeler",
    )
    notice_period: Optional[int] = Field(
        default=None,
        description="The notice period in days that the user has has to serve, if they are currently employed",
        ge=0,
        le=90,
    )
    monthly_salary_expectation: Optional[int] = Field(
        default=None,
        description="The monthly salary expectation of the user in INR",
        ge=0,
        le=1000000,
    )
    has_2_wheeler: Optional[bool] = Field(
        default=None, description="Whether the user has a 2 wheeler"
    )
    created_at: str = Field(
        default=datetime.now().isoformat(),
        description="The timestamp when the user was created",
    )
    updated_at: Optional[str] = Field(
        default=None, description="The timestamp when the user was last updated"
    )
    response: Optional[str] = Field(
        default=None, description="The previous response message to be sent to the user"
    )


class LLMResponse(BaseModel):
    name: Optional[str] = Field(default=None, description="The name of the user")
    email: Optional[EmailStr] = Field(
        default=None, description="The email address of the user"
    )
    age: Optional[int] = Field(
        default=None, description="The age of the user", ge=18, le=65
    )
    gender: Optional[Literal["male", "female", "other"]] = Field(
        default=None, description="The gender of the user"
    )
    city: Optional[str] = Field(
        default=None, description="The city where the user resides"
    )
    postal_code: Optional[int] = Field(
        default=None,
        description="The PIN/Postal code of the user",
        ge=100000,
        le=999999,
    )
    languages: Optional[List[LanguageName]] = Field(
        default=None, description="The languages spoken by the user"
    )
    highest_education_qualification: Optional[
        Literal["10th", "12th", "Diploma", "Graduate", "Post Graduate", "Other"]
    ] = Field(
        default=None, description="The highest educational qualification of the user"
    )
    years_experience: Optional[int] = Field(
        default=None,
        description="The relative experience the user has in their field",
        ge=0,
        le=50,
    )
    work_preferences: Optional[str] = Field(
        default=None,
        description="The work preferences the user may have. For example, what role, industry, location, etc. they are looking for",
    )
    currently_employed: Optional[bool] = Field(
        default=None, description="Whether the user is currently employed or not."
    )
    notice_period: Optional[int] = Field(
        default=None,
        description="The notice period in days that the user has has to serve, if they are currently employed",
        ge=0,
        le=90,
    )
    monthly_salary_expectation: Optional[int] = Field(
        default=None,
        description="The monthly salary expectation of the user in INR",
        ge=0,
        le=1000000,
    )
    has_2_wheeler: Optional[bool] = Field(
        default=None, description="Whether the user has a 2 wheeler"
    )
    response: str = Field(
        ...,
        description="The response message containing the next question that needs to be sent to the user",
    )


class Locale(BaseModel):
    locale: LanguageEnum = Field(
        ..., description="The locale in which to converse with the user, e.g., 'en-IN'"
    )


class LocaleUpdate(BaseModel):
    update: bool = Field(..., description="Whether to update the locale or not")
    locale: Optional[LanguageEnum] = Field(
        ..., description="The locale in which to converse with the user, e.g., 'en-IN'"
    )


class Commands(StrEnum):
    ENABLE = "/enable"
    DISABLE = "/disable"
    EXPORT = "/export"


class Conversation(BaseModel):
    sender_id: int = Field(
        ...,
        description="The unique identifier for the user",
        ge=911000000000,
        le=919999999999,
    )
    ts: str = Field(..., description="")
    content: str = Field(..., description="")
    mid: Optional[str] = Field(..., description="")
    msg_type: Literal["text", "image", "video", "audio", "document"] = Field(
        ..., description="The type of message sent by the user"
    )


class Annotation(BaseModel):
    annotator_id: str = Field(..., description="")
    ts: str = Field(..., description="")
    content: str = Field(..., description="")
    rating: bool = Field(..., description="")


class Conversations(BaseModel):
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
    annotations: Optional[List[Annotation]] = Field(..., description="")
    created_at: str = Field(..., description="The timestamp when the user was created")
    updated_at: str = Field(
        ..., description="The timestamp when the user was last updated"
    )


class UIRole(StrEnum):
    ADMIN = "admin"
    ANNOTATOR = "annotator"
    VIEWER = "viewer"


class DisabledBy(StrEnum):
    SYSTEM = "system"
    USER = "recruiter"
