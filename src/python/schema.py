from datetime import datetime

from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (
    create_engine,
    BigInteger,
    Boolean,
    Column,
    Integer,
    JSON,
    String,
    Text,
    PrimaryKeyConstraint,
)

from configs import config

Base = declarative_base()
DontCreateDB = declarative_base()


class ApplicantTable(Base):
    __tablename__ = "applicants"

    applicant_id = Column(BigInteger, nullable=False, index=True)
    recruiter_id = Column(BigInteger, nullable=False, index=True)
    locale = Column(String, nullable=True)
    user_workflow_status = Column(
        String, nullable=False, default="NOT_INITIATED"
    )  # Enum or String
    name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    city = Column(String, nullable=True)
    postal_code = Column(Integer, nullable=True)
    languages = Column(JSON, nullable=True)
    highest_education_qualification = Column(String, nullable=True)
    years_experience = Column(Integer, nullable=True)
    work_preferences = Column(String, nullable=True)
    currently_employed = Column(Boolean, nullable=True)
    notice_period = Column(Integer, nullable=True)
    has_2_wheeler = Column(Boolean, nullable=True)
    monthly_salary_expectation = Column(Integer, nullable=True)
    created_at = Column(String)
    updated_at = Column(String, nullable=True)
    response = Column(String, nullable=True)

    __table_args__ = (
        # Defining composite primary key
        (PrimaryKeyConstraint("recruiter_id", "applicant_id", name="applicants_pk")),
    )


class DocumentsTable(Base):
    __tablename__ = "documents"

    applicant_id = Column(BigInteger, primary_key=True, index=True)
    recruiter_id = Column(BigInteger, nullable=False, index=True)
    file_paths = Column(JSON, nullable=False)
    updated_at = Column(String, nullable=False)


class RecruiterTable(Base):
    __tablename__ = "recruiters"

    recruiter_id = Column(BigInteger, nullable=False, index=True)
    applicant_id = Column(BigInteger, nullable=False, index=True)
    is_blocked = Column(Boolean, default=False, nullable=False)
    message_count = Column(
        Integer, default=0, nullable=False
    )  # total messages based on particular chat
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=True)
    additional_config = Column(JSON, nullable=True)
    updated_by = Column(String, nullable=True)
    __table_args__ = (
        # Defining composite primary key
        (PrimaryKeyConstraint("recruiter_id", "applicant_id", name="recruiters_pk")),
    )


class ConversationsTable(Base):
    __tablename__ = "conversations"
    recruiter_id = Column(BigInteger, nullable=False, index=True)
    applicant_id = Column(BigInteger, nullable=False, index=True)
    conversations = Column(JSONB, nullable=False)
    annotations = Column(JSONB, nullable=True)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    __table_args__ = (
        # Defining composite primary key
        (PrimaryKeyConstraint("recruiter_id", "applicant_id", name="conversations_pk")),
    )


class UserLogin(Base):
    __tablename__ = "user_login"

    username = Column(String, primary_key=True)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # e.g., 'admin', 'annotator', 'viewer'
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=True)


class WhatsmeowContact(DontCreateDB):
    __tablename__ = "whatsmeow_contacts"
    __table_args__ = (PrimaryKeyConstraint("our_jid", "their_jid"),)
    our_jid = Column(Text, nullable=False)
    their_jid = Column(Text, nullable=False)
    first_name = Column(Text, nullable=True)
    full_name = Column(Text, nullable=True)
    push_name = Column(Text, nullable=True)
    business_name = Column(Text, nullable=True)


DATABASE_URL = f"postgresql+psycopg://{config['postgres']['user']}:{config['postgres']['password']}@{config['postgres']['host']}:{config['postgres']['port']}/{config['postgres']['database']}?sslmode=disable"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()


# Create the database tables if they don't exist
def init_db():
    Base.metadata.create_all(bind=engine)
    session = get_db()
    for recruiter in config["whatsapp"]:
        for number in recruiter["blocked_numbers"]:
            existing_record = (
                session.query(RecruiterTable)
                .filter_by(
                    recruiter_id=int(recruiter["recruiter_id"]),
                    applicant_id=int(number),
                )
                .first()
            )
            if existing_record is None:
                try:
                    user = RecruiterTable(
                        recruiter_id=int(recruiter["recruiter_id"]),
                        applicant_id=int(number),
                        is_blocked=True,
                        created_at=datetime.now().isoformat(),
                    )
                    session.add(user)
                    session.commit()
                except Exception as e:
                    session.rollback()
    session.close()
