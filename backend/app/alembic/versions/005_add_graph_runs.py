"""Add graph_runs table

Revision ID: 005_add_graph_runs
Revises: 004_drop_domain_tables
Create Date: 2026-02-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_add_graph_runs"
down_revision: Union[str, None] = "004_drop_domain_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "graph_runs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("run_id", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("graph_spec", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("node_statuses", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("graph_runs")
