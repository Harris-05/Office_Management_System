from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_engine
from app.login import router as login_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()  # Validate configuration; migrations run separately.
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title="Branch-to-Head-Office Management Platform", lifespan=lifespan)
app.include_router(login_router)


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    # Never expose SQL parameters, connection URLs or driver errors in API responses.
    return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable."})


@app.get("/health")
def health() -> dict[str, str]:
    """Process liveness; database readiness has its own endpoint."""
    return {"status": "ok"}


@app.get("/health/ready")
def readiness() -> dict[str, str]:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1 FROM users LIMIT 1"))
    return {"status": "ready"}
