"""Plot node — turns a DataFrame into a base64-encoded PNG figure.

Supported plot types: scatter, line, histogram, bar, box.

The output slot ``figure`` contains a dict:
    {"__type__": "figure", "data": "<base64-png>", "format": "png"}

The executor passes this dict through to the result JSON as-is (it is
already JSON-serialisable and does not need to be written to disk).

Design:
  * All matplotlib calls happen inside ``run()`` so the module can be imported
    on a headless server without display issues (``Agg`` backend is set lazily
    inside ``run()``).
  * The node is intentionally stateless: the same params + inputs always produce
    the same figure (useful for caching).
"""
from __future__ import annotations

import base64
import io
from typing import Any, Literal

from pydantic import BaseModel

from app.nodes.base import BaseNode, IOSlot, IOTypes


class PlotNode(BaseNode):
    node_id = "plot"
    display_name = "Plot"
    description = (
        "Generate a chart from an upstream DataFrame. "
        "Choose plot type, x/y columns, and an optional colour-grouping column. "
        "Outputs a base64-encoded PNG figure rendered inline in the UI."
    )
    category = "Visualization"

    inputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]
    outputs = [IOSlot(name="figure", type=IOTypes.ARTIFACT)]

    class Params(BaseModel):
        plot_type: Literal["scatter", "line", "histogram", "bar", "box"] = "scatter"
        x_column: str = ""
        y_column: str = ""
        color_column: str = ""   # optional grouping / hue column
        title: str = ""

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        import matplotlib
        matplotlib.use("Agg")  # non-interactive, safe on headless servers
        import matplotlib.pyplot as plt
        import pandas as pd

        df: pd.DataFrame = inputs["dataframe"]
        fig, ax = plt.subplots(figsize=(8, 5))
        title = params.title or params.plot_type.capitalize()

        try:
            if params.plot_type == "scatter":
                if not params.x_column or not params.y_column:
                    raise ValueError("scatter plot requires x_column and y_column")
                if params.color_column and params.color_column in df.columns:
                    for name, grp in df.groupby(params.color_column):
                        ax.scatter(grp[params.x_column], grp[params.y_column],
                                   label=str(name), alpha=0.6, s=15)
                    ax.legend(fontsize=7, loc="best")
                else:
                    ax.scatter(df[params.x_column], df[params.y_column],
                               alpha=0.6, s=15)
                ax.set_xlabel(params.x_column)
                ax.set_ylabel(params.y_column)

            elif params.plot_type == "line":
                if not params.x_column or not params.y_column:
                    raise ValueError("line plot requires x_column and y_column")
                if params.color_column and params.color_column in df.columns:
                    for name, grp in df.groupby(params.color_column):
                        grp_s = grp.sort_values(params.x_column)
                        ax.plot(grp_s[params.x_column], grp_s[params.y_column],
                                label=str(name), alpha=0.8)
                    ax.legend(fontsize=7)
                else:
                    df_s = df.sort_values(params.x_column)
                    ax.plot(df_s[params.x_column], df_s[params.y_column], alpha=0.8)
                ax.set_xlabel(params.x_column)
                ax.set_ylabel(params.y_column)

            elif params.plot_type == "histogram":
                col = params.x_column or params.y_column
                if not col:
                    raise ValueError("histogram requires x_column")
                ax.hist(df[col].dropna(), bins=30, edgecolor="white")
                ax.set_xlabel(col)
                ax.set_ylabel("Count")

            elif params.plot_type == "bar":
                if not params.x_column or not params.y_column:
                    raise ValueError("bar plot requires x_column and y_column")
                series = (
                    df.groupby(params.x_column)[params.y_column]
                    .mean()
                    .sort_values(ascending=False)
                    .head(20)
                )
                ax.bar(series.index.astype(str), series.values)
                ax.set_xlabel(params.x_column)
                ax.set_ylabel(f"mean({params.y_column})")
                plt.xticks(rotation=45, ha="right")

            elif params.plot_type == "box":
                col = params.y_column or params.x_column
                if not col:
                    raise ValueError("box plot requires y_column")
                if (params.x_column and params.x_column in df.columns
                        and params.x_column != col):
                    cats = df[params.x_column].unique()[:12]
                    data = [
                        df[df[params.x_column] == c][col].dropna().values
                        for c in cats
                    ]
                    ax.boxplot(data, labels=[str(c) for c in cats])
                    ax.set_xlabel(params.x_column)
                    plt.xticks(rotation=45, ha="right")
                else:
                    ax.boxplot(df[col].dropna().values)
                ax.set_ylabel(col)

            ax.set_title(title)
            fig.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=100)
            buf.seek(0)
            data = base64.b64encode(buf.read()).decode("utf-8")
            return {"figure": {"__type__": "figure", "data": data, "format": "png"}}

        finally:
            plt.close(fig)
