"""
Bulk ingestion runner for MLPlayground.

Iterates over all registered BaseDatasource plugins for each county in each
configured state and calls fetch() + upsert() for every combination.

The list of states is read from INGEST_STATES env var (comma-separated).
Year range is controlled by INGEST_START_YEAR / INGEST_END_YEAR.
Set DRY_RUN=1 to skip DB writes.
"""
import logging
import os

from app.ingest._daymet_helpers import get_counties_for_state  # noqa: F401 — re-exported for ingest.py

logger = logging.getLogger(__name__)

DEFAULT_STATES = [
    "North Carolina",
    "Iowa",
    "Illinois",
    "Indiana",
    "Nebraska",
    "Minnesota",
    "Ohio",
    "Missouri",
    "South Dakota",
    "Kansas",
]


def main() -> None:
    """
    Bulk ingestion entry point.

    Discovers all ds_*.py datasource plugins, then for each county in each
    configured state calls each plugin's fetch() and upsert().

    Optional environment variables:
        INGEST_STATES      – Comma-separated state names.
        INGEST_START_YEAR  – First year (default: 1980).
        INGEST_END_YEAR    – Last year (default: 2022).
        DRY_RUN            – Set to 1 to skip DB writes.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    from app.ingest import discover_plugins
    from app.ingest.base import BaseDatasource

    discover_plugins()

    if not BaseDatasource._instances:
        logger.error("No datasource plugins found — nothing to ingest.")
        return

    states_env = os.environ.get("INGEST_STATES", "")
    states = [s.strip() for s in states_env.split(",") if s.strip()] if states_env else DEFAULT_STATES
    start_year = int(os.environ.get("INGEST_START_YEAR", "1980"))
    end_year = int(os.environ.get("INGEST_END_YEAR", "2022"))
    dry_run = os.environ.get("DRY_RUN", "") not in ("", "0")

    logger.info(
        "Starting bulk ingestion: %d plugin(s), %d state(s), years %d–%d.",
        len(BaseDatasource._instances), len(states), start_year, end_year,
    )

    for state in states:
        counties = get_counties_for_state(state)
        if not counties:
            logger.warning("No counties found for %s — skipping.", state)
            continue

        total = len(counties)
        for idx, county in enumerate(counties, 1):
            logger.info("[%s %d/%d] Processing %s…", state, idx, total, county)
            if dry_run:
                continue

            for ds in BaseDatasource._instances.values():
                try:
                    df = ds.fetch(county, state, start_year, end_year)
                    ds.upsert(df)
                except Exception as exc:
                    logger.error("Ingestion failed for %s/%s, %s: %s", ds.key, county, state, exc)

    logger.info("Bulk ingestion complete.")


if __name__ == "__main__":
    main()

