import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

from app.api.routes import auth_router, internal_router
from app.core.config import settings
from app.core.email import email_enabled

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not email_enabled():
        logger.warning(
            "SMTP is not configured (SMTP_USER/SMTP_PASSWORD empty): password-recovery "
            "emails will only be logged, not delivered."
        )
    yield


app = FastAPI(
    title="ASR Platform - Auth Service",
    version=settings.version,
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(internal_router)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {"database": "healthy", "email": "smtp" if email_enabled() else "stub"},
    }
