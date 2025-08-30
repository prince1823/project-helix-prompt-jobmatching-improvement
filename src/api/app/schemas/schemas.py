from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    PrimaryKeyConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base

from app.db import Base

# Optional: Only needed if WhatsmeowContactsTable uses separate metadata
OtherBase = declarative_base()


class ConfigsTable(Base):
    __tablename__ = "configs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    recruiter_id = Column(BigInteger, index=True)
    applicant_id = Column(BigInteger, index=True)
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    locale = Column(String, nullable=True)
    message_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.now(), nullable=False)
    updated_at = Column(DateTime, nullable=True)
    additional_config = Column(JSONB, nullable=True)
    updated_by = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("recruiter_id", "applicant_id", name="configs_uk"),
    )


class ApplicantsTable(Base):
    __tablename__ = "applicants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recruiter_id = Column(BigInteger, nullable=False)
    applicant_id = Column(BigInteger, nullable=False)
    details = Column(JSONB, nullable=True)
    status = Column(String, default="NOT_INITIATED", nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now(), nullable=False)
    updated_at = Column(DateTime, nullable=True)
    response = Column(String, nullable=True)
    tags = Column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint("recruiter_id", "applicant_id", name="applicants_uk"),
        ForeignKeyConstraint(
            ["recruiter_id", "applicant_id"],
            ["configs.recruiter_id", "configs.applicant_id"],
            name="fk_applicants_to_configs",
        ),
        Index("applicant_details_idx", "details", postgresql_using="gin"),
    )


class ConversationsTable(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recruiter_id = Column(BigInteger, nullable=False, index=True)
    applicant_id = Column(BigInteger, nullable=False, index=True)
    conversations = Column(JSONB, nullable=False)
    annotations = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.now(), nullable=False)
    updated_at = Column(DateTime, default=datetime.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("recruiter_id", "applicant_id", name="conversations_uk"),
        ForeignKeyConstraint(
            ["recruiter_id", "applicant_id"],
            ["configs.recruiter_id", "configs.applicant_id"],
        ),
    )


class DocumentsTable(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recruiter_id = Column(BigInteger, nullable=False, index=True)
    applicant_id = Column(BigInteger, nullable=False, index=True)
    file_paths = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.now(), nullable=False)
    updated_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("recruiter_id", "applicant_id", name="documents_uk"),
        ForeignKeyConstraint(
            ["recruiter_id", "applicant_id"],
            ["configs.recruiter_id", "configs.applicant_id"],
        ),
    )


class RecruiterListsTable(Base):
    __tablename__ = "recruiter_lists"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recruiter_id = Column(BigInteger, nullable=False, index=True)
    list_name = Column(String, nullable=False)
    list_description = Column(String, nullable=True)
    applicants = Column(JSONB, nullable=True)
    status = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now())
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("recruiter_id", "list_name", name="recruiter_lists_uk"),
        # ForeignKeyConstraint(
        #     ["recruiter_id"],
        #     ["configs.recruiter_id"],
        #     name="fk_recruiter_lists_to_configs"
        # ),
    )


class ListActionsTable(Base):
    __tablename__ = "list_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    list_id = Column(Integer, nullable=False, index=True)
    action_type = Column(String, nullable=False, index=True)
    applicants = Column(JSONB, nullable=True)
    status = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now(), nullable=False)
    updated_at = Column(DateTime, nullable=True)
    updated_by = Column(String, nullable=True)

    __table_args__ = (ForeignKeyConstraint(["list_id"], ["recruiter_lists.id"]),)


class ActionDetailsTable(Base):
    __tablename__ = "action_details"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_id = Column(Integer, ForeignKey("list_actions.id"), nullable=False)
    applicant_id = Column(BigInteger, nullable=False)
    status = Column(String, nullable=False)
    additional_config = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.now(), nullable=False)
    updated_at = Column(DateTime)
    scheduled_at = Column(DateTime)

    __table_args__ = (
        UniqueConstraint("action_id", "applicant_id", name="action_details_uk"),
    )


class UserLoginTable(Base):
    __tablename__ = "user_logins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, index=True)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("username", "role", name="user_login_uk"),)


class WhatsmeowContactsTable(OtherBase):  # Separate base if needed
    __tablename__ = "whatsmeow_contacts"

    our_jid = Column(String, nullable=False)
    their_jid = Column(String, nullable=False)
    first_name = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    push_name = Column(String, nullable=True)
    business_name = Column(String, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("our_jid", "their_jid", name="whatsmeow_contacts_pk"),
    )


class JobMandates(Base):
    __tablename__ = "job_mandates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, nullable=False, unique=True, index=True)
    job_information = Column(JSONB, nullable=False)
    filtering_criteria = Column(JSONB, nullable=False)
    qualifying_criteria = Column(JSONB, nullable=False)
    subjective_questions = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.now(), nullable=False)
    status = Column(String, nullable=False, index=True)


class JobMandateApplicants(Base):
    __tablename__ = "job_mandate_applicants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_mandate_id = Column(Integer, nullable=False, index=True)
    recruiter_id = Column(BigInteger, nullable=False)
    applicant_id = Column(BigInteger, nullable=False, index=True)
    status = Column(String, nullable=False)
    rank = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.now(), nullable=False)
    updated_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index(
            "ix_job_mandate_applicants_applicant_id_status", "applicant_id", "status"
        ),
        UniqueConstraint(
            "job_mandate_id",
            "recruiter_id",
            "applicant_id",
            name="job_mandate_applicants_uk",
        ),
        ForeignKeyConstraint(
            ["job_mandate_id"],
            ["job_mandates.job_id"],
            name="fk_job_mandate_applicants_to_job_mandates",
        ),
        ForeignKeyConstraint(
            ["recruiter_id", "applicant_id"],
            ["configs.recruiter_id", "configs.applicant_id"],
            name="fk_job_mandate_applicants_to_configs",
        ),
    )


class JobMandateQuestions(Base):
    __tablename__ = "job_mandate_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_mandate_id = Column(Integer, nullable=False)
    recruiter_id = Column(BigInteger, nullable=False)
    applicant_id = Column(BigInteger, nullable=False)
    question_id = Column(String, nullable=False)
    question_type = Column(String, nullable=False)
    question_details = Column(JSONB, nullable=False)
    applicant_response = Column(String, nullable=False)
    status = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.now(), nullable=False)
    updated_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "job_mandate_id",
            "recruiter_id",
            "applicant_id",
            "question_id",
            name="job_mandate_questions_uk",
        ),
        ForeignKeyConstraint(
            ["job_mandate_id", "recruiter_id", "applicant_id"],
            [
                "job_mandate_applicants.job_mandate_id",
                "job_mandate_applicants.recruiter_id",
                "job_mandate_applicants.applicant_id",
            ],
            name="fk_job_mandate_questions_to_job_mandate_applicants",
        ),
    )
