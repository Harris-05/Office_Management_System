from fastapi import FastAPI

from app.login import router as login_router

app = FastAPI(title="Branch-to-Head-Office Management Platform")
app.include_router(login_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Process liveness only; database readiness is not checked yet."""
    return {"status": "ok"}
