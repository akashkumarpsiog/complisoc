"""Add confidence workflow fields to control_mappings and candidate_controls

Revision ID: 0002_confidence_workflow
Revises: 0001_initial
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_confidence_workflow"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("control_mappings") as batch_op:
        batch_op.add_column(sa.Column("verification_status", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("final_confidence", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "mapping_status",
                sa.String(50),
                nullable=False,
                server_default="generated",
            )
        )

        # remove old status column if it exists
        try:
            batch_op.drop_column("status")
        except Exception:
            pass

    with op.batch_alter_table("candidate_controls") as batch_op:
        batch_op.add_column(sa.Column("match_score", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("rank", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("candidate_controls") as batch_op:
        batch_op.drop_column("rank")
        batch_op.drop_column("match_score")

    with op.batch_alter_table("control_mappings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(50),
                nullable=False,
                server_default="active"
            )
        )
        batch_op.drop_column("mapping_status")
        batch_op.drop_column("final_confidence")
        batch_op.drop_column("verification_status")