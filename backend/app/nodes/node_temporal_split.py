"""Temporal Split node — split a DataFrame into train / test / holdout by year.

Unlike the random ``SplitNode``, this node keeps year-groups intact so that
no single calendar year's rows are divided across splits.  This is the correct
strategy for time-series data where future-leakage would inflate apparent
model performance.

Usage
-----
* Connect any DataFrame that has a numeric year column (or a datetime index
  that will be used to derive a year column).
* Configure ``date_column`` to the name of the year column (integer, e.g. 2019)
  or a datetime column (in which case the year is extracted automatically).
* Specify ``test_years`` and ``holdout_years`` as JSON arrays, e.g.
  ``[2019, 2021]`` and ``[2022, 2023]``.
* All remaining years flow out of the ``train`` port.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from app.nodes.base import BaseNode, IOSlot, IOTypes

logger = logging.getLogger(__name__)


class TemporalSplitNode(BaseNode):
    node_id = "temporal_split"
    display_name = "Temporal Split"
    description = (
        "Split a DataFrame into train / test / holdout sets by year. "
        "Year groups are kept intact — no single year's rows are divided "
        "across splits.  Remaining years (not in test or holdout) become "
        "the training set."
    )
    category = "Transforms"

    inputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]
    outputs = [
        IOSlot(name="train",   type=IOTypes.DATAFRAME),
        IOSlot(name="test",    type=IOTypes.DATAFRAME),
        IOSlot(name="holdout", type=IOTypes.DATAFRAME),
    ]

    class Params(BaseModel):
        date_column: str = Field(
            default="date",
            description=(
                "Column containing year values (int) or datetime values. "
                "If the column has dtype datetime64, the year is extracted "
                "automatically.  If left blank, the DataFrame index is used."
            ),
        )
        test_years: list[int] = Field(
            default=[2019, 2021],
            description="Years to include in the test (validation) split.",
        )
        holdout_years: list[int] = Field(
            default=[2022, 2023],
            description="Years to reserve as the held-out final evaluation split.",
        )

    params = Params

    # ------------------------------------------------------------------
    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        df: pd.DataFrame = inputs["dataframe"].copy()

        # ── Derive a working "year" column ──────────────────────────────
        year_col = "__year__"

        if params.date_column and params.date_column in df.columns:
            col = df[params.date_column]
            if pd.api.types.is_datetime64_any_dtype(col):
                df[year_col] = col.dt.year
            else:
                df[year_col] = col.astype(int)
        elif params.date_column == "" or params.date_column not in df.columns:
            # Fall back to the DataFrame index if it looks like a datetime
            if isinstance(df.index, pd.DatetimeIndex):
                df[year_col] = df.index.year
            elif "year" in df.columns:
                df[year_col] = df["year"].astype(int)
            else:
                raise ValueError(
                    "TemporalSplitNode: could not determine a year column. "
                    f"Tried '{params.date_column}'; available columns: {list(df.columns)}"
                )

        available_years = sorted(df[year_col].unique().tolist())
        test_set    = set(params.test_years)
        holdout_set = set(params.holdout_years)
        overlap = test_set & holdout_set
        if overlap:
            raise ValueError(
                f"TemporalSplitNode: years {sorted(overlap)} appear in both "
                "test_years and holdout_years."
            )

        train_years = [y for y in available_years if y not in test_set and y not in holdout_set]

        if not train_years:
            raise ValueError(
                "TemporalSplitNode: no years remain for training after removing "
                f"test={sorted(test_set)} and holdout={sorted(holdout_set)}. "
                f"Available years: {available_years}"
            )

        train_df   = df[df[year_col].isin(train_years)].drop(columns=[year_col])
        test_df    = df[df[year_col].isin(test_set)].drop(columns=[year_col])
        holdout_df = df[df[year_col].isin(holdout_set)].drop(columns=[year_col])

        logger.info(
            "TemporalSplitNode: train=%d rows (%s), test=%d rows (%s), holdout=%d rows (%s)",
            len(train_df),   sorted(train_years),
            len(test_df),    sorted(test_set),
            len(holdout_df), sorted(holdout_set),
        )

        return {
            "train":   train_df,
            "test":    test_df,
            "holdout": holdout_df,
        }
