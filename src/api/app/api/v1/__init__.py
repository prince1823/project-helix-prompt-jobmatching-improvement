from app.api.v1.routers import router as main_router
from app.api.v1.list_actions import router as list_actions_router
from app.api.v1.recruiter_lists import router as recruiter_lists_router

main_router.include_router(recruiter_lists_router)
main_router.include_router(list_actions_router)
