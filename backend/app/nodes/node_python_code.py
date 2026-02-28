"""PythonCodeNode — execute arbitrary Python code as a graph node.

The node exposes a snippet editor in the frontend (Monaco).  Inside the
snippet, ``df`` is the input DataFrame (or ``None`` when no upstream
DataFrame is connected).  The snippet must assign a DataFrame to the
name ``result``.

Example code::

    result = df[df["yield"] > 100].reset_index(drop=True)

Sandbox
-------
Execution runs in a ``ThreadPoolExecutor`` with a configurable wall-clock
timeout so a runaway snippet cannot hang the server indefinitely.

The execution namespace is intentionally **restricted**: only ``df``,
``pd`` (pandas), ``np`` (numpy), and the Python builtins are exposed.
Imports of other top-level packages are blocked by a custom ``__import__``
hook unless the module is already in ``sys.modules`` (i.e. pre-loaded by
the server process).
"""
from __future__ import annotations

import importlib
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from app.nodes.base import BaseNode, IOSlot, IOTypes

# Allowed top-level import names inside user code.
_ALLOWED_IMPORTS: frozenset[str] = frozenset(
    {
        "pandas",
        "pd",
        "numpy",
        "np",
        "math",
        "statistics",
        "datetime",
        "json",
        "re",
        "collections",
        "itertools",
        "functools",
        "sklearn",
        "scipy",
        "matplotlib",
    }
)

_DEFAULT_CODE = """\
# 'df' is the input DataFrame (or None if not connected).
# Assign your result to the variable 'result'.

result = df.copy()
"""


def _make_restricted_import(allowed: frozenset[str]):
    """Return a __import__ replacement that blocks non-whitelisted packages."""

    def _restricted_import(name: str, *args, **kwargs):
        top = name.split(".")[0]
        if top not in allowed and top not in sys.modules:
            raise ImportError(
                f"Import of '{name}' is not allowed inside PythonCodeNode. "
                f"Allowed top-level packages: {sorted(allowed)}"
            )
        return importlib.__import__(name, *args, **kwargs)

    return _restricted_import


def _run_code(
    code: str,
    df_in: Optional[pd.DataFrame],
    timeout: int,
) -> pd.DataFrame:
    """Execute *code* in an isolated namespace and return the ``result`` variable.

    Raises
    ------
    TimeoutError
        If execution exceeds *timeout* seconds.
    ValueError
        If ``result`` is not assigned or not a DataFrame.
    """

    def _exec_target():
        # Build a mutable builtins dict and inject the restricted __import__
        # *inside* it — Python resolves `import` statements by looking in
        # __builtins__, not in the top-level exec namespace.
        if isinstance(__builtins__, dict):
            builtins_dict: dict[str, Any] = dict(__builtins__)  # type: ignore[arg-type]
        else:
            builtins_dict = {k: getattr(__builtins__, k) for k in dir(__builtins__)}
        builtins_dict["__import__"] = _make_restricted_import(_ALLOWED_IMPORTS)

        namespace: dict[str, Any] = {
            "__builtins__": builtins_dict,
            "pd": pd,
            "np": np,
            "df": df_in,
        }
        exec(compile(code, "<PythonCodeNode>", "exec"), namespace)  # noqa: S102
        if "result" not in namespace:
            raise ValueError(
                "PythonCodeNode: your code did not assign a value to 'result'."
            )
        result = namespace["result"]
        if not isinstance(result, pd.DataFrame):
            raise ValueError(
                f"PythonCodeNode: 'result' must be a pandas DataFrame, "
                f"got {type(result).__name__!r}."
            )
        return result

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_exec_target)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeout:
            future.cancel()
            raise TimeoutError(
                f"PythonCodeNode: code execution exceeded the {timeout}s timeout."
            )


class PythonCodeNode(BaseNode):
    node_id = "python_code"
    display_name = "Python Code"
    description = (
        "Run arbitrary Python code. "
        "Input DataFrame available as `df`; assign output to `result`."
    )
    category = "Transforms"

    inputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME, required=False)]
    outputs = [IOSlot(name="dataframe", type=IOTypes.DATAFRAME)]

    class Params(BaseModel):
        code: str = Field(
            default=_DEFAULT_CODE,
            description="Python code snippet. Use `df` for input and assign output to `result`.",
            json_schema_extra={"ui_widget": "monaco", "language": "python"},
        )
        timeout_seconds: int = Field(
            default=30,
            ge=1,
            le=300,
            description="Maximum wall-clock seconds allowed for code execution.",
        )

    params = Params

    def run(self, inputs: dict[str, Any], params: Params) -> dict[str, Any]:
        df_in: Optional[pd.DataFrame] = inputs.get("dataframe")
        result_df = _run_code(params.code, df_in, params.timeout_seconds)
        return {"dataframe": result_df}
