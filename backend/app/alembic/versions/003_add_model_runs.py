"""Add model_runs table

Revision ID: 003
Revises: 002
Create Date: 2026-02-25
"""
from alembic import op
import sqlalchemy as sa

revision = "003_add_model_runs"
down_revision = "002_add_daily_weather"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_runs",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("model_type", sa.String(), nullable=False),
        sa.Column("datasources", sa.Text(), nullable=False),    # JSON list
        sa.Column("join_keys", sa.Text(), nullable=False),      # JSON list
        sa.Column("feature_columns", sa.Text(), nullable=False), # JSON list
        sa.Column("target_column", sa.String(), nullable=False),
        sa.Column("filters", sa.Text(), nullable=False),         # JSON object
        sa.Column("r2", sa.Float(), nullable=True),
        sa.Column("rmse", sa.Float(), nullable=True),
        sa.Column("n_samples", sa.Integer(), nullable=True),
        sa.Column("artifact_path", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("model_runs")
