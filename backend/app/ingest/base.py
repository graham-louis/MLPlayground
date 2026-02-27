"""
BaseDatasource — single-file plugin system for MLPlayground datasources.

To add a new data source, create ONE file named ``ds_<name>.py`` in this
directory and subclass ``BaseDatasource``::

    from app.ingest.base import BaseDatasource, Column

    class MySource(BaseDatasource):
        key         = "my_source"
        label       = "My Data Source"
        description = "Short description shown in the UI."
        columns = [
            Column("year",      int),
            Column("state",     str),
            Column("county",    str),
            Column("my_metric", float),
        ]

        def fetch(self, county, state, start_year, end_year):
            # ... call API, return a pandas DataFrame ...
            return df

That's it.  The framework automatically:
  • Registers the datasource with DATASOURCE_REGISTRY (→ Explore tabs, Ingest form)
  • Creates the backing database table on first use (no Alembic migration needed)
  • Provides a generic upsert() that persists DataFrames to the table
  • Exposes a query endpoint at GET /api/v1/data/<key>
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level table cache (populated lazily on first query/upsert)
# ---------------------------------------------------------------------------
_dynamic_tables: dict[str, Any] = {}  # key → sqlalchemy.Table


# ---------------------------------------------------------------------------
# Column descriptor
# ---------------------------------------------------------------------------

class Column:
    """Schema descriptor for a single column in a dynamic datasource table."""

    # Python type → SQLAlchemy column type factory
    _TYPE_MAP: dict[type, Any] = {}

    def __init__(self, name: str, dtype: type = str, nullable: bool = True) -> None:
        self.name = name
        self.dtype = dtype
        self.nullable = nullable

    @property
    def sa_type(self) -> Any:
        from sqlalchemy import Integer, Float, String, Boolean
        mapping = {int: Integer, float: Float, str: String(256), bool: Boolean}
        return mapping.get(self.dtype, String(256))


# ---------------------------------------------------------------------------
# BaseDatasource
# ---------------------------------------------------------------------------

class BaseDatasource(ABC):
    """
    Abstract base class for MLPlayground datasources.

    Subclass this, override ``fetch()``, and save the file as ``ds_*.py``
    in ``app/ingest/``.  Everything else is automatic.
    """

    key: str = ""
    label: str = ""
    description: str = ""
    columns: list[Column] = []
    scope_params: list[dict] = [
        {
            "name": "states",
            "type": "string_list",
            "label": "States",
            "placeholder": "e.g. North Carolina, Iowa",
            "default": ["North Carolina"],
        },
        {"name": "start_year", "type": "integer", "label": "Start Year", "default": 1980},
        {"name": "end_year",   "type": "integer", "label": "End Year",   "default": 2022},
    ]

    # Class-level map: key → instance (populated by __init_subclass__)
    _instances: dict[str, "BaseDatasource"] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "key", ""):
            return  # abstract intermediate subclass — skip

        instance = cls()
        BaseDatasource._instances[cls.key] = instance

        # Register with the central DATASOURCE_REGISTRY so the UI and ingest
        # pipeline discover this datasource automatically.
        try:
            from app.ingest.registry import DATASOURCE_REGISTRY
            DATASOURCE_REGISTRY.register(
                key=cls.key,
                label=cls.label,
                endpoint=f"/api/v1/data/{cls.key}",
                columns=[c.name for c in cls.columns],
                scope_params=cls.scope_params,
                fetch_fn=instance.fetch,
                upsert_fn=instance.upsert,
                description=cls.description,
            )
            logger.debug("BaseDatasource: auto-registered key=%r", cls.key)
        except Exception as exc:
            logger.warning("BaseDatasource: failed to register key=%r: %s", cls.key, exc)

    # ------------------------------------------------------------------
    # Abstract interface — subclasses must implement this one method
    # ------------------------------------------------------------------

    @abstractmethod
    def fetch(
        self,
        county: str,
        state: str,
        start_year: int,
        end_year: int,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch data for a single county/state over a year range.

        Return a DataFrame whose columns match ``self.columns``.
        Return ``None`` or an empty DataFrame if no data is available.
        Any exception raised here is caught and logged by the ingest runner.
        """
        ...

    # ------------------------------------------------------------------
    # Table management (lazy, checkfirst=True — no Alembic needed)
    # ------------------------------------------------------------------

    def _get_table(self) -> Any:
        """Return (and lazily create) the SQLAlchemy Core Table for this datasource."""
        if self.key not in _dynamic_tables:
            from sqlalchemy import Table, Column as SACol, Integer, MetaData
            from app.core.db import engine

            metadata = MetaData()
            sa_cols = [SACol("id", Integer, primary_key=True, autoincrement=True)]
            for col in self.columns:
                sa_cols.append(SACol(col.name, col.sa_type, nullable=col.nullable))

            table = Table(self.key, metadata, *sa_cols, extend_existing=True)
            metadata.create_all(engine, checkfirst=True)
            _dynamic_tables[self.key] = table
            logger.debug("BaseDatasource: table '%s' ready", self.key)

        return _dynamic_tables[self.key]

    # ------------------------------------------------------------------
    # Generic upsert — used by the ingest pipeline
    # ------------------------------------------------------------------

    def upsert(self, df: pd.DataFrame) -> None:
        """
        Persist a DataFrame to the datasource table.

        Rows are matched by (year, county, state) when those columns exist;
        existing rows are replaced.  Rows with entirely NULL values are skipped.
        """
        if df is None or df.empty:
            return

        from sqlalchemy import and_
        from app.core.db import engine

        table = self._get_table()
        col_names = [col.name for col in self.columns]
        identity = [c for c in ("year", "county", "state", "crop", "date") if c in col_names]

        with engine.begin() as conn:
            for _, row in df.iterrows():
                values = {c: row.get(c) for c in col_names if c in row.index}
                if not values:
                    continue

                # Delete existing row with same identity, then insert
                if identity:
                    where_clauses = [
                        table.c[c] == values[c]
                        for c in identity
                        if c in table.c and values.get(c) is not None
                    ]
                    if where_clauses:
                        conn.execute(table.delete().where(and_(*where_clauses)))

                conn.execute(table.insert().values(**values))

        logger.debug("BaseDatasource: upserted %d rows into '%s'", len(df), self.key)

    # ------------------------------------------------------------------
    # Generic query — used by GET /api/v1/data/{key}
    # ------------------------------------------------------------------

    def query(
        self,
        state: Optional[str] = None,
        county: Optional[str] = None,
        year: Optional[int] = None,
        skip: int = 0,
        limit: int = 1000,
    ) -> tuple[list[dict], int]:
        """
        Query the datasource table with optional filters.

        Returns ``(rows, total_count)`` where rows is a list of dicts.
        """
        from sqlalchemy import select, func, and_
        from app.core.db import engine

        table = self._get_table()
        col_names = [col.name for col in self.columns]

        conditions = []
        if state  is not None and "state"  in col_names:
            conditions.append(table.c["state"]  == state)
        if county is not None and "county" in col_names:
            conditions.append(table.c["county"] == county)
        if year   is not None and "year"   in col_names:
            conditions.append(table.c["year"]   == year)

        base_q = select(table)
        if conditions:
            base_q = base_q.where(and_(*conditions))

        count_q = select(func.count()).select_from(base_q.subquery())

        with engine.connect() as conn:
            total = conn.execute(count_q).scalar() or 0
            rows  = conn.execute(base_q.offset(skip).limit(limit)).fetchall()

        return [dict(r._mapping) for r in rows], total
