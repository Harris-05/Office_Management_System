from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import get_settings
from app.database import get_engine
from app.dependencies import Principal, require_api_access
from app.login import router as login_router
from app.middleware import SecurityMiddleware
from app.public import router as public_router
from app.rate_limits import get_redis
from app.staff import router as staff_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()
    try:
        yield
    finally:
        engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Branch Office",
        dependencies=[Depends(require_api_access)],
        lifespan=lifespan,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None if settings.environment == "production" else "/redoc",
        openapi_url=None if settings.environment == "production" else "/openapi.json",
    )

    # Application-level guard also protects future routers unless explicitly public.
    def api_guard(request: Request, principal: Annotated[Principal, Depends(require_api_access)]):
        return principal

    # Only API routes have this guard; health endpoints stay independent.
    from fastapi import APIRouter

    api = APIRouter(dependencies=[Depends(api_guard)])
    api.include_router(login_router)
    api.include_router(staff_router)
    api.include_router(public_router)
    app.include_router(api)
    app.add_middleware(SecurityMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
        expose_headers=["Retry-After"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            {"detail": "Invalid request. Check the required fields and formats."}, status_code=422
        )

    @app.exception_handler(SQLAlchemyError)
    @app.exception_handler(RedisError)
    async def unavailable(request: Request, exc: Exception):
        return JSONResponse({"detail": "Service temporarily unavailable."}, status_code=503)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/health/ready")
    def readiness():
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1 FROM users LIMIT 1"))
            connection.execute(text("SELECT 1 FROM auth_sessions LIMIT 1"))
        get_redis().ping()
        return {"status": "ready"}

    return app


app = create_app()
