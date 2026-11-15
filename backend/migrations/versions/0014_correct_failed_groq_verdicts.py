"""Represent missing Groq verdicts as failures, not disagreements.

Revision ID: 0014_correct_failed_groq_verdicts
Revises: 0013_backfill_scanner_execution_completion
"""
from alembic import op
import sqlalchemy as sa


revision = "0014_correct_failed_groq_verdicts"
down_revision = "0013_backfill_scanner_execution_completion"
branch_labels = None
depends_on = None


def upgrade():
    constraints = sa.inspect(op.get_bind()).get_check_constraints("verification_records")
    has_result_constraint = any(
        constraint.get("name") == "ck_verification_result" for constraint in constraints
    )
    with op.batch_alter_table("verification_records") as batch_op:
        if has_result_constraint:
            batch_op.drop_constraint("ck_verification_result", type_="check")
        batch_op.create_check_constraint(
            "ck_verification_result",
            "result IN ('agree','disagree','failed')",
        )

    op.execute(
        """
        UPDATE control_mappings
        SET groq_agreement_value = NULL,
            final_confidence = NULL
        WHERE verification_status = 'failed'
        """
    )
    op.execute(
        """
        UPDATE verification_records
        SET result = 'failed', agreement_value = NULL
        WHERE result = 'disagree'
          AND control_mapping_id IN (
              SELECT id FROM control_mappings WHERE verification_status = 'failed'
          )
        """
    )
    op.execute(
        """
        UPDATE scan_runs
        SET ai_status = 'partial'
        WHERE ai_status = 'ok'
          AND id IN (
              SELECT se.scan_run_id
              FROM control_mappings cm
              JOIN normalized_findings nf ON nf.id = cm.normalized_finding_id
              JOIN raw_findings rf ON rf.id = nf.raw_finding_id
              JOIN scanner_executions se ON se.id = rf.scanner_execution_id
              WHERE cm.verification_status = 'failed'
          )
        """
    )


def downgrade():
    # Corrected failure records cannot safely be converted back to disagreements.
    pass
