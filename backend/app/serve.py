"""Container entry point with Render's assigned PORT; no shell interpolation."""

import os


def main():
    port = int(os.environ.get("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between1and65535.")
    os.execvp("uvicorn", ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(port)])


if __name__ == "__main__":
    main()
