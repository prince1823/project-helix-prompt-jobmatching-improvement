from enum import StrEnum
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.job_mandates import SubjectiveQuestions, QualifyingCriteria


class QuestionType(StrEnum):
    OBJECTIVE = "objective"
    SUBJECTIVE = "subjective"


class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = Field(
        None, description="The unique identifier for the job mandate question"
    )
    job_mandate_id: int = Field(
        ..., description="The unique identifier for the job mandate"
    )
    recruiter_id: int = Field(
        ..., description="The unique identifier for the recruiter"
    )
    applicant_id: int = Field(
        ..., description="The unique identifier for the job mandate applicant"
    )
    question_id: str = Field(..., description="The unique identifier for the question")
    question_type: QuestionType = Field(
        ...,
        description="The type of question, either 'objective' or 'subjective'",
    )
    question_details: QualifyingCriteria | SubjectiveQuestions = Field(
        ..., description="Details of the question in JSON format"
    )
    applicant_response: str = Field(
        ..., description="Applicant's response to the question"
    )
    status: Optional[bool] = Field(
        None, description="Status of the qualifying criteria"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="The creation timestamp"
    )
    updated_at: Optional[datetime] = Field(None, description="The update timestamp")
