from typing import List
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.list_actions import Model, Status, Actions
from app.schemas.schemas import ListActionsTable as Table, RecruiterListsTable


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
            query = query.join(
                RecruiterListsTable, RecruiterListsTable.id == self.table.list_id
            ).filter(RecruiterListsTable.recruiter_id == id)
        return query.all()

    def get(self, id: int) -> Table:
        return self.db.query(self.table).filter(self.table.id == id).first()

    def get_by_status(self, status: Status, admin: bool = False) -> List[Table]:
        query = self.db.query(self.table).filter(self.table.status == status)
        if not admin:
            query = query.join(
                RecruiterListsTable, RecruiterListsTable.id == self.table.list_id
            ).filter(RecruiterListsTable.recruiter_id == id)
        return query.all()

    def get_by_type(self, action_type: Actions, admin: bool = False) -> List[Table]:
        query = self.db.query(self.table).filter(self.table.action_type == action_type)
        if not admin:
            query = query.join(
                RecruiterListsTable, RecruiterListsTable.id == self.table.list_id
            ).filter(RecruiterListsTable.recruiter_id == id)
        return query.all()

    def get_by_list(self, id: int, admin: bool = False) -> List[Table]:
        query = self.db.query(self.table).filter(self.table.list_id == id)
        if not admin:
            query = query.join(
                RecruiterListsTable, RecruiterListsTable.id == self.table.list_id
            ).filter(RecruiterListsTable.recruiter_id == id)
        return query.all()

    def get_by_list_status(
        self, id: int, status: Status, admin: bool = False
    ) -> List[Table]:
        query = self.db.query(self.table).filter(
            self.table.list_id == id, self.table.status == status
        )
        if not admin:
            query = query.join(
                RecruiterListsTable, RecruiterListsTable.id == self.table.list_id
            ).filter(RecruiterListsTable.recruiter_id == id)
        return query.all()

    def get_by_list_type(
        self, id: int, action_type: Actions, admin: bool = False
    ) -> List[Table]:
        query = self.db.query(self.table).filter(
            self.table.list_id == id, self.table.action_type == action_type
        )
        if not admin:
            query = query.join(
                RecruiterListsTable, RecruiterListsTable.id == self.table.list_id
            ).filter(RecruiterListsTable.recruiter_id == id)
        return query.all()

    def get_by_list_status_type(
        self, id: int, status: Status, action_type: Actions, admin: bool = False
    ) -> List[Table]:
        query = self.db.query(self.table).filter(
            self.table.list_id == id,
            self.table.status == status,
            self.table.action_type == action_type,
        )
        if not admin:
            query = query.join(
                RecruiterListsTable, RecruiterListsTable.id == self.table.list_id
            ).filter(RecruiterListsTable.recruiter_id == id)
        return query.all()

    def update(self, id: int, status: Status) -> Table:
        table = self.db.query(self.table).filter(self.table.list_id == id).first()
        if table:
            model = Model.model_validate(table)
            update = (
                self.db.query(self.table)
                .filter(self.table.list_id == model.id)
                .update(
                    {self.table.status: status, self.table.updated_at: datetime.now()}
                )
            )
            self.db.commit()
            if update == 1:
                table = (
                    self.db.query(self.table).filter(self.table.list_id == id).first()
                )
        return table

    def update_by_id(self, id: int, status: Status) -> Table:
        table = self.db.query(self.table).filter(self.table.id == id).first()
        if table:
            model = Model.model_validate(table)
            update = (
                self.db.query(self.table)
                .filter(self.table.id == model.id)
                .update(
                    {self.table.status: status, self.table.updated_at: datetime.now()}
                )
            )
            self.db.commit()
            if update == 1:
                table = (
                    self.db.query(self.table).filter(self.table.list_id == id).first()
                )
        return table

    def close(self):
        self.db.close()
