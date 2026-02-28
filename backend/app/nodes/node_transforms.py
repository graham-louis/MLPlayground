"""Transform nodes — stateless DataFrame operations.

All transform nodes follow the same contract:
  input  slot "dataframe"  → a pandas DataFrame
  output slot "dataframe"  → the transformed DataFrame

Keeping them stateless (no side effects, no global reads) makes them
cacheable and independently testable.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

import pandas as pd
from pydantic import BaseModel

from app.nodes.base import BaseNode, IOSlot, IOTypes


class FilterNode(BaseNode):
    node_id = "filter"
    display_name = "Filter"
    description = "Filter rows where column satisfies a comparison condition."
    category = "Transforms"

    inputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]
    outputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]

    class Params(BaseModel):
        column: str
        operator: Literal["==", "!=", ">", "<", ">=", "<="]
        value: Any

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        df: pd.DataFrame = inputs["dataframe"]
        if params.column not in df.columns:
            raise ValueError(
                f"FilterNode: column '{params.column}' not found. "
                f"Available: {list(df.columns)}"
            )
        ops = {
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">":  lambda a, b: a > b,
            "<":  lambda a, b: a < b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
        }
        # Try to cast value to the column's dtype
        val = params.value
        col_series = df[params.column]
        try:
            val = pd.Series([val]).astype(col_series.dtype).iloc[0]
        except (ValueError, TypeError):
            pass  # keep as is if cast fails

        mask = ops[params.operator](col_series, val)
        return {"dataframe": df[mask].reset_index(drop=True)}


class JoinNode(BaseNode):
    node_id = "join"
    display_name = "Join"
    description = "Merge two DataFrames on one or more key columns."
    category = "Transforms"

    inputs = [
        IOSlot(name="left", type=IOTypes.DATAFRAME),
        IOSlot(name="right", type=IOTypes.DATAFRAME),
    ]
    outputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]

    class Params(BaseModel):
        on: list[str]
        how: Literal["inner", "left", "right", "outer"] = "inner"

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        left: pd.DataFrame = inputs["left"]
        right: pd.DataFrame = inputs["right"]
        missing_left = [c for c in params.on if c not in left.columns]
        missing_right = [c for c in params.on if c not in right.columns]
        if missing_left:
            raise ValueError(f"JoinNode: key columns {missing_left} not in left DataFrame.")
        if missing_right:
            raise ValueError(f"JoinNode: key columns {missing_right} not in right DataFrame.")
        merged = pd.merge(left, right, on=params.on, how=params.how)
        return {"dataframe": merged}


class GroupByNode(BaseNode):
    node_id = "group_by"
    display_name = "Group By"
    description = "Group rows by one or more columns and aggregate with specified functions."
    category = "Transforms"

    inputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]
    outputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]

    class Params(BaseModel):
        group_columns: list[str]
        # Maps column name → aggregation function name ("mean", "sum", "min", "max", "count")
        aggregations: dict[str, str]

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        df: pd.DataFrame = inputs["dataframe"]
        result = df.groupby(params.group_columns).agg(params.aggregations).reset_index()
        # Flatten multi-level columns produced by some aggregation combos
        if isinstance(result.columns, pd.MultiIndex):
            result.columns = ["_".join(c).strip("_") for c in result.columns]
        return {"dataframe": result}


class ImputeNode(BaseNode):
    node_id = "impute"
    display_name = "Impute"
    description = "Fill missing values in numeric columns using mean, median, or a constant."
    category = "Transforms"

    inputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]
    outputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]

    class Params(BaseModel):
        strategy: Literal["mean", "median", "constant"] = "mean"
        fill_value: float = 0.0  # used only when strategy == "constant"
        columns: list[str] = []  # empty = all numeric columns

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        df = inputs["dataframe"].copy()
        cols = params.columns or list(df.select_dtypes(include="number").columns)
        for col in cols:
            if col not in df.columns:
                continue
            if params.strategy == "mean":
                df[col] = df[col].fillna(df[col].mean())
            elif params.strategy == "median":
                df[col] = df[col].fillna(df[col].median())
            else:
                df[col] = df[col].fillna(params.fill_value)
        return {"dataframe": df}


class EncodeNode(BaseNode):
    node_id = "encode"
    display_name = "Encode"
    description = "Encode categorical columns using label encoding or one-hot encoding."
    category = "Transforms"

    inputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]
    outputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]

    class Params(BaseModel):
        columns: list[str]
        method: Literal["label", "onehot"] = "label"

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        df = inputs["dataframe"].copy()
        if params.method == "onehot":
            df = pd.get_dummies(df, columns=params.columns)
        else:
            from sklearn.preprocessing import LabelEncoder
            le = LabelEncoder()
            for col in params.columns:
                if col in df.columns:
                    df[col] = le.fit_transform(df[col].astype(str))
        return {"dataframe": df}


class ScaleNode(BaseNode):
    node_id = "scale"
    display_name = "Scale"
    description = "Scale numeric columns using standard scaling (z-score) or min-max normalization."
    category = "Transforms"

    inputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]
    outputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]

    class Params(BaseModel):
        columns: list[str] = []  # empty = all numeric columns
        method: Literal["standard", "minmax"] = "standard"

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        from sklearn.preprocessing import MinMaxScaler, StandardScaler

        df = inputs["dataframe"].copy()
        cols = params.columns or list(df.select_dtypes(include="number").columns)
        scaler = StandardScaler() if params.method == "standard" else MinMaxScaler()
        df[cols] = scaler.fit_transform(df[cols].fillna(0))
        return {"dataframe": df}


class SelectColumnsNode(BaseNode):
    node_id = "select_columns"
    display_name = "Select Columns"
    description = "Keep only the specified columns in a DataFrame."
    category = "Transforms"

    inputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]
    outputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]

    class Params(BaseModel):
        columns: list[str]

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        df: pd.DataFrame = inputs["dataframe"]
        missing = [c for c in params.columns if c not in df.columns]
        if missing:
            raise ValueError(f"SelectColumnsNode: columns not found: {missing}")
        return {"dataframe": df[params.columns].copy()}


class DropNaNode(BaseNode):
    node_id = "drop_na"
    display_name = "Drop NA"
    description = "Remove rows that contain any null values (or nulls in specific columns)."
    category = "Transforms"

    inputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]
    outputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]

    class Params(BaseModel):
        columns: list[str] = []  # empty = check all columns

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        df: pd.DataFrame = inputs["dataframe"]
        subset = params.columns or None
        return {"dataframe": df.dropna(subset=subset).reset_index(drop=True)}
