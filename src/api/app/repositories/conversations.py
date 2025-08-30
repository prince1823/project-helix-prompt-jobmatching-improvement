from typing import List
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logger import logger

from app.models.conversations import Model, Conversation, Annotation

from app.schemas.schemas import ConversationsTable as Table


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

    def update_annotations(
        self, recruiter_id: int, applicant_id: int, annotation: Annotation
    ) -> Table:
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
            annotations = model.annotations if model.annotations else []
            annotations.append(annotation)
            update = (
                self.db.query(self.table)
                .filter(
                    self.table.recruiter_id == recruiter_id,
                    self.table.applicant_id == applicant_id,
                )
                .update(
                    {
                        self.table.annotations: annotations,
                        self.table.updated_at: datetime.now(),
                    }
                )
            )
            self.db.commit()
            if update == 1:
                logger.info(
                    f"[update_annotations] Update annotations for applicant {applicant_id} by recruiter {recruiter_id}: {update}"
                )
                table = (
                    self.db.query(self.table)
                    .filter(
                        self.table.recruiter_id == recruiter_id,
                        self.table.applicant_id == applicant_id,
                    )
                    .first()
                )
        return table

    def update_conversations(
        self, recruiter_id: int, applicant_id: int, conversation: Conversation
    ) -> Table:
        table = (
            self.db.query(self.table)
            .filter(
                self.table.recruiter_id == recruiter_id,
                self.table.applicant_id == applicant_id,
            )
            .first()
        )
        conversations = []
        if table:
            model = Model.model_validate(table)
            conversations = model.conversations if model.conversations else []
        conversations.append(conversation)
        conversations = [conv.model_dump(exclude_none=True) for conv in conversations]
        update = (
            self.db.query(self.table)
            .filter(
                self.table.recruiter_id == recruiter_id,
                self.table.applicant_id == applicant_id,
            )
            .update(
                {
                    self.table.conversations: conversations,
                    self.table.updated_at: datetime.now(),
                }
            )
        )
        self.db.commit()
        logger.info(
            f"[update_conversations] Update conversations for applicant {applicant_id} by recruiter {recruiter_id}: {update}"
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
                f"[update_conversations] Conversations updated for applicant {applicant_id} by recruiter {recruiter_id}: {table.__dict__}"
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
