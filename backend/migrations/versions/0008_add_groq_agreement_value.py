"""Add groq_agreement_value to control_mappings.

Revision ID: 0008_add_groq_agreement_value
Revises: 0007_add_agreement_value
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_add_groq_agreement_value"
down_revision = "0007_add_agreement_value"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("control_mappings")}
    if "groq_agreement_value" not in columns:
        with op.batch_alter_table("control_mappings") as batch_op:
            batch_op.add_column(sa.Column("groq_agreement_value", sa.Float()))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("control_mappings")}
    if "groq_agreement_value" in columns:
        with op.batch_alter_table("control_mappings") as batch_op:
            batch_op.drop_column("groq_agreement_value")
