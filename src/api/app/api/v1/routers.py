from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/")
def home():
    return {"result": "Recruiter Copilot API. Check the documentation at /docs"}


@router.get("/health")
def health_check():
    return {"status": "healthy"}
