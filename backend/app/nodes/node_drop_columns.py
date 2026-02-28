"""Drop Columns node — remove named columns from a DataFrame.

Simple stateless transform: receives a list of column names to drop.
The column toggles in the inspector are populated automatically from the
upstream run result (the ColumnToggleSelect component in the frontend).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.nodes.base import BaseNode, IOSlot, IOTypes


class DropColumnsNode(BaseNode):
    node_id = "drop_columns"
    display_name = "Drop Columns"
    description = (
        "Remove one or more columns from a DataFrame. "
        "Select columns to drop using the toggle buttons in the inspector "
        "(run the graph once to populate the list automatically)."
    )
    category = "Transforms"

    inputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]
    outputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]

    class Params(BaseModel):
        columns: list[str] = []

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        import pandas as pd

        df: pd.DataFrame = inputs["dataframe"]
        if not params.columns:
            return {"dataframe": df}
        missing = [c for c in params.columns if c not in df.columns]
        if missing:
            raise ValueError(
                f"DropColumnsNode: columns not found: {missing}. "
                f"Available: {list(df.columns)}"
            )
        return {"dataframe": df.drop(columns=params.columns).reset_index(drop=True)}
