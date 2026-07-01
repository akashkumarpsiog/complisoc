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


def _columns(table_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    control_catalog_columns = _columns("control_catalog")
    with op.batch_alter_table("control_catalog") as batch_op:
        if "framework_version" not in control_catalog_columns:
            batch_op.add_column(sa.Column("framework_version", sa.String(64), nullable=True))
        if "control_family" not in control_catalog_columns:
            batch_op.add_column(sa.Column("control_family", sa.String(256), nullable=True))
        if "objective" not in control_catalog_columns:
            batch_op.add_column(sa.Column("objective", sa.Text(), nullable=True))
        if "evidence_examples" not in control_catalog_columns:
            batch_op.add_column(sa.Column("evidence_examples", sa.JSON(), nullable=True))
        if "scanner_signals" not in control_catalog_columns:
            batch_op.add_column(sa.Column("scanner_signals", sa.JSON(), nullable=True))
        if "keywords" not in control_catalog_columns:
            batch_op.add_column(sa.Column("keywords", sa.JSON(), nullable=True))
        if "source_url" not in control_catalog_columns:
            batch_op.add_column(sa.Column("source_url", sa.String(1024), nullable=True))

        if "version" in control_catalog_columns:
            batch_op.drop_column("version")
        if "control_metadata" in control_catalog_columns:
            batch_op.drop_column("control_metadata")

    control_mapping_columns = _columns("control_mappings")
    with op.batch_alter_table("control_mappings") as batch_op:
        if "rank" not in control_mapping_columns:
            batch_op.add_column(sa.Column("rank", sa.Integer(), nullable=True, server_default="1"))
        if "mapping_model" not in control_mapping_columns:
            batch_op.add_column(sa.Column("mapping_model", sa.String(256), nullable=True))
        if "prompt_version" not in control_mapping_columns:
            batch_op.add_column(sa.Column("prompt_version", sa.String(128), nullable=True))
        if "verification_status" not in control_mapping_columns:
            batch_op.add_column(sa.Column("verification_status", sa.String(50), nullable=True))
        if "final_confidence" not in control_mapping_columns:
            batch_op.add_column(sa.Column("final_confidence", sa.Float(), nullable=True))
        if "mapping_status" not in control_mapping_columns:
            batch_op.add_column(
                sa.Column(
                    "mapping_status",
                    sa.String(50),
                    nullable=False,
                    server_default="generated",
                )
            )

        if "status" in control_mapping_columns:
            batch_op.drop_column("status")
        if "scan_run_id" in control_mapping_columns:
            batch_op.drop_column("scan_run_id")

    candidate_control_columns = _columns("candidate_controls")
    with op.batch_alter_table("candidate_controls") as batch_op:
        if "match_score" not in candidate_control_columns:
            batch_op.add_column(sa.Column("match_score", sa.Float(), nullable=True))
        if "rank" not in candidate_control_columns:
            batch_op.add_column(sa.Column("rank", sa.Integer(), nullable=True))
        if "score" in candidate_control_columns:
            batch_op.drop_column("score")
        if "rationale" in candidate_control_columns:
            batch_op.drop_column("rationale")


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
