"""Utility nodes — split, preview, save/load artifacts, and cache checkpoints.

These nodes handle the plumbing of a pipeline rather than data transformation
or model training.  They are intentionally thin wrappers around well-known
library functions.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Literal

from pydantic import BaseModel

from app.nodes.base import BaseNode, IOSlot, IOTypes

logger = logging.getLogger(__name__)

ARTIFACTS_BASE: str = os.environ.get("ARTIFACTS_BASE", "/app/artifacts")


class SplitNode(BaseNode):
    node_id = "split"
    display_name = "Split"
    description = "Split a DataFrame into training and test sets."
    category = "Utilities"

    inputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]
    outputs = [
        IOSlot(name="train", type=IOTypes.DATAFRAME),
        IOSlot(name="test", type=IOTypes.DATAFRAME),
    ]

    class Params(BaseModel):
        test_size: float = 0.2
        random_state: int = 42
        stratify_column: str = ""  # optional — column to stratify on

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        from sklearn.model_selection import train_test_split

        df = inputs["dataframe"]
        stratify = df[params.stratify_column] if params.stratify_column else None
        train_df, test_df = train_test_split(
            df,
            test_size=params.test_size,
            random_state=params.random_state,
            stratify=stratify,
        )
        return {
            "train": train_df.reset_index(drop=True),
            "test": test_df.reset_index(drop=True),
        }


class PreviewNode(BaseNode):
    node_id = "preview"
    display_name = "Preview"
    description = (
        "Pass a DataFrame through unchanged and emit the first N rows as a JSON "
        "list for inline display in the UI."
    )
    category = "Utilities"

    inputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]
    outputs = [
        IOSlot(name="dataframe", type=IOTypes.DATAFRAME),
        IOSlot(name="preview", type=IOTypes.ARTIFACT),
    ]

    class Params(BaseModel):
        rows: int = 20

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        df = inputs["dataframe"]
        preview = {
            "rows": df.head(params.rows).to_dict(orient="records"),
            "columns": list(df.columns),
        }
        return {"dataframe": df, "preview": preview}


class SaveArtifactNode(BaseNode):
    node_id = "save_artifact"
    display_name = "Save Artifact"
    description = "Save a DataFrame to disk as CSV or Parquet and return the file path."
    category = "Utilities"

    inputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]
    outputs = [IOSlot(name="artifact_path", type=IOTypes.ARTIFACT)]

    class Params(BaseModel):
        name: str = "output"
        format: Literal["csv", "parquet"] = "parquet"

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        df = inputs["dataframe"]
        out_dir = os.path.join(ARTIFACTS_BASE, "exports")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{params.name}.{params.format}")
        if params.format == "csv":
            df.to_csv(path, index=False)
        else:
            df.to_parquet(path, index=False)
        return {"artifact_path": path}


class LoadArtifactNode(BaseNode):
    node_id = "load_artifact"
    display_name = "Load Artifact"
    description = "Load a previously saved DataFrame artifact (CSV or Parquet) from disk."
    category = "Utilities"

    outputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]

    class Params(BaseModel):
        artifact_path: str

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        import pandas as pd

        if not os.path.exists(params.artifact_path):
            raise FileNotFoundError(
                f"LoadArtifactNode: artifact not found at '{params.artifact_path}'."
            )
        if params.artifact_path.endswith(".parquet"):
            df = pd.read_parquet(params.artifact_path)
        else:
            df = pd.read_csv(params.artifact_path)
        return {"dataframe": df}


class PredictNode(BaseNode):
    node_id = "predict"
    display_name = "Predict"
    description = "Run inference on a DataFrame using a fitted model."
    category = "Utilities"

    inputs = [
        IOSlot(name="dataframe", type=IOTypes.DATAFRAME),
        IOSlot(name="model", type=IOTypes.MODEL),
    ]
    outputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]

    class Params(BaseModel):
        feature_columns: list[str] = []
        output_column: str = "prediction"

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        import pandas as pd

        df = inputs["dataframe"].copy()
        model = inputs["model"]

        feature_cols = params.feature_columns or list(
            df.select_dtypes(include="number").columns
        )
        X = df[feature_cols].values
        df[params.output_column] = model.predict(X)
        return {"dataframe": df}
