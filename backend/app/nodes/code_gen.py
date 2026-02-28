"""Standalone Python code generators for each node type.

Each generator produces a list of source-code lines (strings, no trailing
newlines) that implement the node's logic using standard libraries only —
no ``app.nodes.*`` imports are used.  The generated lines are assembled by
``graphs.py:_generate_standalone_script()`` into a complete runnable script.

Public API
----------
generate_node_code(node_type, params, input_refs, output_var, display_name, step)
    Returns ``(imports: set[str], body_lines: list[str])``.

``input_refs``  maps slot name → Python expression for the upstream variable.
``output_var``  is the base variable name for this node, e.g. ``"_nd_node_3"``.
"""
from __future__ import annotations

import json
import re
from typing import Any

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _r(v: Any) -> str:
    """repr() shortcut."""
    return repr(v)


def _ivar(output_var: str, slot: str) -> str:
    """Output variable name for a specific slot, e.g. `_nd_node_3__dataframe`."""
    return f"{output_var}__{slot}"


# ---------------------------------------------------------------------------
# Individual generators
# (each returns (extra_imports: set[str], lines: list[str]))
# ---------------------------------------------------------------------------

def _gen_csv_source(p: dict, inp: dict, ov: str) -> tuple[set, list]:
    path = p.get("file_path", "data.csv")
    sep = p.get("separator", ",")
    enc = p.get("encoding", "utf-8")
    out = _ivar(ov, "dataframe")
    return (
        {"import pandas as pd"},
        [
            f"{out} = pd.read_csv({_r(path)}, sep={_r(sep)}, encoding={_r(enc)})",
        ],
    )


def _gen_parquet_source(p: dict, inp: dict, ov: str) -> tuple[set, list]:
    path = p.get("file_path", "data.parquet")
    out = _ivar(ov, "dataframe")
    return (
        {"import pandas as pd"},
        [f"{out} = pd.read_parquet({_r(path)})"],
    )


def _gen_database_source(p: dict, inp: dict, ov: str) -> tuple[set, list]:
    dskey = p.get("datasource_key", "")
    filters = p.get("filters_json", "{}")
    limit = p.get("limit", 50000)
    out = _ivar(ov, "dataframe")
    return (
        {"import pandas as pd", "import requests"},
        [
            f"# DatabaseSource: fetch '{dskey}' via the MLPlayground API",
            f"_ds_resp = requests.get(",
            f"    \"http://localhost:8000/api/v1/graphs/datasource-info/{dskey}\",",
            f"    params={{\"limit\": {limit}, **{filters}}},",
            f"    timeout=60,",
            f")",
            f"_ds_resp.raise_for_status()",
            f"# Alternatively, query your DB directly and load into a DataFrame.",
            f"# Replace the line below with your actual data loading logic.",
            f"{out} = pd.DataFrame(_ds_resp.json())  # adjust as needed",
        ],
    )


def _gen_remote_fetch(p: dict, inp: dict, ov: str) -> tuple[set, list]:
    dskey = p.get("datasource_key", "")
    scope_raw = p.get("scope_params_json", "{}")
    out = _ivar(ov, "dataframe")
    try:
        scope = json.loads(scope_raw) if scope_raw else {}
    except Exception:
        scope = {}
    return (
        {"import pandas as pd", "import requests"},
        [
            f"# RemoteFetch: call datasource '{dskey}' with scope params",
            f"_rf_resp = requests.post(",
            f"    \"http://localhost:8000/api/v1/ingest/fetch\",",
            f"    json={{\"datasource_key\": {_r(dskey)}, \"scope_params\": {_r(scope)}}},",
            f"    timeout=120,",
            f")",
            f"_rf_resp.raise_for_status()",
            f"{out} = pd.DataFrame(_rf_resp.json())",
        ],
    )


def _gen_filter(p: dict, inp: dict, ov: str) -> tuple[set, list]:
    df_in = inp.get("dataframe", "None")
    col = p.get("column", "col")
    op = p.get("operator", "==")
    val = p.get("value", 0)
    out = _ivar(ov, "dataframe")
    # Build the mask expression
    if op == "==":
        mask = f"{df_in}[{_r(col)}] == {_r(val)}"
    elif op == "!=":
        mask = f"{df_in}[{_r(col)}] != {_r(val)}"
    elif op == ">":
        mask = f"{df_in}[{_r(col)}] > {_r(val)}"
    elif op == "<":
        mask = f"{df_in}[{_r(col)}] < {_r(val)}"
    elif op == ">=":
        mask = f"{df_in}[{_r(col)}] >= {_r(val)}"
    elif op == "<=":
        mask = f"{df_in}[{_r(col)}] <= {_r(val)}"
    else:
        mask = f"{df_in}[{_r(col)}] == {_r(val)}"
    return (
        set(),
        [f"{out} = {df_in}[{mask}].reset_index(drop=True)"],
    )


def _gen_join(p: dict, inp: dict, ov: str) -> tuple[set, list]:
    left = inp.get("left", "None")
    right = inp.get("right", "None")
    on = p.get("on", [])
    how = p.get("how", "inner")
    out = _ivar(ov, "dataframe")
    return (
        set(),
        [f"{out} = {left}.merge({right}, on={_r(on)}, how={_r(how)})"],
    )


def _gen_group_by(p: dict, inp: dict, ov: str) -> tuple[set, list]:
    df_in = inp.get("dataframe", "None")
    gcols = p.get("group_columns", [])
    aggs = p.get("aggregations", {})
    out = _ivar(ov, "dataframe")
    lines = [
        f"{out} = {df_in}.groupby({_r(gcols)}).agg({_r(aggs)}).reset_index()",
        f"if hasattr({out}.columns, 'levels'):  # flatten MultiIndex",
        f"    {out}.columns = ['_'.join(c).strip('_') for c in {out}.columns]",
    ]
    return set(), lines


def _gen_impute(p: dict, inp: dict, ov: str) -> tuple[set, list]:
    df_in = inp.get("dataframe", "None")
    strategy = p.get("strategy", "mean")
    fill = p.get("fill_value", 0.0)
    cols = p.get("columns", [])
    out = _ivar(ov, "dataframe")
    lines = [f"{out} = {df_in}.copy()"]
    cols_expr = _r(cols) if cols else f"list({out}.select_dtypes(include='number').columns)"
    if strategy == "mean":
        lines += [
            f"for _col in {cols_expr}:",
            f"    {out}[_col] = {out}[_col].fillna({out}[_col].mean())",
        ]
    elif strategy == "median":
        lines += [
            f"for _col in {cols_expr}:",
            f"    {out}[_col] = {out}[_col].fillna({out}[_col].median())",
        ]
    else:
        lines += [
            f"for _col in {cols_expr}:",
            f"    {out}[_col] = {out}[_col].fillna({_r(fill)})",
        ]
    return set(), lines


def _gen_encode(p: dict, inp: dict, ov: str) -> tuple[set, list]:
    df_in = inp.get("dataframe", "None")
    cols = p.get("columns", [])
    method = p.get("method", "label")
    out = _ivar(ov, "dataframe")
    if method == "onehot":
        return (
            set(),
            [f"{out} = pd.get_dummies({df_in}, columns={_r(cols)})"],
        )
    else:
        return (
            {"from sklearn.preprocessing import LabelEncoder"},
            [
                f"{out} = {df_in}.copy()",
                f"_le = LabelEncoder()",
                *[
                    f"{out}[{_r(c)}] = _le.fit_transform({out}[{_r(c)}].astype(str))"
                    for c in cols
                ],
            ],
        )


def _gen_scale(p: dict, inp: dict, ov: str) -> tuple[set, list]:
    df_in = inp.get("dataframe", "None")
    cols = p.get("columns", [])
    method = p.get("method", "standard")
    out = _ivar(ov, "dataframe")
    scaler_cls = "StandardScaler" if method == "standard" else "MinMaxScaler"
    cols_expr = _r(cols) if cols else f"list({df_in}.select_dtypes(include='number').columns)"
    return (
        {f"from sklearn.preprocessing import {scaler_cls}"},
        [
            f"{out} = {df_in}.copy()",
            f"_scale_cols = {cols_expr}",
            f"_scaler = {scaler_cls}()",
            f"{out}[_scale_cols] = _scaler.fit_transform({out}[_scale_cols].fillna(0))",
        ],
    )


def _gen_select_columns(p: dict, inp: dict, ov: str) -> tuple[set, list]:
    df_in = inp.get("dataframe", "None")
    cols = p.get("columns", [])
    out = _ivar(ov, "dataframe")
    return set(), [f"{out} = {df_in}[{_r(cols)}].copy()"]


def _gen_drop_na(p: dict, inp: dict, ov: str) -> tuple[set, list]:
    df_in = inp.get("dataframe", "None")
    cols = p.get("columns", [])
    out = _ivar(ov, "dataframe")
    subset = f"subset={_r(cols)}" if cols else ""
    return set(), [f"{out} = {df_in}.dropna({subset}).reset_index(drop=True)"]


def _gen_drop_columns(p: dict, inp: dict, ov: str) -> tuple[set, list]:
    df_in = inp.get("dataframe", "None")
    cols = p.get("columns", [])
    out = _ivar(ov, "dataframe")
    if not cols:
        return set(), [f"{out} = {df_in}.copy()"]
    return set(), [f"{out} = {df_in}.drop(columns={_r(cols)}).reset_index(drop=True)"]


def _gen_trainer(p: dict, inp: dict, ov: str) -> tuple[set, list]:
    df_in = inp.get("dataframe", "None")
    model_type = p.get("model_type", "random_forest")
    target = p.get("target_column", "target")
    feat_cols = p.get("feature_columns", [])
    test_size = p.get("test_size", 0.2)
    random_state = p.get("random_state", 42)

    model_map = {
        "linear_regression": (
            "from sklearn.linear_model import LinearRegression",
            "LinearRegression()",
        ),
        "random_forest": (
            "from sklearn.ensemble import RandomForestRegressor",
            f"RandomForestRegressor(n_estimators=100, random_state={random_state})",
        ),
        "gradient_boosting": (
            "from sklearn.ensemble import GradientBoostingRegressor",
            f"GradientBoostingRegressor(n_estimators=100, random_state={random_state})",
        ),
    }
    imp_line, constructor = model_map.get(
        model_type,
        ("from sklearn.ensemble import RandomForestRegressor", "RandomForestRegressor()"),
    )

    feat_expr = (
        _r(feat_cols)
        if feat_cols
        else f"[c for c in {df_in}.select_dtypes(include='number').columns if c != {_r(target)}]"
    )

    out_model = _ivar(ov, "model")
    out_metrics = _ivar(ov, "metrics")
    out_path = _ivar(ov, "artifact_path")
    out_feat = _ivar(ov, "feature_names")

    lines = [
        f"import joblib, uuid as _uuid",
        f"from sklearn.metrics import mean_squared_error, r2_score",
        f"from sklearn.model_selection import train_test_split",
        f"{out_feat} = {feat_expr}",
        f"_df_clean = {df_in}[{out_feat} + [{_r(target)}]].dropna()",
        f"_X = _df_clean[{out_feat}].values",
        f"_y = _df_clean[{_r(target)}].values",
        f"_X_train, _X_test, _y_train, _y_test = train_test_split(",
        f"    _X, _y, test_size={test_size}, random_state={random_state}",
        f")",
        f"{out_model} = {constructor}",
        f"{out_model}.fit(_X_train, _y_train)",
        f"_y_pred = {out_model}.predict(_X_test)",
        f"{out_metrics} = {{",
        f"    'rmse': float(mean_squared_error(_y_test, _y_pred) ** 0.5),",
        f"    'r2': float(r2_score(_y_test, _y_pred)),",
        f"    'n_train': int(len(_X_train)),",
        f"    'n_test': int(len(_X_test)),",
        f"}}",
        f"_model_path = f'model_{{_uuid.uuid4().hex[:8]}}.pkl'",
        f"joblib.dump({out_model}, _model_path)",
        f"{out_path} = _model_path",
        f"print(f'Trained {model_type} → {{_model_path}}, R²={{{{_y_pred[:5]}}}}')",
        f"print(f'Metrics: {{{out_metrics}}}')",
    ]
    return {imp_line}, lines


def _gen_plot(p: dict, inp: dict, ov: str) -> tuple[set, list]:
    df_in = inp.get("dataframe", "None")
    ptype = p.get("plot_type", "scatter")
    xcol = p.get("x_column", "")
    ycol = p.get("y_column", "")
    ccol = p.get("color_column", "")
    title = p.get("title", "") or ptype.capitalize()
    out = _ivar(ov, "figure")

    lines = [
        "import matplotlib",
        "matplotlib.use('Agg')",
        "import matplotlib.pyplot as plt",
        f"_fig, _ax = plt.subplots(figsize=(8, 5))",
        f"_ax.set_title({_r(title)})",
    ]
    if ptype == "scatter":
        if ccol:
            lines += [
                f"for _grp_name, _grp_df in {df_in}.groupby({_r(ccol)}):",
                f"    _ax.scatter(_grp_df[{_r(xcol)}], _grp_df[{_r(ycol)}], label=str(_grp_name), alpha=0.6, s=15)",
                f"_ax.legend()",
            ]
        else:
            lines += [
                f"_ax.scatter({df_in}[{_r(xcol)}], {df_in}[{_r(ycol)}], alpha=0.6, s=15)",
            ]
        lines += [f"_ax.set_xlabel({_r(xcol)})", f"_ax.set_ylabel({_r(ycol)})"]
    elif ptype == "line":
        if ccol:
            lines += [
                f"for _grp_name, _grp_df in {df_in}.groupby({_r(ccol)}):",
                f"    _ax.plot(_grp_df[{_r(xcol)}], _grp_df[{_r(ycol)}], label=str(_grp_name))",
                f"_ax.legend()",
            ]
        else:
            lines += [f"_ax.plot({df_in}[{_r(xcol)}], {df_in}[{_r(ycol)}])"]
        lines += [f"_ax.set_xlabel({_r(xcol)})", f"_ax.set_ylabel({_r(ycol)})"]
    elif ptype == "histogram":
        col = xcol or ycol
        lines += [f"_ax.hist({df_in}[{_r(col)}].dropna(), bins=30, edgecolor='white')"]
        lines += [f"_ax.set_xlabel({_r(col)})"]
    elif ptype == "bar":
        lines += [
            f"_bar_data = {df_in}.groupby({_r(xcol)})[{_r(ycol)}].mean()",
            f"_ax.bar(_bar_data.index.astype(str), _bar_data.values)",
            f"_ax.set_xlabel({_r(xcol)})",
            f"_ax.set_ylabel({_r(ycol)})",
            f"plt.xticks(rotation=45, ha='right')",
        ]
    elif ptype == "box":
        col = ycol or xcol
        if ccol:
            lines += [
                f"_box_groups = {df_in}.groupby({_r(ccol)})[{_r(col)}].apply(list)",
                f"_ax.boxplot(_box_groups.values, labels=_box_groups.index.astype(str))",
            ]
        else:
            lines += [f"{df_in}[[{_r(col)}]].boxplot(ax=_ax)"]
    lines += [
        "plt.tight_layout()",
        "plt.savefig('plot_output.png', dpi=120)",
        "plt.show()",
        f"{out} = 'plot_output.png'",
    ]
    return {"import matplotlib"}, lines


def _gen_metrics(p: dict, inp: dict, ov: str) -> tuple[set, list]:
    df_in = inp.get("dataframe", "None")
    model_in = inp.get("model", "None")
    target = p.get("target_column", "target")
    feat_cols = p.get("feature_columns", [])
    task = p.get("task", "regression")
    out = _ivar(ov, "metrics")

    feat_expr = (
        _r(feat_cols)
        if feat_cols
        else f"[c for c in {df_in}.select_dtypes(include='number').columns if c != {_r(target)}]"
    )
    if task == "regression":
        imp = "from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error"
        lines = [
            f"_eval_feat = {feat_expr}",
            f"_eval_df = {df_in}[_eval_feat + [{_r(target)}]].dropna()",
            f"_eval_pred = {model_in}.predict(_eval_df[_eval_feat].values)",
            f"_eval_true = _eval_df[{_r(target)}].values",
            f"{out} = {{",
            f"    'rmse': float(mean_squared_error(_eval_true, _eval_pred) ** 0.5),",
            f"    'mae': float(mean_absolute_error(_eval_true, _eval_pred)),",
            f"    'r2': float(r2_score(_eval_true, _eval_pred)),",
            f"}}",
        ]
    else:
        imp = "from sklearn.metrics import accuracy_score, classification_report"
        lines = [
            f"_eval_feat = {feat_expr}",
            f"_eval_df = {df_in}[_eval_feat + [{_r(target)}]].dropna()",
            f"_eval_pred = {model_in}.predict(_eval_df[_eval_feat].values)",
            f"_eval_true = _eval_df[{_r(target)}].values",
            f"{out} = {{",
            f"    'accuracy': float(accuracy_score(_eval_true, _eval_pred)),",
            f"    'report': classification_report(_eval_true, _eval_pred),",
            f"}}",
        ]
    return {imp}, lines


def _gen_python_code(p: dict, inp: dict, ov: str) -> tuple[set, list]:
    df_in = inp.get("dataframe", "None")
    code: str = p.get("code", "result = df")
    out = _ivar(ov, "dataframe")
    # Indent the user's code under a block that binds `df`
    indented = "\n".join("    " + ln for ln in code.splitlines())
    lines = [
        "# ── User-defined Python code ──",
        f"_pc_df = {df_in}",
        "if True:  # scope block",
        "    import pandas as pd",
        "    import numpy as np",
        f"    df = _pc_df",
        indented or "    result = df",
        f"{out} = result  # noqa: F821",
    ]
    return set(), lines


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_GENERATORS: dict[str, Any] = {
    "csv_source": _gen_csv_source,
    "parquet_source": _gen_parquet_source,
    "database_source": _gen_database_source,
    "remote_fetch": _gen_remote_fetch,
    "filter": _gen_filter,
    "join": _gen_join,
    "group_by": _gen_group_by,
    "impute": _gen_impute,
    "encode": _gen_encode,
    "scale": _gen_scale,
    "select_columns": _gen_select_columns,
    "drop_na": _gen_drop_na,
    "drop_columns": _gen_drop_columns,
    "trainer": _gen_trainer,
    "plot": _gen_plot,
    "metrics": _gen_metrics,
    "python_code": _gen_python_code,
}


def generate_node_code(
    node_type: str,
    params: dict,
    input_refs: dict[str, str],
    output_var: str,
    display_name: str,
    step: int,
) -> tuple[set[str], list[str]]:
    """Return ``(imports, body_lines)`` for one node.

    Falls back to a comment block for unknown node types.
    """
    gen = _GENERATORS.get(node_type)
    if gen is None:
        out_slots = [f"{output_var}__dataframe"]
        lines = [
            f"# [{step}] {display_name} ({node_type}) — no standalone generator available",
            f"# inputs: {input_refs}",
        ]
        # Passthrough the first input to the expected dataframe output
        first_input = next(iter(input_refs.values()), "None")
        lines.append(f"{output_var}__dataframe = {first_input}  # passthrough")
        return set(), lines

    extra_imports, body = gen(params, input_refs, output_var)
    return extra_imports, body
