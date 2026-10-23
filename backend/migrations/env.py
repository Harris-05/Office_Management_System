from alembic import context

from app.database import Base, database_url, get_engine
from app.models import User  # noqa: F401 -- register model metadata

target_metadata = Base.metadata


def run_online(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
elif context.config.attributes.get("connection") is not None:
    run_online(context.config.attributes["connection"])
else:
    with get_engine().connect() as connection:
        run_online(connection)
