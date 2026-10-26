from alembic import context

from app.collection_models import Collection  # noqa: F401 -- register collection metadata
from app.database import Base, database_url, get_engine
from app.membership_models import Member  # noqa: F401 -- register membership metadata
from app.models import User  # noqa: F401 -- register model metadata
from app.public_models import Branch  # noqa: F401 -- register public metadata

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
