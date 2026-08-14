"""Add non-destructive scan-run archiving.

Revision ID: 0009_add_scan_run_archiving
Revises: 0008_add_groq_agreement_value
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_add_scan_run_archiving"
down_revision = "0008_add_groq_agreement_value"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("scan_runs")}
    if "archived_at" not in columns:
        with op.batch_alter_table("scan_runs") as batch_op:
            batch_op.add_column(sa.Column("archived_at", sa.DateTime(), nullable=True))
            batch_op.create_index("ix_scan_runs_archived_at", ["archived_at"])


def downgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("scan_runs")}
    if "archived_at" in columns:
        with op.batch_alter_table("scan_runs") as batch_op:
            batch_op.drop_index("ix_scan_runs_archived_at")
            batch_op.drop_column("archived_at")
