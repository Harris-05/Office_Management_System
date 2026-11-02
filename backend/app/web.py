"""Serve the built SPA without turning API or missing asset requests into HTML."""

from pathlib import Path

from fastapi.responses import FileResponse
from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles

PUBLIC_PATHS = {"", "about", "programs", "branches", "events", "get-involved", "contact"}
STAFF_PATHS = {
    "staff",
    "staff/branches",
    "staff/applications",
    "staff/members",
    "staff/collections",
    "staff/transfers",
    "staff/reports",
    "staff/dashboard",
    "staff/content",
}


def install_frontend(app, directory: Path):
    directory = directory.resolve()
    index = directory / "index.html"
    if not index.is_file():
        return
    if (directory / "assets").is_dir():
        app.mount(
            "/assets",
            GZipMiddleware(StaticFiles(directory=directory / "assets"), minimum_size=500),
            name="frontend-assets",
        )
    if (directory / "fonts").is_dir():
        app.mount("/fonts", StaticFiles(directory=directory / "fonts"), name="frontend-fonts")

    def frontend():
        return FileResponse(index, media_type="text/html")

    # Explicit SPA routes preserve405for an existing API path with the wrong method.
    # A catch-all GET route would shadow the API's partial method match.
    for page in sorted(PUBLIC_PATHS | STAFF_PATHS):
        app.add_api_route("/" + page, frontend, methods=["GET"], include_in_schema=False)
