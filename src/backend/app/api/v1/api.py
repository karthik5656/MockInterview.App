from fastapi import APIRouter
from app.api.v1.endpoints import sessions

api_router = APIRouter()

api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
# api_router.include_router(answers.router, prefix="", tags=["answers"])
# api_router.include_router(results.router, prefix="/sessions", tags=["results"])