from typing import List
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.user_login import Model

from app.schemas.schemas import UserLoginTable as Table


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

    def get_all(self, id: str, admin: bool = False) -> List[Table]:
        if admin:
            return self.db.query(self.table).all()
        else:
            return self.db.query(self.table).filter(self.table.username == id).all()

    def get_by_username(self, username: str) -> Table | None:
        return self.db.query(self.table).filter(self.table.username == username).first()

    def update(self, username: str, password_hash: str, role: str) -> Table:
        update = (
            self.db.query(self.table)
            .filter(self.table.username == username)
            .update(
                {
                    self.table.password: password_hash,
                    self.table.role: role,
                    self.table.updated_at: datetime.now(),
                }
            )
        )
        self.db.commit()
        if update == 1:
            table = (
                self.db.query(self.table)
                .filter(self.table.username == username)
                .first()
            )
        return table

    def close(self):
        self.db.close()
