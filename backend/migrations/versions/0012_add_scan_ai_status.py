"""Track AI enrichment outcome separately from scanner completion.

Revision ID: 0012_add_scan_ai_status
Revises: 0011_correct_iso27001_benchmark_controls
"""
from alembic import op
import sqlalchemy as sa


revision = "0012_add_scan_ai_status"
down_revision = "0011_correct_iso27001_benchmark_controls"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("scan_runs") as batch_op:
        batch_op.add_column(sa.Column("ai_status", sa.String(length=16), nullable=True))
        batch_op.create_check_constraint(
            "ck_scanrun_ai_status",
            "ai_status IS NULL OR ai_status IN ('ok','partial','failed')",
        )


def downgrade():
    with op.batch_alter_table("scan_runs") as batch_op:
        batch_op.drop_constraint("ck_scanrun_ai_status", type_="check")
        batch_op.drop_column("ai_status")
