from logging.config import fileConfig
import os
import sys

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Make the app package importable when Alembic is run from backend/.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import models  # noqa: E402  -- populates Base.metadata
from app.database import Base  # noqa: E402
from app import config as app_config  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Real target metadata (not None) -- this is what makes
# `alembic revision --autogenerate` diff against the actual ORM models
# instead of producing an empty migration.
target_metadata = Base.metadata

# DATABASE_URL from the app's own config (env var), not a hardcoded value
# duplicated into alembic.ini -- one source of truth for the connection
# string, same as the running application uses.
config.set_main_option("sqlalchemy.url", app_config.DATABASE_URL)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


# PostGIS creates its own internal bookkeeping tables (spatial_ref_sys,
# geometry_columns, etc.) that live in the same schema but aren't part of
# our ORM models. Without this filter, `--autogenerate` tries to DROP
# them on every run, which would break the PostGIS extension.
POSTGIS_SYSTEM_TABLES = {"spatial_ref_sys", "geometry_columns", "geography_columns", "raster_columns", "raster_overviews"}


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in POSTGIS_SYSTEM_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
