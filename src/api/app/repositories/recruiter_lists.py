from typing import List
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.recruiter_lists import Model, Status
from app.schemas.schemas import RecruiterListsTable as Table


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
        if admin:
            return self.db.query(self.table).all()
        else:
            return self.db.query(self.table).filter(self.table.recruiter_id == id).all()

    def get(self, id: int) -> Table:
        return self.db.query(self.table).filter(self.table.id == id).first()

    def get_by_name(self, id: int, name: str) -> Table:
        return (
            self.db.query(self.table)
            .filter(self.table.recruiter_id == id, self.table.list_name == name)
            .first()
        )

    def get_by_status(
        self, id: int, status: Status, admin: bool = False
    ) -> List[Table]:
        if admin:
            return self.db.query(self.table).filter(self.table.status == status).all()
        else:
            return (
                self.db.query(self.table)
                .filter(self.table.recruiter_id == id, self.table.status == status)
                .all()
            )

    def update(self, id: int, applicants: List[int]) -> Table:
        table = self.get(id)
        setattr(table, "applicants", applicants)
        setattr(table, "updated_at", datetime.now())
        self.db.commit()
        self.db.refresh(table)
        return table

    def close(self):
        self.db.close()
