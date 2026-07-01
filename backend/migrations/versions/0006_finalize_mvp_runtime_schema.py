"""Finalize runtime schema after local MVP drift repair.

Revision ID: 0006_finalize_mvp_runtime_schema
Revises: 0005_repair_mvp_schema_drift
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_finalize_mvp_runtime_schema"
down_revision = "0005_repair_mvp_schema_drift"
branch_labels = None
depends_on = None


def _columns(table_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _drop_columns_if_present(table_name, column_names):
    existing = _columns(table_name)
    to_drop = [column_name for column_name in column_names if column_name in existing]
    if not to_drop:
        return
    with op.batch_alter_table(table_name) as batch_op:
        for column_name in to_drop:
            batch_op.drop_column(column_name)


def upgrade():
    bind = op.get_bind()

    _drop_columns_if_present("scan_runs", ["name"])
    _drop_columns_if_present("normalized_findings", ["scan_run_id", "normalized_data"])

    bind.execute(sa.text("UPDATE control_catalog SET framework_version = COALESCE(framework_version, 'unknown')"))
    bind.execute(sa.text("UPDATE control_catalog SET control_family = COALESCE(control_family, 'Unclassified')"))
    bind.execute(sa.text("UPDATE control_catalog SET objective = COALESCE(objective, description)"))
    bind.execute(sa.text("UPDATE control_catalog SET evidence_examples = COALESCE(evidence_examples, json_array())"))
    bind.execute(sa.text("UPDATE control_catalog SET scanner_signals = COALESCE(scanner_signals, json_array())"))
    bind.execute(sa.text("UPDATE control_catalog SET keywords = COALESCE(keywords, json_array())"))
    bind.execute(sa.text("UPDATE control_catalog SET source_url = COALESCE(source_url, 'https://example.invalid/legacy-control')"))


def downgrade():
    pass
