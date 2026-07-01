"""Repair MVP schema drift from early local SQLite databases.

Revision ID: 0005_repair_mvp_schema_drift
Revises: 0004_seed_soc2_tsc_categories
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_repair_mvp_schema_drift"
down_revision = "0004_seed_soc2_tsc_categories"
branch_labels = None
depends_on = None


def _columns(table_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _add_column_if_missing(table_name, column):
    if column.name not in _columns(table_name):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(column)


def upgrade():
    bind = op.get_bind()

    _add_column_if_missing("scan_runs", sa.Column("target_environment", sa.String(128), nullable=True))
    if "name" in _columns("scan_runs"):
        bind.execute(sa.text("UPDATE scan_runs SET target_environment = COALESCE(target_environment, name)"))
    bind.execute(sa.text("UPDATE scan_runs SET target_environment = COALESCE(target_environment, 'unknown')"))

    raw_columns = _columns("raw_findings")
    _add_column_if_missing("raw_findings", sa.Column("scanner_finding_id", sa.String(256), nullable=True))
    _add_column_if_missing("raw_findings", sa.Column("raw_json", sa.JSON(), nullable=True))
    if "raw_data" in raw_columns:
        bind.execute(sa.text("UPDATE raw_findings SET raw_json = COALESCE(raw_json, raw_data)"))
    if "title" in raw_columns:
        bind.execute(sa.text("UPDATE raw_findings SET scanner_finding_id = COALESCE(scanner_finding_id, title)"))
    bind.execute(sa.text("UPDATE raw_findings SET scanner_finding_id = COALESCE(scanner_finding_id, 'legacy-' || id)"))
    bind.execute(sa.text("UPDATE raw_findings SET raw_json = COALESCE(raw_json, json_object('legacy_raw_finding_id', id))"))

    _add_column_if_missing("normalized_findings", sa.Column("metadata_json", sa.JSON(), nullable=True))
    if "normalized_data" in _columns("normalized_findings"):
        bind.execute(sa.text("UPDATE normalized_findings SET metadata_json = COALESCE(metadata_json, normalized_data)"))

    _add_column_if_missing("verification_records", sa.Column("verification_model", sa.String(256), nullable=True))
    _add_column_if_missing("verification_records", sa.Column("prompt_version", sa.String(128), nullable=True))
    bind.execute(sa.text("UPDATE verification_records SET verification_model = COALESCE(verification_model, 'legacy-verifier')"))
    bind.execute(sa.text("UPDATE verification_records SET prompt_version = COALESCE(prompt_version, 'legacy')"))

    _add_column_if_missing("review_queue_items", sa.Column("review_reason_code", sa.String(64), nullable=True))
    _add_column_if_missing("review_queue_items", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    bind.execute(sa.text("UPDATE review_queue_items SET review_reason_code = COALESCE(review_reason_code, 'LEGACY_REVIEW')"))

    _add_column_if_missing("compliance_reports", sa.Column("generated_by", sa.String(256), nullable=True))
    _add_column_if_missing("compliance_reports", sa.Column("content_path", sa.String(1024), nullable=True))
    _add_column_if_missing("compliance_reports", sa.Column("content_hash", sa.String(128), nullable=True))
    bind.execute(sa.text("UPDATE compliance_reports SET generated_by = COALESCE(generated_by, 'legacy')"))

    _add_column_if_missing("audit_bundles", sa.Column("checksum", sa.String(128), nullable=True))
    bind.execute(sa.text("UPDATE audit_bundles SET checksum = COALESCE(checksum, 'legacy-' || id)"))

    # Early local databases had extra NOT NULL raw_finding columns from a previous model.
    # Recreate the table to match the immutable evidence model used by the MVP workflow.
    raw_columns = _columns("raw_findings")
    legacy_raw_columns = {
        "finding_type",
        "resource_type",
        "resource_identifier",
        "severity",
        "title",
        "description",
        "raw_data",
        "timestamp",
        "updated_at",
    }
    if legacy_raw_columns & raw_columns:
        with op.batch_alter_table("raw_findings") as batch_op:
            for column_name in sorted(legacy_raw_columns & raw_columns):
                batch_op.drop_column(column_name)


def downgrade():
    # This migration is a forward-only repair for local development SQLite drift.
    pass
