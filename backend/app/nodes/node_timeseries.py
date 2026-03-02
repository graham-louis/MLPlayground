"""Time-series modeling nodes.

SARIMAXForecastNode
-------------------
Fits an ARIMA / SARIMAX model on a time-ordered DataFrame, performs an AIC
grid search over (p,d,q) orders, generates a multi-step forecast with
optional exogenous regressors, and returns:

  * ``forecast``     — DataFrame with columns: year, mean, lo_80, hi_80, lo_95, hi_95
  * ``figure``       — base64-encoded PNG (observed history + forecast + shaded bands)
  * ``model_summary``— dict with selected order, AIC, sample size, etc.

Design notes
~~~~~~~~~~~~
* The node distinguishes *training rows* from *future rows* by checking for
  NaN in the ``target_column``.  Upstream nodes should append placeholder
  rows (NaN target, filled exog columns) for the forecast horizon.
* Lazy imports (statsmodels, matplotlib) keep startup time low and allow the
  node to be registered even when those packages are absent at import time.
* ``matplotlib.use("Agg")`` is set lazily inside ``run()`` to avoid
  conflicting with interactive backends in local development.
"""
from __future__ import annotations

import base64
import io
import itertools
import logging
from typing import Any

from pydantic import BaseModel

from app.nodes.base import BaseNode, IOSlot, IOTypes

logger = logging.getLogger(__name__)


class SARIMAXForecastNode(BaseNode):
    node_id = "sarimax_forecaster"
    display_name = "SARIMAX Forecast"
    description = (
        "Fit an ARIMA/SARIMAX model with AIC-based order selection on a "
        "time-series DataFrame.  Outputs a forecast DataFrame, a figure with "
        "prediction intervals, and a model summary dict."
    )
    category = "Modeling"

    inputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]
    outputs = [
        IOSlot(name="forecast", type=IOTypes.DATAFRAME),
        IOSlot(name="figure", type=IOTypes.ARTIFACT),
        IOSlot(name="model_summary", type=IOTypes.ARTIFACT),
    ]

    class Params(BaseModel):
        year_column: str = "year"
        target_column: str = "value"
        exog_columns: list[str] = []
        max_p: int = 3
        max_d: int = 2
        max_q: int = 3
        seasonal: bool = False
        seasonal_period: int = 12
        forecast_steps: int = 0  # 0 = auto-detect from NaN rows
        confidence_levels: list[int] = [80, 95]
        title: str = ""
        auto_d: bool = False
        """When True, run ADF on the training target and constrain d to the
        inferred value instead of grid-searching across all d values."""
        drop_exog_if_incomplete: bool = True
        """When True, silently drop any exog_columns that contain NaN in the
        training rows.  For the forecast step, exog is set to None if any
        future exog values are missing, rather than raising an error."""

    params = Params

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_d(y_train, significance: float = 0.05) -> int:
        """Infer minimum differencing order via sequential ADF tests."""
        from statsmodels.tsa.stattools import adfuller

        def _pval(s) -> float:
            try:
                return float(adfuller(s, autolag="AIC")[1])
            except Exception:
                return 1.0

        import numpy as np
        series = y_train[~np.isnan(y_train)]
        if _pval(series) <= significance:
            return 0
        if _pval(np.diff(series)) <= significance:
            return 1
        return 2

    @staticmethod
    def _fit_best(y, exog_train, orders, seasonal_order, warn_prefix: str,
                  forced_d: int | None = None):
        """Grid-search ARIMA/SARIMAX orders by AIC; return fitted result.

        If *forced_d* is provided the grid is restricted to that single
        differencing value, dramatically reducing the candidate model count.
        """
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        if forced_d is not None:
            orders = [(p, forced_d, q) for (p, _d, q) in orders]
            # deduplicate while preserving order
            seen: set = set()
            orders = [o for o in orders if not (o in seen or seen.add(o))]  # type: ignore[func-returns-value]

        best_aic = float("inf")
        best_res = None
        best_order = None

        for order in orders:
            try:
                mod = SARIMAX(
                    y,
                    exog=exog_train if len(exog_train.columns) > 0 else None,
                    order=order,
                    seasonal_order=seasonal_order,
                    trend="c",
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                )
                res = mod.fit(disp=False, maxiter=200)
                if res.aic < best_aic:
                    best_aic = res.aic
                    best_res = res
                    best_order = order
            except Exception as exc:
                logger.debug("%s order=%s failed: %s", warn_prefix, order, exc)

        if best_res is None:
            raise RuntimeError(
                f"{warn_prefix}: all ARIMA orders failed — check that the "
                "target column has enough non-NaN observations."
            )
        return best_res, best_order, best_aic

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:  # type: ignore[override]
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd

        df: pd.DataFrame = inputs["dataframe"]

        # ---- validate columns ----------------------------------------
        missing_cols = [c for c in [params.year_column, params.target_column] if c not in df.columns]
        if missing_cols:
            raise ValueError(
                f"SARIMAXForecastNode: columns not found in DataFrame: {missing_cols}. "
                f"Available: {list(df.columns)}"
            )

        exog_missing = [c for c in params.exog_columns if c not in df.columns]
        if exog_missing:
            raise ValueError(
                f"SARIMAXForecastNode: exog columns not found: {exog_missing}."
            )

        # ---- sort + split train / future ---------------------------------
        df = df.copy().sort_values(params.year_column).reset_index(drop=True)
        is_future = df[params.target_column].isna()
        train_df = df[~is_future].copy()
        future_df = df[is_future].copy()

        steps = params.forecast_steps if params.forecast_steps > 0 else len(future_df)
        if steps == 0:
            steps = 3  # default fallback

        if len(train_df) < 4:
            raise ValueError(
                f"SARIMAXForecastNode: need at least 4 training rows, "
                f"got {len(train_df)}."
            )

        y_train = train_df[params.target_column].values.astype(float)

        # ---- exog: drop columns with NaN in training rows ---------------
        active_exog = list(params.exog_columns)
        dropped_exog: list[str] = []
        if active_exog and params.drop_exog_if_incomplete:
            clean = []
            for col in active_exog:
                if train_df[col].isna().any():
                    dropped_exog.append(col)
                    logger.warning(
                        "SARIMAXForecastNode: dropping exog '%s' — contains NaN in training rows.",
                        col,
                    )
                else:
                    clean.append(col)
            active_exog = clean

        exog_train = train_df[active_exog] if active_exog else pd.DataFrame()

        exog_future: Any = None
        if active_exog and len(future_df) >= steps:
            future_slice = future_df[active_exog].iloc[:steps]
            if future_slice.isna().any().any():
                logger.warning(
                    "SARIMAXForecastNode: exog has NaN in forecast horizon — "
                    "forecasting without exogenous regressors."
                )
                exog_future = None
                exog_train = pd.DataFrame()
                active_exog = []
            else:
                exog_future = future_slice.values

        # ---- build order grid -------------------------------------------
        prange = range(params.max_p + 1)
        drange = range(params.max_d + 1)
        qrange = range(params.max_q + 1)
        orders = list(itertools.product(prange, drange, qrange))

        seasonal_order = (0, 0, 0, 0)
        if params.seasonal:
            seasonal_order = (1, 1, 1, params.seasonal_period)

        # ---- optionally infer d from ADF --------------------------------
        forced_d: int | None = None
        if params.auto_d:
            forced_d = self._infer_d(y_train)
            logger.info(
                "SARIMAXForecastNode: auto_d=True → ADF recommends d=%d", forced_d
            )

        # ---- fit ---------------------------------------------------------
        result, best_order, best_aic = self._fit_best(
            y_train,
            exog_train,
            orders,
            seasonal_order,
            warn_prefix="SARIMAXForecastNode",
            forced_d=forced_d,
        )

        # ---- forecast ----------------------------------------------------
        fc = result.get_forecast(steps=steps, exog=exog_future)
        fc_mean = fc.predicted_mean

        # future year labels
        last_train_year = int(train_df[params.year_column].iloc[-1])
        if len(future_df) >= steps:
            fc_years = future_df[params.year_column].iloc[:steps].values
        else:
            fc_years = np.arange(last_train_year + 1, last_train_year + 1 + steps)

        # confidence intervals
        ci_bands: dict[str, Any] = {}
        for level in params.confidence_levels:
            alpha = 1.0 - level / 100.0
            ci = fc.conf_int(alpha=alpha)
            lo_col, hi_col = ci.columns[0], ci.columns[1]
            ci_bands[f"lo_{level}"] = ci[lo_col].values
            ci_bands[f"hi_{level}"] = ci[hi_col].values

        # ---- assemble forecast DataFrame ---------------------------------
        forecast_rec: dict[str, Any] = {
            params.year_column: fc_years,
            "mean": fc_mean.values,
        }
        forecast_rec.update(ci_bands)
        forecast_df = pd.DataFrame(forecast_rec)

        # ---- figure ------------------------------------------------------
        train_years = train_df[params.year_column].values
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(train_years, y_train, "o-", color="#1f77b4", label="Observed", linewidth=2)
        ax.plot(fc_years, fc_mean.values, "s--", color="#ff7f0e", label="Forecast", linewidth=2)

        # shade confidence bands (darkest innermost)
        band_colors = ["#ff7f0e", "#ffbb78"]
        for i, level in enumerate(sorted(params.confidence_levels, reverse=True)):
            if f"lo_{level}" in forecast_rec:
                lo = np.array(ci_bands[f"lo_{level}"])
                hi = np.array(ci_bands[f"hi_{level}"])
                color = band_colors[i % len(band_colors)]
                ax.fill_between(fc_years, lo, hi, alpha=0.25, color=color, label=f"{level}% CI")

        title = params.title or f"SARIMAX Forecast — order={best_order}"
        ax.set_title(title, fontsize=13)
        ax.set_xlabel(params.year_column.capitalize())
        ax.set_ylabel(params.target_column)
        ax.legend(loc="upper left", fontsize=9)
        ax.grid(True, linestyle="--", alpha=0.4)
        fig.tight_layout()

        buf = io.BytesIO()
        try:
            fig.savefig(buf, format="png", dpi=120)
            buf.seek(0)
            img_b64 = base64.b64encode(buf.read()).decode("utf-8")
        finally:
            plt.close(fig)
            buf.close()

        figure_out = {"__type__": "figure", "data": img_b64, "format": "png"}

        # ---- model summary -----------------------------------------------
        model_summary = {
            "order": list(best_order),
            "seasonal_order": list(seasonal_order),
            "aic": round(float(best_aic), 4),
            "n_train": int(len(train_df)),
            "n_forecast": int(steps),
            "exog_columns": active_exog,
            "dropped_exog": dropped_exog,
            "auto_d_used": params.auto_d,
            "forced_d": forced_d,
        }

        logger.info(
            "SARIMAXForecastNode: order=%s AIC=%.2f n_train=%d n_forecast=%d",
            best_order, best_aic, len(train_df), steps,
        )

        return {
            "forecast": forecast_df,
            "figure": figure_out,
            "model_summary": model_summary,
        }
