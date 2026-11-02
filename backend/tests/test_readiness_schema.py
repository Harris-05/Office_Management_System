import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.schema_health import require_current_schema


def test_readiness_rejects_behind_schema_without_changing_records(db_session):
    connection = db_session.connection()
    require_current_schema(connection)
    connection.execute(text("UPDATE alembic_version SET version_num='0001'"))
    with pytest.raises(SQLAlchemyError, match="Schema is not current"):
        require_current_schema(connection)
