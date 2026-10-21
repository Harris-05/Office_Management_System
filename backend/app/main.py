from fastapi import FastAPI

app = FastAPI(title="Branch-to-Head-Office Management Platform")


@app.get("/health")
def health() -> dict[str, str]:
    """Process liveness only; database readiness is not checked yet."""
    return {"status": "ok"}
