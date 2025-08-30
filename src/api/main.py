from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.db.postgres import init_db
from app.api.v1 import main_router as router

app = FastAPI()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(router)
