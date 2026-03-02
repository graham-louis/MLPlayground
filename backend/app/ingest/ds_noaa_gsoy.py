"""
NOAA Global Summary of the Year (GSOY) datasource plugin.

Fetches annual climate summaries for US states from the NOAA Climate Data
Online (CDO) API.  Requires the ``NOAA_CDO_TOKEN`` environment variable — a
free token can be requested at https://www.ncdc.noaa.gov/cdo-web/token

Results are cached under ``{ARTIFACTS_BASE}/noaa_cache/`` so repeated
requests do not hit the API.

Compatible with the ``remote_fetch`` graph node, which reads ``scope_params``
from this class and passes user-supplied values to ``fetch()``.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from app.ingest.base import BaseDatasource, Column

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CDO API helpers
# ---------------------------------------------------------------------------

_CDO_BASE = "https://www.ncdc.noaa.gov/cdo-web/api/v2/data"

# FIPS location codes used by the CDO API for US state-level queries
_STATE_FIPS: dict[str, str] = {
    "AL": "FIPS:01", "AK": "FIPS:02", "AZ": "FIPS:04", "AR": "FIPS:05",
    "CA": "FIPS:06", "CO": "FIPS:08", "CT": "FIPS:09", "DE": "FIPS:10",
    "FL": "FIPS:12", "GA": "FIPS:13", "HI": "FIPS:15", "ID": "FIPS:16",
    "IL": "FIPS:17", "IN": "FIPS:18", "IA": "FIPS:19", "KS": "FIPS:20",
    "KY": "FIPS:21", "LA": "FIPS:22", "ME": "FIPS:23", "MD": "FIPS:24",
    "MA": "FIPS:25", "MI": "FIPS:26", "MN": "FIPS:27", "MS": "FIPS:28",
    "MO": "FIPS:29", "MT": "FIPS:30", "NE": "FIPS:31", "NV": "FIPS:32",
    "NH": "FIPS:33", "NJ": "FIPS:34", "NM": "FIPS:35", "NY": "FIPS:36",
    "NC": "FIPS:37", "ND": "FIPS:38", "OH": "FIPS:39", "OK": "FIPS:40",
    "OR": "FIPS:41", "PA": "FIPS:42", "RI": "FIPS:44", "SC": "FIPS:45",
    "SD": "FIPS:46", "TN": "FIPS:47", "TX": "FIPS:48", "UT": "FIPS:49",
    "VT": "FIPS:50", "VA": "FIPS:51", "WA": "FIPS:53", "WV": "FIPS:54",
    "WI": "FIPS:55", "WY": "FIPS:56",
}


_CDO_MAX_YEARS = 10  # NOAA CDO API rejects date ranges longer than 10 years


def _fetch_cdo_chunk(
    location_id: str,
    chunk_start: int,
    chunk_end: int,
    variables: list[str],
    headers: dict,
) -> list[dict]:
    """Page through CDO results for a single ≤10-year chunk."""
    import requests

    base_params: dict[str, Any] = {
        "datasetid": "GSOY",
        "locationid": location_id,
        "startdate": f"{chunk_start}-01-01",
        "enddate": f"{chunk_end}-12-31",
        "datatypeid": ",".join(v.upper() for v in variables),
        "units": "standard",
        "limit": 1000,
    }

    records: list[dict] = []
    offset = 1
    while True:
        resp = requests.get(
            _CDO_BASE,
            headers=headers,
            params={**base_params, "offset": offset},
            timeout=30,
        )
        if resp.status_code == 404:
            break
        resp.raise_for_status()
        body = resp.json()
        page = body.get("results", [])
        records.extend(page)
        resultset = body.get("metadata", {}).get("resultset", {})
        count = resultset.get("count", 0)
        if not page or offset + len(page) - 1 >= count:
            break
        offset += len(page)

    return records


def _call_cdo_api(
    state: str,
    start_year: int,
    end_year: int,
    variables: list[str],
    token: str,
) -> pd.DataFrame:
    """Page through the CDO API and return a tidy DataFrame of annual summaries.

    The NOAA CDO API rejects requests spanning more than 10 years, so long
    ranges are automatically split into ≤10-year chunks.
    """
    location_id = _STATE_FIPS.get(state.upper())
    if location_id is None:
        raise ValueError(
            f"NOAAGSOYDatasource: unknown state abbreviation '{state}'. "
            f"Expected two-letter US postal code, e.g. 'NC'."
        )

    headers = {"token": token}

    # Build list of (chunk_start, chunk_end) pairs each ≤ _CDO_MAX_YEARS wide
    chunks: list[tuple[int, int]] = []
    cs = start_year
    while cs <= end_year:
        ce = min(cs + _CDO_MAX_YEARS - 1, end_year)
        chunks.append((cs, ce))
        cs = ce + 1

    records: list[dict] = []
    for cs, ce in chunks:
        logger.debug("NOAAGSOYDatasource: fetching chunk %d–%d", cs, ce)
        records.extend(_fetch_cdo_chunk(location_id, cs, ce, variables, headers))

    if not records:
        logger.warning(
            "NOAAGSOYDatasource: no records for %s %d–%d vars=%s",
            state, start_year, end_year, variables,
        )
        cols = ["year", "state", "station"] + [v.lower() for v in variables]
        return pd.DataFrame(columns=cols)

    raw = pd.DataFrame(records)
    raw["year"] = pd.to_datetime(raw["date"]).dt.year
    pivoted = (
        raw.pivot_table(
            index=["year", "station"],
            columns="datatype",
            values="value",
            aggfunc="mean",
        )
        .reset_index()
    )
    pivoted.columns.name = None
    # Lowercase every variable column
    pivoted.rename(columns={v: v.lower() for v in variables}, inplace=True)

    var_cols = sorted(v.lower() for v in variables if v.lower() in pivoted.columns)
    final_cols = ["year", "station"] + var_cols
    for c in final_cols:
        if c not in pivoted.columns:
            pivoted[c] = None
    pivoted["state"] = state.upper()
    return (
        pivoted[["year", "state", "station"] + var_cols]
        .sort_values(["year", "station"])
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# Datasource plugin
# ---------------------------------------------------------------------------

class NOAAGSOYDatasource(BaseDatasource):
    """Annual climate summaries (GSOY) for US states from the NOAA CDO API."""

    key         = "noaa_gsoy"
    label       = "NOAA Annual Weather (GSOY)"
    description = (
        "Yearly climate summaries from the NOAA Climate Data Online (CDO) API. "
        "Requires the NOAA_CDO_TOKEN environment variable."
    )

    columns = [
        Column("year",    int),
        Column("state",   str),
        Column("station", str),
        Column("tavg",    float),
        Column("prcp",    float),
        Column("tmax",    float),
        Column("tmin",    float),
        Column("snow",    float),
    ]

    # These scope_params are read by the ``remote_fetch`` graph node to
    # auto-populate its inspector fields when this datasource is selected.
    scope_params = [
        {
            "name": "state",
            "type": "string",
            "label": "State (2-letter abbrev.)",
            "description": "US state abbreviation, e.g. NC, IA, CA.",
            "default": "NC",
        },
        {
            "name": "start_year",
            "type": "integer",
            "label": "Start Year",
            "description": "Inclusive start of the year range.",
            "default": 2010,
        },
        {
            "name": "end_year",
            "type": "integer",
            "label": "End Year",
            "description": "Inclusive end of the year range.",
            "default": 2020,
        },
        {
            "name": "variables",
            "type": "string_list",
            "label": "Variables",
            "description": (
                "NOAA data-type IDs: TAVG, PRCP, TMAX, TMIN, SNOW, etc. "
                "See https://www.ncdc.noaa.gov/cdo-web/datatools/findstation"
            ),
            "default": ["TAVG", "PRCP"],
        },
    ]

    # ------------------------------------------------------------------
    # fetch() — called by the ingest runner AND by RemoteFetchNode
    # ------------------------------------------------------------------

    def fetch(  # type: ignore[override]
        self,
        county: str = "",
        state: str = "NC",
        start_year: int = 2010,
        end_year: int = 2020,
        variables: Optional[list[str]] = None,
    ) -> Optional[pd.DataFrame]:
        """Fetch GSOY data for *state* over [start_year, end_year].

        ``county`` is accepted for interface compatibility but ignored —
        NOAA GSOY data is aggregated at the state level.
        Results are cached as Parquet files under ``{ARTIFACTS_BASE}/noaa_cache/``.
        """
        token = os.environ.get("NOAA_CDO_TOKEN", "").strip()
        try:
            from app.core.config import settings as _settings
            token = _settings.NOAA_CDO_TOKEN.strip() or token
        except Exception:
            pass
        if not token:
            raise RuntimeError(
                "NOAAGSOYDatasource: NOAA_CDO_TOKEN environment variable is not set. "
                "Request a free token at https://www.ncdc.noaa.gov/cdo-web/token"
            )

        state = str(state).upper().strip()
        variables = [v.upper().strip() for v in (variables or ["TAVG", "PRCP"])]
        start_year = int(start_year)
        end_year = int(end_year)

        if start_year > end_year:
            raise ValueError(
                f"NOAAGSOYDatasource: start_year ({start_year}) must be ≤ end_year ({end_year})."
            )

        # Build a stable cache key from all relevant params
        cache_key = hashlib.sha256(
            json.dumps(
                {"state": state, "start": start_year, "end": end_year, "vars": sorted(variables)},
                sort_keys=True,
            ).encode()
        ).hexdigest()[:16]

        try:
            from app.core.config import settings as _settings
            cache_dir = Path(_settings.ARTIFACTS_BASE) / "noaa_cache"
        except Exception:
            cache_dir = Path(os.environ.get("ARTIFACTS_BASE", "/app/artifacts")) / "noaa_cache"

        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{state}_{start_year}_{end_year}_{cache_key}.parquet"

        if cache_file.exists():
            logger.info("NOAAGSOYDatasource: loading cached data from %s", cache_file)
            return pd.read_parquet(cache_file)

        logger.info(
            "NOAAGSOYDatasource: fetching GSOY for %s %d–%d vars=%s",
            state, start_year, end_year, variables,
        )
        df = _call_cdo_api(state, start_year, end_year, variables, token)
        df.to_parquet(cache_file, index=False)
        logger.info("NOAAGSOYDatasource: cached %d rows → %s", len(df), cache_file)
        return df
