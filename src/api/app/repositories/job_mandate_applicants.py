from typing import List
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.job_mandate_applicants import Model, Status

from app.schemas.schemas import JobMandateApplicants as Table


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

    def get_by_id(self, job_id: int, applicant_id: int, recruiter_id: int) -> Table:
        return (
            self.db.query(self.table)
            .filter(
                self.table.job_mandate_id == job_id,
                self.table.applicant_id == applicant_id,
                self.table.recruiter_id == recruiter_id,
            )
            .first()
        )

    def get_by_applicant_id(self, applicant_id: int, recruiter_id: int) -> List[Table]:
        return (
            self.db.query(self.table)
            .filter(
                self.table.applicant_id == applicant_id,
                self.table.recruiter_id == recruiter_id,
            )
            .all()
        )

    def get_by_applicant_id_and_status_ordered(
        self, applicant_id: int, status: Status
    ) -> Table:
        return (
            self.db.query(self.table)
            .filter(
                self.table.applicant_id == applicant_id,
                self.table.status == status,
            )
            .order_by(self.table.rank.asc())
            .first()
        )

    def update(self, id: int, data: dict) -> int:
        result = (
            self.db.query(self.table)
            .filter(self.table.id == id)
            .update({**data, "updated_at": datetime.now()})
        )
        self.db.commit()
        return result

    def update_status(self, applicant_id: int, job_mandate_id: int, status: str) -> int:
        result = (
            self.db.query(self.table)
            .filter(
                self.table.applicant_id == applicant_id,
                self.table.job_mandate_id == job_mandate_id,
            )
            .update({self.table.status: status, self.table.updated_at: datetime.now()})
        )
        self.db.commit()
        return result

    def close(self):
        self.db.close()

    def delete(self, recruiter_id: int, applicant_id: int) -> None:
        self.db.query(self.table).filter(
            self.table.recruiter_id == recruiter_id,
            self.table.applicant_id == applicant_id,
        ).delete()
        self.db.commit()
