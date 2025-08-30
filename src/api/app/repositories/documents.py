from typing import List
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logger import logger

from app.models.documents import Model

from app.schemas.schemas import DocumentsTable as Table


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

    def update_document(
        self, recruiter_id: int, applicant_id: int, file_path: List[str]
    ) -> Table:
        table = (
            self.db.query(self.table)
            .filter(
                self.table.recruiter_id == recruiter_id,
                self.table.applicant_id == applicant_id,
            )
            .first()
        )
        logger.info(
            f"Updating document for recruiter {recruiter_id} and applicant {applicant_id}: {table.__dict__}"
        )
        if table:
            model = Model.model_validate(table)
            file_paths = model.file_paths if model.file_paths else []
            file_paths += file_path
            update = (
                self.db.query(self.table)
                .filter(
                    self.table.recruiter_id == recruiter_id,
                    self.table.applicant_id == applicant_id,
                )
                .update(
                    {
                        self.table.file_paths: file_paths,
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
        logger.info(
            f"Document updated: {table.__dict__ if table else 'No document found'}"
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
