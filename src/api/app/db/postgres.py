import json
from pathlib import Path
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.core.config import config
from app.models.user_login import Role

from app.schemas.schemas import ConfigsTable, UserLoginTable, JobMandates

DATABASE_URL = f"postgresql+psycopg://{config['postgres']['user']}:{config['postgres']['password']}@{config['postgres']['host']}:{config['postgres']['port']}/{config['postgres']['database']}?sslmode=disable"
engine = create_engine(
    DATABASE_URL,
    pool_size=config["postgres"]["pool_size"],
    max_overflow=config["postgres"]["max_overflow"],
    pool_timeout=config["postgres"]["pool_timeout"],
    pool_recycle=config["postgres"]["pool_recycle"],
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()


def create_configs():
    session = get_db()
    for recruiter in config["whatsapp"]:
        for number in recruiter["blocked_numbers"]:
            existing_record = (
                session.query(ConfigsTable)
                .filter_by(
                    recruiter_id=int(recruiter["recruiter_id"]),
                    applicant_id=int(number),
                )
                .first()
            )
            if existing_record is None:
                try:
                    user = ConfigsTable(
                        recruiter_id=int(recruiter["recruiter_id"]),
                        applicant_id=int(number),
                        enabled=False,
                        created_at=datetime.now(),
                    )
                    session.add(user)
                    session.commit()
                except Exception as e:
                    session.rollback()
    session.close()


def create_users():
    session = get_db()
    for recruiter in config["whatsapp"]:
        user = (
            session.query(UserLoginTable)
            .filter_by(username=str(recruiter["recruiter_id"]))
            .first()
        )
        if not user:
            user = UserLoginTable(
                username=str(recruiter["recruiter_id"]),
                password=recruiter["recruiter_password"],
                role=Role.RECRUITER,
            )
            session.add(user)
            session.commit()
    session.close()


def create_jobs():
    session = get_db()
    data_dir = Path(config["job_mandates_path"])
    for item in data_dir.glob("*.json"):
        with open(item) as f:
            mandate = json.load(f)
            exists = (
                session.query(JobMandates)
                .filter(JobMandates.job_id == mandate["job_id"])
                .first()
            )
            if exists:
                continue
            table = JobMandates(**mandate)
            session.add(table)
            session.commit()
    session.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    create_configs()
    create_users()
    create_jobs()
