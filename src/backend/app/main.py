from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db, engine
from app.core.logging import setup_logging
from app.api.v1.api import api_router
from app.api.errors import (
    AppException,
    app_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield
    # Dispose connection pool cleanly on shutdown
    await engine.dispose()


app = FastAPI(
    title="Mock Interview API",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Centralized error handlers
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Include API v1 router
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["system"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Verifies API liveness and database connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
    }