"""Diagnostic nodes — statistical tests and visualisations.

StationarityTestNode
--------------------
Runs the Augmented Dickey-Fuller (ADF) and KPSS unit-root tests on a
single column of a time-series DataFrame.  Outputs:

  * ``result``  — DataFrame with one row per test: test name, statistic,
                  p-value, is_stationary flag, and a recommended
                  differencing order ``recommended_d``.
  * ``figure``  — base64-encoded PNG with side-by-side ACF and PACF plots
                  to help diagnose lag structure.

Design notes
~~~~~~~~~~~~
* Lazy imports (statsmodels, matplotlib) keep startup time low.
* ``matplotlib.use("Agg")`` is set lazily inside ``run()`` to avoid
  conflicting with interactive backends in local development.
* The node is auto-discovered via the ``node_*.py`` glob in
  ``app/api/main.py`` — no registration changes required.
"""
from __future__ import annotations

import base64
import io
import logging
from typing import Any

from pydantic import BaseModel

from app.nodes.base import BaseNode, IOSlot, IOTypes

logger = logging.getLogger(__name__)


class StationarityTestNode(BaseNode):
    node_id = "stationarity_test"
    display_name = "Stationarity Test"
    description = (
        "Run ADF and KPSS unit-root tests on a time-series column and plot "
        "ACF / PACF to diagnose lag structure. Outputs a result DataFrame and "
        "a diagnostic figure. Connect upstream of SARIMAX to decide differencing order."
    )
    category = "Diagnostics"

    inputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]
    outputs = [
        IOSlot(name="result", type=IOTypes.DATAFRAME),
        IOSlot(name="figure", type=IOTypes.ARTIFACT),
    ]

    class Params(BaseModel):
        column: str
        max_lags: int = 12
        significance: float = 0.05

    params = Params

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _recommended_d(series, significance: float) -> int:
        """Infer minimum differencing order via sequential ADF tests."""
        from statsmodels.tsa.stattools import adfuller

        def _adf_pval(s) -> float:
            try:
                return float(adfuller(s.dropna(), autolag="AIC")[1])
            except Exception:
                return 1.0

        if _adf_pval(series) <= significance:
            return 0
        if _adf_pval(series.diff().dropna()) <= significance:
            return 1
        return 2

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:  # type: ignore[override]
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import pandas as pd
        from statsmodels.tsa.stattools import adfuller, kpss
        from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

        df: pd.DataFrame = inputs["dataframe"]

        if params.column not in df.columns:
            raise ValueError(
                f"StationarityTestNode: column '{params.column}' not found. "
                f"Available: {list(df.columns)}"
            )

        series = df[params.column].dropna().reset_index(drop=True)

        if len(series) < 8:
            raise ValueError(
                f"StationarityTestNode: need at least 8 non-NaN observations, "
                f"got {len(series)}."
            )

        # ── ADF test ──────────────────────────────────────────────────
        adf_stat, adf_p, _, _, adf_crit, _ = adfuller(series, autolag="AIC")
        adf_stationary = bool(adf_p <= params.significance)

        # ── KPSS test ─────────────────────────────────────────────────
        # KPSS null = stationary; reject → non-stationary
        try:
            kpss_stat, kpss_p, _, kpss_crit = kpss(series, regression="c", nlags="auto")
            kpss_stationary = bool(kpss_p > params.significance)
        except Exception as exc:
            logger.warning("StationarityTestNode: KPSS failed: %s", exc)
            kpss_stat, kpss_p, kpss_crit = float("nan"), float("nan"), {}
            kpss_stationary = False

        recommended_d = self._recommended_d(series, params.significance)

        result_df = pd.DataFrame([
            {
                "test": "ADF",
                "statistic": round(float(adf_stat), 6),
                "p_value": round(float(adf_p), 6),
                "critical_values": str({k: round(v, 4) for k, v in adf_crit.items()}),
                "is_stationary": adf_stationary,
                "recommended_d": recommended_d,
            },
            {
                "test": "KPSS",
                "statistic": round(float(kpss_stat), 6),
                "p_value": round(float(kpss_p), 6),
                "critical_values": str({k: round(v, 4) for k, v in kpss_crit.items()}),
                "is_stationary": kpss_stationary,
                "recommended_d": recommended_d,
            },
        ])

        # ── ACF / PACF figure ─────────────────────────────────────────
        n_lags = min(params.max_lags, len(series) // 2 - 1)
        fig, axes = plt.subplots(1, 2, figsize=(12, 4))

        plot_acf(series, lags=n_lags, ax=axes[0], title=f"ACF — {params.column}")
        plot_pacf(series, lags=n_lags, ax=axes[1], method="ywm",
                  title=f"PACF — {params.column}")

        adf_label = f"ADF p={adf_p:.3f} ({'stationary' if adf_stationary else 'non-stationary'})"
        kpss_label = f"KPSS p={kpss_p:.3f} ({'stationary' if kpss_stationary else 'non-stationary'})"
        fig.suptitle(
            f"{params.column} — {adf_label}  |  {kpss_label}  |  recommended_d={recommended_d}",
            fontsize=10,
        )
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

        logger.info(
            "StationarityTestNode: col=%r ADF_p=%.4f KPSS_p=%.4f recommended_d=%d",
            params.column, adf_p, kpss_p, recommended_d,
        )

        return {"result": result_df, "figure": figure_out}
