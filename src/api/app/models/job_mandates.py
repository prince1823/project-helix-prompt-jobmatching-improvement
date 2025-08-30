from enum import StrEnum
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, ConfigDict

from app.models.job_mandate_applicants import Status as JobMandateApplicantsStatus


class Status(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    RETIRED = "retired"
    DRAFT = "draft"


class Industry(StrEnum):
    FRESHER = "Fresher"
    MANUFACTURING = "Manufacturing"
    SALES = "Sales"
    OTHER = "Other"


class EducationLevel(StrEnum):
    EIGHTH = "8"
    NINTH = "9"
    TENTH = "10"
    TWELFTH = "12"
    DIPLOMA = "Diploma"
    ITI = "ITI"
    UNDERGRADUATE = "UG"
    POSTGRADUATE = "PG"


class Gender(StrEnum):
    MALE = "Male"
    FEMALE = "Female"
    ANY = "Any"


class Range(BaseModel):
    min: int = Field(
        ..., description="Minimum value of the range", examples=[10000], ge=0
    )
    max: int = Field(
        ..., description="Maximum value of the range", examples=[10000], ge=0
    )


class JobBenefits(BaseModel):
    bonus: Optional[str] = Field(None, description="Bonus details")
    food: Optional[str] = Field(None, description="Food details")
    transport: Optional[str] = Field(None, description="Transport details")
    accommodation: Optional[str] = Field(None, description="Accommodation details")
    uniform: Optional[str] = Field(None, description="Uniform details")
    overtime: Optional[str] = Field(None, description="Overtime details")
    insurance: Optional[str] = Field(None, description="Insurance details")
    schemes: Optional[List[str]] = Field(None, description="Schemes details")


class PayBenefits(BaseModel):
    monthly_pay: Range = Field(..., description="Monthly pay range")
    incentive: Optional[str] = Field(None, description="Incentive details")
    benefits: Optional[JobBenefits] = Field(None, description="Job benefits details")


class JobDetails(BaseModel):
    rotational_shifts: Optional[str] = Field(
        None, description="Rotational shifts details"
    )
    shifts: Optional[str] = Field(None, description="Shifts details")
    weekly_off: Optional[str] = Field(None, description="Weekly off details")
    hours: Optional[str] = Field(None, description="Hours details")
    training: Optional[str] = Field(None, description="Training details")
    skills: Optional[List[str]] = Field(None, description="Skills details")


class InterviewProcess(BaseModel):
    rounds: int = Field(..., description="Number of interview rounds")
    documents: List[str] = Field(..., description="List of required documents")
    start_date: str = Field(..., description="Job start date")


class JobInformation(BaseModel):
    title: str = Field(..., description="Job title")
    client: str = Field(..., description="Client name")
    location: str = Field(..., description="Job location")
    description: str = Field(..., description="Job description")
    benefits: PayBenefits = Field(..., description="Job benefits")
    details: JobDetails = Field(..., description="Job details")
    interview_process: InterviewProcess = Field(
        ..., description="Interview process details"
    )


class Location(BaseModel):
    location: str = Field(..., description="Location name")
    order: int = Field(..., description="Order of the location")


class EducationRange(BaseModel):
    min: EducationLevel = Field(
        ..., description="Minimum education level", examples=["10"]
    )
    max: EducationLevel = Field(
        ..., description="Maximum education level", examples=["UG"]
    )


class FilteringCriteria(BaseModel):
    locations: List[Location] = Field(..., description="List of job locations")
    experience: Range = Field(..., description="Experience range")
    type_of_experience: Industry = Field(..., description="Type of experience")
    age: Range = Field(..., description="Age range")
    gender: Gender = Field(..., description="Gender")
    education_level: EducationRange = Field(..., description="Education level")


class Answer(BaseModel):
    text: str = Field(..., description="The answer text")
    pass_: bool = Field(..., description="Whether the answer is a pass")


class QualifyingCriteria(BaseModel):
    id: str = Field(
        ..., description="The unique identifier for the qualifying criteria question"
    )
    order: int = Field(..., description="The order of the qualifying criteria")
    strict: bool = Field(..., description="Whether the criteria is strict")
    question: str = Field(..., description="The question text")
    condition: Optional[List[dict[str, Any]]] = Field(
        None, description="Condition details"
    )
    help_text: Optional[str] = Field(None, description="Help text details")
    answers: List[Answer] = Field(..., description="List of possible answers")


class SubjectiveQuestions(BaseModel):
    id: str = Field(
        ..., description="The unique identifier for the subjective question"
    )
    order: int = Field(..., description="The order of the subjective question")
    strict: bool = Field(..., description="Whether the question is strict")
    question: str = Field(..., description="The question text")
    answers: Optional[List[str]] = Field(None, description="Answers details")


class MatchingFilters(BaseModel):
    job_id: int = Field(..., description="The unique identifier for the job")
    salary_max: int = Field(..., description="The maximum salary for the job")
    location: List[Location] = Field(..., description="List of job locations")
    experience: Range = Field(..., description="Experience range")
    type_of_experience: Industry = Field(..., description="Type of experience")
    age: Range = Field(..., description="Age range")
    gender: Gender = Field(..., description="Gender")
    education_level: EducationRange = Field(..., description="Education level")


class Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = Field(
        None, description="The unique identifier for the job mandate"
    )
    job_id: int = Field(..., description="The unique identifier for the job")
    job_information: JobInformation = Field(
        ..., description="Information about the job in JSON format"
    )
    filtering_criteria: FilteringCriteria = Field(
        ..., description="Criteria for filtering applicants in JSON format"
    )
    qualifying_criteria: List[QualifyingCriteria] = Field(
        ..., description="Qualifying criteria for the job in JSON format"
    )
    subjective_questions: Optional[List[SubjectiveQuestions]] = Field(
        None, description="Subjective questions for the job in JSON format"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="The timestamp when the job mandate was created",
    )
    status: Status = Field(..., description="The status of the job mandate")


class LatestJob(BaseModel):
    job_mandate: Model = Field(..., description="The latest job mandate details")
    job_mandate_applicant_status: Optional[JobMandateApplicantsStatus] = Field(
        None, description="The status of the job mandate applicant"
    )
