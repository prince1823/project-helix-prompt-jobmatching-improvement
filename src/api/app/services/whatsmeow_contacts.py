from typing import List

from fastapi import HTTPException, status as http_status

from app.repositories.whatsmeow_contacts import Repository

from app.models.user_login import UserDetails
from app.models.whatsmeow_contacts import Model


class Service:
    def __init__(self, repo: Repository):
        self.repo = repo

    def get_contacts(self, user_details: UserDetails) -> List[Model]:
        tables = self.repo.get_contacts(user_details.id)
        if not tables:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail="No contacts found"
            )
        data = [Model.model_validate(table) for table in tables]
        return data
