import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings, setup_logging
from app.db.session import engine
from app.limiter import limiter
from app.routers import auth, bookings, centres, payments

setup_logging()
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="EVE Healthcare — Diagnostic Booking API",
        description=(
            "Book diagnostic tests at centres near you. "
            "Includes auth, booking management, and simulated payment processing."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(centres.router, prefix="/centres", tags=["centres"])
    app.include_router(bookings.router, prefix="/bookings", tags=["bookings"])
    app.include_router(payments.router, prefix="/payments", tags=["payments"])

    @app.get("/health", tags=["meta"])
    async def health():
        return {"status": "ok"}

    @app.on_event("startup")
    async def startup():
        logger.info("app started", extra={"env": settings.APP_ENV})

    @app.on_event("shutdown")
    async def shutdown():
        await engine.dispose()
        logger.info("app shutdown")

    return app


app = create_app()
