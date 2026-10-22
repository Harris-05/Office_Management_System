import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

import app.main as main_module
from app.database import get_db
from app.main import app
from app.seed import seed_demo_users


@pytest.fixture(scope="session")
def engine():
    test_url = os.environ.get("TEST_DATABASE_URL")
    if not test_url:
        raise pytest.UsageError(
            "Set TEST_DATABASE_URL to a dedicated PostgreSQL database ending _test."
        )
    url = make_url(test_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
        raise pytest.UsageError("Tests require a dedicated PostgreSQL database ending _test.")
    engine = create_engine(
        url.set(drivername="postgresql+psycopg"),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        command.check(config)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine):
    # Each test gets a transaction; even service-level commits stay inside a savepoint.
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()


@pytest.fixture(autouse=True)
def database_overrides(db_session, engine, monkeypatch):
    seed_demo_users(db_session)

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(main_module, "get_engine", lambda: engine)
    yield
    app.dependency_overrides.clear()
