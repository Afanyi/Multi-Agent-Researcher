from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

from app.config import settings
from app.db import Base, wait_for_database
import app.models  # noqa: F401


def make_config() -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def schema_diff_exists() -> bool:
    engine = create_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            return bool(compare_metadata(context, Base.metadata))
    finally:
        engine.dispose()


def main() -> None:
    wait_for_database()
    config = make_config()

    # First apply any checked-in migrations.
    command.upgrade(config, "head")

    # Then generate and apply a new revision only if the database still differs from metadata.
    if not schema_diff_exists():
        print("No schema changes detected after upgrade.")
        return

    print("Detected schema changes. Generating an Alembic revision.")
    command.revision(config, message="auto schema sync", autogenerate=True)
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
