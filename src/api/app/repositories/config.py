from typing import List
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logger import logger

from app.models.configs import Model
from app.models.utils import LanguageEnum

from app.schemas.schemas import ConfigsTable as Table


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

    def update_enabled(
        self, recruiter_id: int, applicant_id: int, enabled: bool, updated_by: str
    ) -> Table:
        update = (
            self.db.query(self.table)
            .filter(
                self.table.recruiter_id == recruiter_id,
                self.table.applicant_id == applicant_id,
            )
            .update(
                {
                    self.table.enabled: enabled,
                    self.table.updated_at: datetime.now(),
                    self.table.updated_by: updated_by,
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

    def update_locale(
        self, recruiter_id: int, applicant_id: int, locale: LanguageEnum
    ) -> Table:
        update = (
            self.db.query(self.table)
            .filter(
                self.table.recruiter_id == recruiter_id,
                self.table.applicant_id == applicant_id,
            )
            .update(
                {
                    self.table.locale: locale,
                    self.table.updated_at: datetime.now(),
                    self.table.updated_by: str(recruiter_id),
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

    def update_counter(self, recruiter_id: int, applicant_id: int) -> Table:
        table = (
            self.db.query(self.table)
            .filter(
                self.table.recruiter_id == recruiter_id,
                self.table.applicant_id == applicant_id,
            )
            .first()
        )
        if table:
            model = Model.model_validate(table)
            update = (
                self.db.query(self.table)
                .filter(
                    self.table.recruiter_id == recruiter_id,
                    self.table.applicant_id == applicant_id,
                )
                .update(
                    {
                        self.table.message_count: model.message_count + 1,
                        self.table.updated_at: datetime.now(),
                        self.table.updated_by: str(recruiter_id),
                    }
                )
            )
            self.db.commit()
            logger.info(
                f"[update_counter] Update message_count for applicant {applicant_id} by recruiter {recruiter_id}: {update}"
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
                    f"[update_counter] Message count updated to {table.__dict__} for applicant {applicant_id} by recruiter {recruiter_id}"
                )
        return table

    def reset_counts(self) -> int:
        update = (
            self.db.query(self.table)
            .filter(
                self.table.enabled == True,
            )
            .update(
                {
                    self.table.message_count: 0,
                    self.table.updated_at: datetime.now(),
                    self.table.updated_by: "SYSTEM",
                }
            )
        )
        self.db.commit()
        return update

    def close(self):
        self.db.close()

    def delete(self, recruiter_id: int, applicant_id: int) -> None:
        self.db.query(self.table).filter(
            self.table.recruiter_id == recruiter_id,
            self.table.applicant_id == applicant_id,
        ).delete()
        self.db.commit()
