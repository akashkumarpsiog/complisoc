"""Add agreement_value to verification_records.

Revision ID: 0007_add_agreement_value
Revises: 0006_finalize_mvp_runtime_schema
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_add_agreement_value"
down_revision = "0006_finalize_mvp_runtime_schema"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("verification_records")}
    if "agreement_value" not in columns:
        with op.batch_alter_table("verification_records") as batch_op:
            batch_op.add_column(sa.Column("agreement_value", sa.Float()))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("verification_records")}
    if "agreement_value" in columns:
        with op.batch_alter_table("verification_records") as batch_op:
            batch_op.drop_column("agreement_value")
