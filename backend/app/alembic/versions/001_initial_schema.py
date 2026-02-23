"""Initial schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "yields",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("state", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("district", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("county", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("county_ansi", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("crop", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "weather",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("state", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("county", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("avg_temp", sa.Float(), nullable=True),
        sa.Column("precipitation", sa.Float(), nullable=True),
        sa.Column("vp", sa.Float(), nullable=True),
        sa.Column("srad", sa.Float(), nullable=True),
        sa.Column("gdd", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "soil",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("state", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("county", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("ph", sa.Float(), nullable=True),
        sa.Column("organic_matter", sa.Float(), nullable=True),
        sa.Column("sand_pct", sa.Float(), nullable=True),
        sa.Column("clay_pct", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("soil")
    op.drop_table("weather")
    op.drop_table("yields")
