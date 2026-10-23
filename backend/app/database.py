from collections.abc import Iterator
from functools import lru_cache

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    # Render may supply postgresql://; use psycopg 3 for either spelling.
    url = make_url(str(get_settings().database_url))
    return url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)


@lru_cache
def get_engine() -> Engine:
    return create_engine(
        database_url(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=5,
        connect_args={"connect_timeout": 5},
    )


def get_db(request: Request) -> Iterator[Session | None]:
    if not (request.url.path == "/api" or request.url.path.startswith("/api/")):
        yield None
        return
    # Closing the request's session rolls back uncommitted transactions.
    with Session(get_engine()) as session:
        yield session
