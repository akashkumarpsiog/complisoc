"""Add manifest_path to audit_bundles for cryptographic integrity verification.

Revision ID: 0010_add_audit_bundle_manifest
Revises: 0009_add_scan_run_archiving
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_add_audit_bundle_manifest"
down_revision = "0009_add_scan_run_archiving"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("audit_bundles")}
    if "manifest_path" not in columns:
        with op.batch_alter_table("audit_bundles") as batch_op:
            batch_op.add_column(sa.Column("manifest_path", sa.String(1024), nullable=True))


def downgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("audit_bundles")}
    if "manifest_path" in columns:
        with op.batch_alter_table("audit_bundles") as batch_op:
            batch_op.drop_column("manifest_path")
