from typing import List
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.action_details import Model, Status
from app.schemas.schemas import ActionDetailsTable as Table


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
            return self.db.query(self.table).filter(self.table.action_id == id).all()

    def get(self, id: int) -> Table:
        return self.db.query(self.table).filter(self.table.id == id).first()

    def update(self, id: int, status: Status) -> Table:
        table = self.get(id=id)
        setattr(table, "status", status)
        setattr(table, "updated_at", datetime.now().isoformat())
        self.db.commit()
        self.db.refresh(table)
        return table

    def get_by_action_id(self, action_id: int) -> List[Table]:
        return self.db.query(self.table).filter(self.table.action_id == action_id).all()

    def get_by_action_id_applicant_id(self, action_id: int, applicant_id: int) -> Table:
        return (
            self.db.query(self.table)
            .filter(
                self.table.action_id == action_id,
                self.table.applicant_id == applicant_id,
            )
            .first()
        )

    def update_by_action_id(
        self, action_id: int, applicant_id: int, status: Status
    ) -> Table:
        table = self.get_by_action_id_applicant_id(action_id, applicant_id)
        setattr(table, "status", status)
        setattr(table, "updated_at", datetime.now().isoformat())
        self.db.commit()
        self.db.refresh(table)
        return table

    def close(self):
        self.db.close()
