"""Initial schema migration

Revision ID: 0001_initial
Revises: None
Create Date: 2026-06-10 00:00:00.000000
"""

from alembic import op #provides commands to create tables, add columns, drop constraints.
from sqlalchemy import text #text lets us write raw sql 
from complisoc.backend.database.base import Base #stores all ORM table definitions
from complisoc.backend.models import * #imports all models so they register with the Base.metadata

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade():
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
