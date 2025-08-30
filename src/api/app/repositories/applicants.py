from typing import List
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logger import logger

from app.models.llm import ApplicantDetails
from app.models.applicants import Model, Status

from app.schemas.schemas import ApplicantsTable as Table


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

    def get_all(self, id: int, admin: bool = False) -> List[Table]:
        query = self.db.query(self.table)
        if not admin:
            query = query.filter(self.table.recruiter_id == id)
        return query.all()

    def get(self, id: int) -> Table:
        return self.db.query(self.table).filter(self.table.id == id).first()

    def get_by_recruiter_and_applicant(
        self, recruiter_id: int, applicant_id: int
    ) -> Table:
        return (
            self.db.query(self.table)
            .filter(
                self.table.recruiter_id == recruiter_id,
                self.table.applicant_id == applicant_id,
            )
            .first()
        )

    def get_by_recruiter_and_applicants(
        self, recruiter_id: int, applicant_ids: List[int]
    ) -> List[Table]:
        return (
            self.db.query(self.table)
            .filter(
                self.table.recruiter_id == recruiter_id,
                self.table.applicant_id.in_(applicant_ids),
            )
            .all()
        )

    def get_by_status(
        self, id: int, status: Status, admin: bool = False
    ) -> List[Table]:
        query = self.db.query(self.table).filter(self.table.status == status)
        if not admin:
            query = query.filter(self.table.recruiter_id == id)
        return query.all()

    def get_applicant_by_recruiter_and_not_status(
        self, recruiter_id: int, applicant_id: int, status: Status
    ) -> Table:
        return (
            self.db.query(self.table)
            .filter(
                self.table.recruiter_id == recruiter_id,
                self.table.applicant_id == applicant_id,
                self.table.status != status,
            )
            .first()
        )

    def get_applicant_by_not_status(self, applicant_id: int, status: Status) -> Table:
        return (
            self.db.query(self.table)
            .filter(
                self.table.applicant_id == applicant_id,
                self.table.status != status,
            )
            .first()
        )

    def update_status(
        self, recruiter_id: int, applicant_id: int, status: Status
    ) -> Table:
        update = (
            self.db.query(self.table)
            .filter(
                self.table.recruiter_id == recruiter_id,
                self.table.applicant_id == applicant_id,
            )
            .update({self.table.status: status, self.table.updated_at: datetime.now()})
        )
        self.db.commit()
        logger.info(
            f"[update_status] Update status for applicant {applicant_id} by recruiter {recruiter_id}: {update}"
        )
        if update == 1:
            table = (
                self.db.query(self.table)
                .filter(
                    self.table.recruiter_id == recruiter_id,
                    self.table.applicant_id == applicant_id,
                )
                .first()
            )
            logger.info(
                f"[update_status] Status updated to {status} for applicant {applicant_id} by recruiter {recruiter_id}: {table.__dict__}"
            )
        return table

    def update_details(
        self, recruiter_id: int, applicant_id: int, details: ApplicantDetails
    ) -> Table:
        update = (
            self.db.query(self.table)
            .filter(
                self.table.recruiter_id == recruiter_id,
                self.table.applicant_id == applicant_id,
            )
            .update(
                {
                    self.table.details: details.model_dump(exclude_none=True),
                    self.table.updated_at: datetime.now(),
                }
            )
        )
        self.db.commit()
        if update == 1:
            table = (
                self.db.query(self.table)
                .filter(
                    self.table.recruiter_id == recruiter_id,
                    self.table.applicant_id == applicant_id,
                )
                .first()
            )
        return table

    def update_response(
        self, recruiter_id: int, applicant_id: int, response: str
    ) -> Table:
        update = (
            self.db.query(self.table)
            .filter(
                self.table.recruiter_id == recruiter_id,
                self.table.applicant_id == applicant_id,
            )
            .update(
                {self.table.response: response, self.table.updated_at: datetime.now()}
            )
        )
        self.db.commit()
        logger.info(
            f"[update_response] Update response for applicant {applicant_id} by recruiter {recruiter_id}: {update}"
        )
        table = (
            self.db.query(self.table)
            .filter(
                self.table.recruiter_id == recruiter_id,
                self.table.applicant_id == applicant_id,
            )
            .first()
        )
        logger.info(
            f"[update_response] Response updated to {response} for applicant {applicant_id} by recruiter {recruiter_id}: {table.__dict__}"
        )
        return table

    def update_tags(
        self, recruiter_id: int, applicant_id: int, tags: List[str]
    ) -> Table:
        update = (
            self.db.query(self.table)
            .filter(
                self.table.recruiter_id == recruiter_id,
                self.table.applicant_id == applicant_id,
            )
            .update({self.table.tags: tags, self.table.updated_at: datetime.now()})
        )
        self.db.commit()
        logger.info(
            f"[update_tags] Update tags for applicant {applicant_id} by recruiter {recruiter_id}: {update}"
        )
        table = (
            self.db.query(self.table)
            .filter(
                self.table.recruiter_id == recruiter_id,
                self.table.applicant_id == applicant_id,
            )
            .first()
        )
        logger.info(
            f"[update_tags] Tags updated to {tags} for applicant {applicant_id} by recruiter {recruiter_id}: {table.__dict__}"
        )
        return table

    def update(self, recruiter_id: int, applicant_id: int, data: dict) -> Table:
        update = (
            self.db.query(self.table)
            .filter(
                self.table.recruiter_id == recruiter_id,
                self.table.applicant_id == applicant_id,
            )
            .update({**data, "updated_at": datetime.now()})
        )
        self.db.commit()
        if update == 1:
            table = (
                self.db.query(self.table)
                .filter(
                    self.table.recruiter_id == recruiter_id,
                    self.table.applicant_id == applicant_id,
                )
                .first()
            )
        return table

    def close(self):
        self.db.close()

    def delete(self, recruiter_id: int, applicant_id: int) -> None:
        self.db.query(self.table).filter(
            self.table.recruiter_id == recruiter_id,
            self.table.applicant_id == applicant_id,
        ).delete()
        self.db.commit()
