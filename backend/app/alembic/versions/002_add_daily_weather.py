"""Add daily_weather table

Revision ID: 002_add_daily_weather
Revises: 001_initial_schema
Create Date: 2026-02-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

revision: str = "002_add_daily_weather"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_weather",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("day_of_year", sa.Integer(), nullable=False),
        sa.Column("date", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("state", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("county", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("tmax", sa.Float(), nullable=True),
        sa.Column("tmin", sa.Float(), nullable=True),
        sa.Column("prcp", sa.Float(), nullable=True),
        sa.Column("srad", sa.Float(), nullable=True),
        sa.Column("vp", sa.Float(), nullable=True),
        sa.Column("dayl", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_daily_weather_county_year", "daily_weather", ["county", "state", "year"])


def downgrade() -> None:
    op.drop_index("ix_daily_weather_county_year", table_name="daily_weather")
    op.drop_table("daily_weather")
