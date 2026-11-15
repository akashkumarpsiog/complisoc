"""Populate completion timestamps for finished scanner records.

Revision ID: 0013_backfill_scanner_execution_completion
Revises: 0012_add_scan_ai_status
"""
from alembic import op


revision = "0013_backfill_scanner_execution_completion"
down_revision = "0012_add_scan_ai_status"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE scanner_executions
        SET completed_at = COALESCE(updated_at, created_at)
        WHERE completed_at IS NULL
          AND status IN ('completed', 'failed')
        """
    )


def downgrade():
    # Historical completion timestamps cannot be distinguished from values
    # recorded by the application after this migration.
    pass
