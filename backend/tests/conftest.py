import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

os.environ.setdefault("ALLOWED_HOSTS", '["localhost","127.0.0.1","testserver"]')
os.environ.setdefault("ALLOWED_ORIGINS", '["http://testserver","http://localhost:5173"]')

import app.main as main_module
from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models import User
from app.passwords import hash_password
from app.seed import DEMO_ACCOUNTS


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


@pytest.fixture(scope="session")
def demo_hash():
    return hash_password("Demo123!")


@pytest.fixture(autouse=True)
def database_overrides(db_session, engine, monkeypatch, demo_hash):
    monkeypatch.setenv("RATE_NAMESPACE", f"test-{uuid.uuid4().hex}")
    monkeypatch.setenv("REDIS_URL", os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/2"))
    get_settings.cache_clear()
    # Reuse a real hash in fixtures; password-policy and seeding tests exercise real hashing.
    db_session.add_all(
        [
            User(email=email, name=name, role=role, password_hash=demo_hash)
            for email, name, role in DEMO_ACCOUNTS
        ]
    )
    db_session.flush()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(main_module, "get_engine", lambda: engine)
    yield
    app.dependency_overrides.clear()
    from app.rate_limits import get_redis

    client = get_redis()
    for key in client.scan_iter(match=f"{get_settings().rate_namespace}:*"):
        client.delete(key)
    get_settings.cache_clear()
