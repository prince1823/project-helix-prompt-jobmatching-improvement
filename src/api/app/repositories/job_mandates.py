from typing import List

from sqlalchemy.orm import Session

from app.models.job_mandates import Status, Model

from app.schemas.schemas import JobMandates as Table


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

    def get_by_job_id(self, job_id: int) -> Table:
        return self.db.query(self.table).filter(self.table.job_id == job_id).first()

    def get_by_status(self, status: Status) -> List[Table]:
        return self.db.query(self.table).filter(self.table.status == status).all()

    def close(self):
        self.db.close()
