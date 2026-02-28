"""Remote Data Fetch node — call any registered ingest datasource at runtime.

This node is a generalised alternative to hard-coded source nodes.  The user
picks a datasource key (e.g. ``noaa_gsoy``, ``yields``, ``weather``) and
fills in **scope params** — the same parameters that drive the ingest form —
as a JSON object.

The node reads the datasource's ``scope_params`` spec to:
  1. Know which keys are expected and what their types are.
  2. Supply defaults for any key the user omits.
  3. Cast values to the correct Python types before calling ``fetch()``.

Result is cached as Parquet under ``{ARTIFACTS_BASE}/cache/remote/`` using a
hash of (datasource_key, resolved_params) so re-runs with identical settings
are free.

Example scope params for ``noaa_gsoy``::

    {"state": "NC", "start_year": 2015, "end_year": 2020, "variables": ["TAVG", "PRCP"]}

To discover available datasource keys and their required scope params, call::

    GET /api/v1/graphs/datasource-keys
    GET /api/v1/graphs/datasource-info/{key}
"""
from __future__ import annotations

import hashlib
import inspect
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.nodes.base import BaseNode, IOSlot, IOTypes

logger = logging.getLogger(__name__)


def _artifacts_base() -> str:
    try:
        from app.core.config import settings
        return settings.ARTIFACTS_BASE
    except Exception:
        return os.environ.get("ARTIFACTS_BASE", "/app/artifacts")


def _cast_scope_value(value: Any, param_spec: dict) -> Any:
    """Cast *value* to the Python type declared in a ``scope_params`` entry.

    Supported ``type`` strings:
      * ``"integer"``     → ``int``
      * ``"float"``       → ``float``
      * ``"boolean"``     → ``bool``
      * ``"string_list"`` → ``list[str]`` (accepts comma-separated str or list)
      * ``"string"``      → ``str``  (default)
    """
    spec_type = param_spec.get("type", "string")
    if value is None:
        return None
    if spec_type == "integer":
        return int(value)
    if spec_type == "float":
        return float(value)
    if spec_type == "boolean":
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes")
    if spec_type == "string_list":
        if isinstance(value, list):
            return [str(v) for v in value]
        # Accept comma-separated strings
        return [v.strip() for v in str(value).split(",") if v.strip()]
    return str(value)


def _resolve_scope_params(
    raw: dict[str, Any],
    scope_params: list[dict],
) -> dict[str, Any]:
    """Merge user-supplied *raw* values with datasource defaults and apply type casts.

    Returns a dict suitable for passing to ``datasource.fetch()`` as ``**kwargs``.
    """
    resolved: dict[str, Any] = {}
    for spec in scope_params:
        name = spec["name"]
        default = spec.get("default")
        value = raw.get(name, default)
        if value is not None:
            resolved[name] = _cast_scope_value(value, spec)
    # Preserve any extra keys the user provided (e.g. undocumented params)
    for k, v in raw.items():
        if k not in resolved:
            resolved[k] = v
    return resolved


class RemoteFetchNode(BaseNode):
    node_id = "remote_fetch"
    display_name = "Remote Data Fetch"
    description = (
        "Fetch data from any registered ingest datasource (e.g. noaa_gsoy, "
        "yields, weather) by supplying its scope parameters as JSON. "
        "Use GET /api/v1/graphs/datasource-info/{key} to see required params."
    )
    category = "Sources"

    inputs: list = []
    outputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]

    class Params(BaseModel):
        datasource_key: str = Field(
            default="noaa_gsoy",
            description=(
                "Key of a registered ingest datasource. "
                "Call GET /api/v1/graphs/datasource-keys to list available keys."
            ),
        )
        scope_params_json: str = Field(
            default="{}",
            description=(
                "JSON object whose keys match the datasource's scope_params. "
                "Omitted keys fall back to the datasource's declared defaults. "
                'Example for noaa_gsoy: {"state":"NC","start_year":2015,"end_year":2020}'
            ),
        )

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        import pandas as pd
        from app.ingest.base import BaseDatasource

        # ------------------------------------------------------------------
        # 1. Resolve datasource
        # ------------------------------------------------------------------
        ds = BaseDatasource._instances.get(params.datasource_key)
        if ds is None:
            known = sorted(BaseDatasource._instances.keys())
            raise ValueError(
                f"RemoteFetchNode: unknown datasource key {params.datasource_key!r}. "
                f"Known keys: {known}"
            )

        # ------------------------------------------------------------------
        # 2. Parse and type-cast scope params
        # ------------------------------------------------------------------
        try:
            raw: dict[str, Any] = json.loads(params.scope_params_json or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"RemoteFetchNode: scope_params_json is not valid JSON: {exc}"
            ) from exc

        resolved = _resolve_scope_params(raw, type(ds).scope_params)
        logger.debug("RemoteFetchNode: resolved scope params for %r: %s", params.datasource_key, resolved)

        # ------------------------------------------------------------------
        # 3. Check result cache (datasource_key + resolved params hash)
        # ------------------------------------------------------------------
        cache_hash = hashlib.sha256(
            json.dumps(
                {"key": params.datasource_key, "params": resolved},
                sort_keys=True,
                default=str,
            ).encode()
        ).hexdigest()[:16]

        cache_dir = Path(_artifacts_base()) / "cache" / "remote"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{params.datasource_key}_{cache_hash}.parquet"

        if cache_file.exists():
            logger.info("RemoteFetchNode: cache hit — loading %s", cache_file)
            return {"dataframe": pd.read_parquet(cache_file)}

        # ------------------------------------------------------------------
        # 4. Call fetch() — pass only params the method actually accepts
        # ------------------------------------------------------------------
        sig = inspect.signature(ds.fetch)
        accepted = set(sig.parameters.keys()) - {"self"}

        # Build kwargs, accepting anything if the signature has **kwargs
        has_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )
        if has_var_keyword:
            fetch_kwargs = resolved
        else:
            fetch_kwargs = {k: v for k, v in resolved.items() if k in accepted}

        logger.info(
            "RemoteFetchNode: calling %s.fetch(%s)",
            params.datasource_key,
            ", ".join(f"{k}={v!r}" for k, v in fetch_kwargs.items()),
        )
        result = ds.fetch(**fetch_kwargs)

        if result is None or (isinstance(result, pd.DataFrame) and result.empty):
            logger.warning("RemoteFetchNode: %s.fetch() returned no data.", params.datasource_key)
            df = pd.DataFrame()
        else:
            df = result if isinstance(result, pd.DataFrame) else pd.DataFrame(result)

        # ------------------------------------------------------------------
        # 5. Persist to local cache
        # ------------------------------------------------------------------
        if not df.empty:
            df.to_parquet(cache_file, index=False)
            logger.info("RemoteFetchNode: cached %d rows → %s", len(df), cache_file)

        return {"dataframe": df}
