"""Add saved_workflows table

Revision ID: 006_add_saved_workflows
Revises: 005_add_graph_runs
Create Date: 2026-02-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "006_add_saved_workflows"
down_revision: str = "005_add_graph_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_workflows",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("graph_spec", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("saved_workflows")
