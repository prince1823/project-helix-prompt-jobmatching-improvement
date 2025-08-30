from typing import List
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.job_mandate_questions import Model, QuestionType

from app.schemas.schemas import JobMandateQuestions as Table


class Repository:
    def __init__(self, db: Session):
        self.db = db
        self.table = Table
        self.model = Model

    def create(self, model: Model) -> Table:
        table = self.table(**model.model_dump())
        self.db.add(table)
        self.db.commit()
        self.db.refresh(table)
        return table

    def get(self, id: int) -> Table:
        return self.db.query(self.table).filter(self.table.id == id).first()

    def get_all(self) -> List[Table]:
        return self.db.query(self.table).all()

    def get_by_id(
        self, recruiter_id: int, applicant_id: int, job_id: int, question_id: str
    ) -> Table:
        return (
            self.db.query(self.table)
            .filter(
                self.table.recruiter_id == recruiter_id,
                self.table.applicant_id == applicant_id,
                self.table.job_mandate_id == job_id,
                self.table.question_id == question_id,
            )
            .first()
        )

    def get_by_question_type(
        self, job_mandate_id: int, applicant_id: int, question_type: QuestionType
    ) -> List[Table]:
        return (
            self.db.query(self.table)
            .filter(
                self.table.job_mandate_id == job_mandate_id,
                self.table.applicant_id == applicant_id,
                self.table.question_type == question_type,
            )
            .all()
        )

    def get_by_id_status_type(
        self, applicant_id: int, job_id: int, status: bool, question_type: QuestionType
    ) -> Table:
        return (
            self.db.query(self.table)
            .filter(
                self.table.applicant_id == applicant_id,
                self.table.job_mandate_id == job_id,
                self.table.status == status,
                self.table.question_type == question_type,
            )
            .first()
        )

    def update_status(
        self,
        job_mandate_id: int,
        applicant_id: int,
        question_id: str,
        status: bool,
        applicant_response: str,
    ) -> int:
        updated = (
            self.db.query(self.table)
            .filter(
                self.table.job_mandate_id == job_mandate_id,
                self.table.applicant_id == applicant_id,
                self.table.question_id == question_id,
            )
            .update(
                {
                    self.table.status: status,
                    self.table.applicant_response: applicant_response,
                    self.table.updated_at: datetime.now(),
                }
            )
        )
        self.db.commit()
        return updated

    def close(self):
        if self.db:
            self.db.close()

    def delete(self, recruiter_id: int, applicant_id: int) -> None:
        self.db.query(self.table).filter(
            self.table.recruiter_id == recruiter_id,
            self.table.applicant_id == applicant_id,
        ).delete()
        self.db.commit()
