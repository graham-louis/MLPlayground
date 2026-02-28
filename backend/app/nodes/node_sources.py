from app.nodes.base import BaseNode, IOTypes, IOSlot
from pydantic import BaseModel
from typing import Any

class CsvSourceNode(BaseNode):
    node_id = "csv_source"
    display_name = "CSV Source Node"
    description = "Node that reads data from a CSV file and outputs a DataFrame."
    category = "Sources"

    outputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]

    # Parameters for the node, such as the file path to read from
    class Params(BaseModel):
        file_path: str
        separator: str = ","
        encoding: str = "utf-8"
    
    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        import pandas as pd
        
        try:
            df = pd.read_csv(params.file_path, sep=params.separator, encoding=params.encoding)
            return {"dataframe": df}
        except Exception as e:
            raise RuntimeError(f"Failed to read CSV file at {params.file_path}: {e}")


class ParquetSourceNode(BaseNode):
    node_id = "parquet_source"
    display_name = "Parquet Source"
    description = "Read a Parquet file from disk into a DataFrame."
    category = "Sources"

    outputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]

    class Params(BaseModel):
        file_path: str

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        import pandas as pd
        try:
            df = pd.read_parquet(params.file_path)
            return {"dataframe": df}
        except Exception as exc:
            raise RuntimeError(f"Failed to read Parquet file at {params.file_path}: {exc}")


class DatabaseSourceNode(BaseNode):
    node_id = "database_source"
    display_name = "Database Source"
    description = (
        "Query any registered datasource (yields, weather, soil, etc.) "
        "and return the results as a DataFrame. Select a datasource key, "
        "then set optional column filters in the inspector."
    )
    category = "Sources"

    outputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]

    class Params(BaseModel):
        datasource_key: str = ""
        filters_json: str = "{}"
        limit: int = 50000

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        import json
        import pandas as pd
        from app.ingest.base import BaseDatasource

        ds = BaseDatasource._instances.get(params.datasource_key)
        if ds is None:
            known = list(BaseDatasource._instances.keys())
            raise ValueError(
                f"Unknown datasource key: {params.datasource_key!r}. Known: {known}"
            )

        # Parse generic filters and pass only what this datasource's query() accepts
        try:
            filters: dict[str, Any] = json.loads(params.filters_json or "{}")
        except json.JSONDecodeError:
            filters = {}

        import inspect
        import typing
        sig = inspect.signature(ds.query)
        accepted = set(sig.parameters.keys())
        # Resolve string annotations (from `from __future__ import annotations`) to real types
        try:
            hints = typing.get_type_hints(ds.query)
        except Exception:
            hints = {}
        kwargs: dict[str, Any] = {"limit": params.limit}
        for col, val in filters.items():
            if col not in accepted or val in (None, ""):
                continue
            # Unwrap Optional[T] -> T, then cast
            hint = hints.get(col)
            if hint is not None:
                type_args = typing.get_args(hint)
                inner_type = next((a for a in type_args if a is not type(None)), hint) if type_args else hint
                try:
                    val = inner_type(val)
                except (TypeError, ValueError):
                    pass  # keep as string if cast fails
            kwargs[col] = val

        rows, _ = ds.query(**kwargs)
        return {"dataframe": pd.DataFrame(rows)}
