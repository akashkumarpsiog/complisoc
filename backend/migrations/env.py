from __future__ import with_statement

import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from sqlalchemy import create_engine
from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
fileConfig(config.config_file_name)

# Interpret the config file for Python logging.
# This line sets up loggers basically.

# Use the same database URL as the application by default.
section = config.get_section(config.config_ini_section)
if not section.get("sqlalchemy.url"):
    section["sqlalchemy.url"] = os.getenv("DATABASE_URL", "sqlite:///complisoc.db")

# Import metadata from models
from complisoc.backend.database.base import Base  # noqa: E402
from complisoc.backend.models import *  # noqa: E402, F401

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
