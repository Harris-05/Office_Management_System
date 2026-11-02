"""Readiness checks the code's migration head, not merely database connectivity."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


def require_current_schema(connection):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    required = set(ScriptDirectory.from_config(config).get_heads())
    actual = set(connection.scalars(text("SELECT version_num FROM alembic_version")))
    if actual != required:
        raise SQLAlchemyError("Schema is not current.")
