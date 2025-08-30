from typing import List
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.whatsmeow_contacts import Model
from app.schemas.schemas import WhatsmeowContactsTable as Table


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
            query = query.filter(self.table.our_jid == id)
        return query.all()

    def get(self, id: int) -> Table:
        return self.db.query(self.table).filter(self.table.id == id).first()

    def get_by_recruiter_and_applicant(
        self, recruiter_id: int, applicant_id: int
    ) -> Table:
        return (
            self.db.query(self.table)
            .filter(
                self.table.our_jid == recruiter_id,
                self.table.their_jid == applicant_id,
            )
            .first()
        )

    def get_contacts(self, recruiter_id: int) -> List[Table]:
        return (
            self.db.query(self.table)
            .filter(
                self.table.our_jid.like(f"%{recruiter_id}%"),
                self.table.full_name != None,
            )
            .all()
        )

    def close(self):
        self.db.close()
