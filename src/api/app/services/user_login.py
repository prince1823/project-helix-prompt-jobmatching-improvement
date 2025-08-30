import hashlib
from typing import List
from datetime import datetime

from fastapi import HTTPException

from app.repositories.user_login import Repository

from app.models.user_login import Model, Role, UserDetails, Request, Response


class Service:
    def __init__(self, repo: Repository):
        self.repo = repo

    def create(self, user_details: UserDetails, body: Request) -> Response:
        model = Model(
            username=str(user_details.id),
            password=body.request.password,
            role=Role[body.request.role],
        )  # type: ignore
        db_user = self.repo.create(model)
        return Response(
            data=[Model.model_validate(db_user)],
            mid=body.mid,
            ts=datetime.now(),
        )

    def get_all(self, user_details: UserDetails) -> List[Model]:
        if user_details.role == "ADMIN":
            users = self.repo.get_all(str(user_details.id), admin=True)
        else:
            users = self.repo.get_all(str(user_details.id))
        if not users:
            raise HTTPException(status_code=404, detail="No users found")
        return [Model.model_validate(user) for user in users]

    def get_user_details(self, user_id: str) -> UserDetails:
        """
        Fetch user details based on user_id.
        """
        users = self.repo.get_all(user_id)
        if not users:
            raise HTTPException(status_code=404, detail="User not found")
        user = Model.model_validate(users[0])
        return UserDetails(id=int(user.username), role=user.role)

    def create_user(self, body: Request) -> Model:
        username = body.request.username
        password = body.request.password
        role = body.request.role
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        existing_user = self.repo.get_by_username(username)
        if existing_user:
            table = self.repo.update(username, password_hash, role)
        else:
            model = Model(
                username=username,
                password=password_hash,
                role=Role[role],
            )  # type: ignore
            table = self.repo.create(model)
        return Model.model_validate(table)
