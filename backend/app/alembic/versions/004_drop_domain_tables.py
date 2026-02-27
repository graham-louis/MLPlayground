"""Drop domain tables managed by Alembic; BaseDatasource will recreate them.

After this migration, the yields, weather, soil, daily_weather, and weather_psa
tables are no longer managed by Alembic.  They are recreated automatically by
the BaseDatasource plugin system (app/ingest/ds_*.py files) on first use with
the schema defined in each plugin's ``columns`` list.

Revision ID: 004_drop_domain_tables
Revises: 03519123921b
Create Date: 2026-03-01
"""
from typing import Sequence, Union

from alembic import op

revision: str = "004_drop_domain_tables"
down_revision: Union[str, None] = "03519123921b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("yields", "weather", "soil", "daily_weather", "weather_psa"):
        op.execute(f"DROP TABLE IF EXISTS {table}")  # noqa: S608


def downgrade() -> None:
    # Domain tables are now plugin-managed; downgrade is a no-op.
    pass
