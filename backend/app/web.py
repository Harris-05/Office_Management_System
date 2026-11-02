"""Serve the built SPA without turning API or missing asset requests into HTML."""

from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

PUBLIC_PATHS = {"", "about", "programs", "branches", "events", "get-involved", "contact"}
STAFF_PATHS = {"staff", "staff/branches", "staff/applications", "staff/members", "staff/collections",
    "staff/transfers", "staff/reports", "staff/dashboard", "staff/content"}


def install_frontend(app, directory: Path):
    directory = directory.resolve()
    index = directory / "index.html"
    if not index.is_file():
        return
    if (directory / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=directory / "assets"), name="frontend-assets")

    @app.get("/{page:path}", include_in_schema=False)
    def frontend(page: str):
        if page.strip("/") not in PUBLIC_PATHS | STAFF_PATHS:
            raise HTTPException(404, "Page not found.")
        return FileResponse(index, media_type="text/html")
