import type { Edge } from "@xyflow/react"
import type { GraphFlowNode, GraphTemplate } from "../graphTypes"

/**
 * "Python Code Transform" template
 *
 * Demonstrates the python_code node by:
 *   1. Loading a CSV file
 *   2. Running a Python snippet that normalises a numeric column and adds
 *      a z-score and a rolling mean column — operations not covered by
 *      the built-in transform nodes
 *   3. Plotting the resulting distribution as a histogram and a scatter
 *      of raw value vs z-score
 *
 * Edit the Python code snippet in the inspector to explore the full API:
 *   - `df`     — the upstream DataFrame (pandas)
 *   - `pd`     — pandas
 *   - `np`     — numpy
 *   - `result` — assign your output DataFrame here
 */

const PYTHON_CODE = `\
# 'df' is the input DataFrame (pandas).
# 'pd' and 'np' are already available — no imports needed.
# Assign your output to 'result'.

result = df.copy()

# ── z-score normalisation ──
col = "yield_kg_ha"  # numeric column from sample.csv
if col in result.columns:
    mean = result[col].mean()
    std  = result[col].std()
    result["z_score"] = (result[col] - mean) / std

    # 3-row rolling mean (useful for time-series smoothing)
    result["rolling_mean"] = result[col].rolling(window=3, min_periods=1).mean()

# Drop rows where z-score is extreme (|z| > 3)
if "z_score" in result.columns:
    result = result[result["z_score"].abs() <= 3].reset_index(drop=True)
`

const pythonCodeNodeInfo = {
  node_id: "python_code",
  display_name: "Python Code",
  category: "Transforms",
  endpoint: "",
  description: "Run arbitrary Python. `df` = input DataFrame; assign output to `result`.",
  inputs: ["dataframe"],
  outputs: ["dataframe"],
  params: ["code", "timeout_seconds"],
  params_schema: {
    properties: {
      code: {
        type: "string",
        title: "Code",
        description: "Python code snippet. Use `df` for input and assign output to `result`.",
        default: "result = df.copy()",
        ui_widget: "monaco",
        language: "python",
      },
      timeout_seconds: {
        type: "integer",
        title: "Timeout (s)",
        description: "Maximum wall-clock seconds allowed for code execution.",
        default: 30,
      },
    },
  },
}

const plotSchema = {
  properties: {
    plot_type: {
      type: "string",
      title: "Plot Type",
      enum: ["scatter", "line", "histogram", "bar", "box"],
      default: "histogram",
    },
    x_column: { type: "string", title: "X Column", default: "" },
    y_column: { type: "string", title: "Y Column", default: "" },
    color_column: { type: "string", title: "Colour Column", default: "" },
    title: { type: "string", title: "Title", default: "" },
  },
}

export const pythonCodeTransformTemplate: GraphTemplate = {
  nodes: [
    // ── Source ──────────────────────────────────────────────────────────────
    {
      id: "py1",
      type: "graphNode",
      position: { x: 50, y: 180 },
      data: {
        nodeInfo: {
          node_id: "csv_source",
          display_name: "CSV Source",
          category: "Sources",
          endpoint: "",
          description: "Load CSV file",
          inputs: [],
          outputs: ["dataframe"],
          params: [],
          params_schema: {
            properties: {
              file_path: { type: "string", title: "File Path", default: "/app/data/sample.csv" },
              separator: { type: "string", title: "Separator", default: "," },
              encoding: { type: "string", title: "Encoding", default: "utf-8" },
            },
            required: ["file_path"],
          },
        },
        params: { file_path: "/app/data/sample.csv", separator: ",", encoding: "utf-8" },
        label: "Load CSV",
      },
    } satisfies GraphFlowNode,

    // ── Python transform ─────────────────────────────────────────────────────
    {
      id: "py2",
      type: "graphNode",
      position: { x: 310, y: 180 },
      data: {
        nodeInfo: pythonCodeNodeInfo,
        params: {
          code: PYTHON_CODE,
          timeout_seconds: 30,
        },
        label: "Normalise + Rolling Mean",
      },
    } satisfies GraphFlowNode,

    // ── Plot 1: z-score distribution ─────────────────────────────────────────
    {
      id: "py3",
      type: "graphNode",
      position: { x: 580, y: 60 },
      data: {
        nodeInfo: {
          node_id: "plot",
          display_name: "Z-score Distribution",
          category: "Visualization",
          endpoint: "",
          description: "Histogram of z-scores",
          inputs: ["dataframe"],
          outputs: ["figure"],
          params: ["plot_type", "x_column", "y_column", "color_column", "title"],
          params_schema: plotSchema,
        },
        params: {
          plot_type: "histogram",
          x_column: "z_score",
          y_column: "",
          color_column: "",
          title: "Z-score Distribution",
        },
        label: "Z-score Histogram",
      },
    } satisfies GraphFlowNode,

    // ── Plot 2: raw value vs rolling mean ────────────────────────────────────
    {
      id: "py4",
      type: "graphNode",
      position: { x: 580, y: 310 },
      data: {
        nodeInfo: {
          node_id: "plot",
          display_name: "Yield vs Rolling Mean",
          category: "Visualization",
          endpoint: "",
          description: "Scatter of raw yield vs rolling mean",
          inputs: ["dataframe"],
          outputs: ["figure"],
          params: ["plot_type", "x_column", "y_column", "color_column", "title"],
          params_schema: plotSchema,
        },
        params: {
          plot_type: "scatter",
          x_column: "yield_kg_ha",
          y_column: "rolling_mean",
          color_column: "",
          title: "Raw Yield vs Rolling Mean",
        },
        label: "Yield vs Rolling Mean",
      },
    } satisfies GraphFlowNode,
  ],
  edges: [
    {
      id: "epy1-py2",
      source: "py1",
      sourceHandle: "dataframe",
      target: "py2",
      targetHandle: "dataframe",
    } satisfies Edge,
    {
      id: "epy2-py3",
      source: "py2",
      sourceHandle: "dataframe",
      target: "py3",
      targetHandle: "dataframe",
    } satisfies Edge,
    {
      id: "epy2-py4",
      source: "py2",
      sourceHandle: "dataframe",
      target: "py4",
      targetHandle: "dataframe",
    } satisfies Edge,
  ],
}
