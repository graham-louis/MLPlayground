/**
 * LSTM Soil Moisture Forecast — Bidirectional LSTM (PyTorch)
 *
 * Reproduces the full workflow from lstm_model_lab.py as a composable
 * MLPlayground graph.  Replace the CSV source with any daily weather + soil
 * DataFrame that contains a ``soil_moisture`` target column.
 *
 * Pipeline
 * ~~~~~~~~
 *  1. Load daily weather + soil data from a CSV file.
 *  2. Feature engineering (Python Code node):
 *       • Lowercase columns, resample to daily mean, ffill.
 *       • Saxton-Rawls pedotransfer → field capacity (fc), wilting point (wp),
 *         plant-available water (paw).
 *       • Rolling precipitation sums (3 / 7 / 30 / 90 days).
 *       • Dynamic Antecedent Precipitation Index (API) with clay-based decay k.
 *       • Rolling temperature means (7 / 30 days).
 *       • VPD approximation from temp + rhum (if vpd column missing).
 *       • Adds integer ``Year`` column for temporal splitting.
 *  3. Temporal Split — year-based, no cross-year leakage.
 *       • Test years    : [2019, 2021]  (validation during training)
 *       • Holdout years : [2022, 2023]  (final evaluation, unseen)
 *  4. Sequence Builder — MinMaxScaler fit on train; 30-day sliding windows
 *     built per year; saves arrays + scalers as a single joblib artifact.
 *  5. LSTM Trainer — Bidirectional LSTM(64) → Dropout(0.2) → Linear(16) →
 *     ReLU → Linear(1); Adam(lr=0.001); 20 epochs.
 *  6. LSTM Predictor ×2 — one for the test split, one for holdout.
 *  7. Plot ×2 — actual vs predicted line charts.
 *
 * Prerequisites
 * ~~~~~~~~~~~~~
 * * A CSV file at ``data/training_data_cleaned.csv`` (or update the path in
 *   the CSV Source node).  The file must contain a ``soil_moisture`` column
 *   and a datetime index or ``date`` column.
 * * ``torch`` is already in the backend dependencies.
 *
 * Customisation tips
 * ~~~~~~~~~~~~~~~~~~
 * * Edit the Python Code node to add / remove feature engineering steps.
 * * Adjust ``test_years`` / ``holdout_years`` in Temporal Split to match
 *   the years available in your dataset.
 * * Tune ``lstm_units``, ``epochs``, ``learning_rate`` in LSTM Trainer.
 * * Change ``seq_length`` in Sequence Builder if your seasonality differs.
 */
import type { Edge } from "@xyflow/react"
import type { GraphFlowNode, GraphTemplate } from "../graphTypes"

// ── Re-usable schema snippets ───────────────────────────────────────────────

const csvSourceSchema = {
  properties: {
    file_path: { type: "string", title: "File Path", default: "data/training_data_cleaned.csv" },
    separator: { type: "string", title: "Separator", default: "," },
    encoding:  { type: "string", title: "Encoding",  default: "utf-8" },
  },
  required: ["file_path"],
}

const pythonCodeSchema = {
  properties: {
    code: {
      type: "string",
      title: "Code",
      description: "df = input DataFrame.  Assign output to result.  pd and np are available.",
      default: "result = df.copy()",
      ui_widget: "monaco",
      language: "python",
    },
    timeout_seconds: { type: "integer", title: "Timeout (s)", default: 120 },
  },
}

const temporalSplitSchema = {
  properties: {
    date_column:   { type: "string", title: "Date / Year Column", default: "date" },
    test_years: {
      type: "array", items: { type: "integer" },
      title: "Test Years", default: [2019, 2021],
    },
    holdout_years: {
      type: "array", items: { type: "integer" },
      title: "Holdout Years", default: [2022, 2023],
    },
  },
}

const sequenceBuilderSchema = {
  properties: {
    target_column: { type: "string", title: "Target Column", default: "soil_moisture" },
    feature_columns: {
      type: "array", items: { type: "string" },
      title: "Feature Columns (empty = all numeric except target)",
      default: [],
    },
    seq_length: { type: "integer", title: "Sequence Length (days)", default: 30, minimum: 3, maximum: 365 },
    year_column: { type: "string", title: "Year Column", default: "Year" },
  },
}

const lstmTrainerSchema = {
  properties: {
    lstm_units: {
      type: "integer", title: "LSTM Units",
      enum: ["16", "32", "64", "128"], default: 64,
    },
    dropout: { type: "number", title: "Dropout Rate", default: 0.2, minimum: 0.0, maximum: 0.5 },
    learning_rate: { type: "number", title: "Learning Rate", default: 0.001 },
    epochs: { type: "integer", title: "Epochs", default: 20, minimum: 1, maximum: 500 },
    batch_size: { type: "integer", title: "Batch Size", default: 64 },
    bidirectional: { type: "boolean", title: "Bidirectional", default: true },
    model_name: { type: "string", title: "Model Name", default: "lstm_soil_moisture" },
  },
}

const lstmPredictorSchema = {
  properties: {
    split: {
      type: "string", title: "Split",
      enum: ["train", "test", "holdout"], default: "test",
    },
  },
}

const plotSchema = {
  properties: {
    plot_type: {
      type: "string", title: "Plot Type",
      enum: ["scatter", "line", "histogram", "bar", "box"], default: "line",
    },
    x_column: { type: "string", title: "X Column", default: "sample_index" },
    y_column: { type: "string", title: "Y Column", default: "actual" },
    color_column: { type: "string", title: "Colour Column", default: "predicted" },
    title: { type: "string", title: "Title", default: "" },
  },
}

// ── Feature engineering code (pre-filled in the Python Code node) ───────────
//
// Mirrors the load_data() function in lstm_model_lab.py.
// Input  : df   (raw daily weather + soil DataFrame from csv_source)
// Output : result  (feature-engineered DataFrame with a Year column)

const FEATURE_ENGINEERING_CODE = `\
# ─────────────────────────────────────────────────────────────────────────────
# Soil Moisture Feature Engineering
#
# Input  : df     — raw daily CSV data loaded by the CSV Source node.
# Output : result — feature-engineered DataFrame with a 'Year' column added.
#                   Includes physics-based and lagged time-series features.
# ─────────────────────────────────────────────────────────────────────────────

import pandas as pd
import numpy as np

# 1. Lowercase all column names for consistency
df.columns = [c.lower() for c in df.columns]

# 2. Ensure a DatetimeIndex for resampling
if not isinstance(df.index, pd.DatetimeIndex):
    date_candidates = [c for c in df.columns if "date" in c.lower() or c == "time"]
    if date_candidates:
        df = df.set_index(date_candidates[0])
        df.index = pd.to_datetime(df.index)
    else:
        raise ValueError(
            "Feature Engineering: could not find a date column. "
            "Expected a DatetimeIndex or a column like 'date' / 'time'."
        )

# 3. Remove physiologically impossible soil moisture values (< 0.1 m³/m³)
if "soil_moisture" in df.columns:
    df = df[df["soil_moisture"] >= 0.1]

# 4. Select numeric columns and resample to daily mean, forward-fill gaps
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
df = df[numeric_cols].resample("D").mean().ffill().fillna(0)

# 5. Saxton-Rawls pedotransfer functions
#    Computes field capacity (fc), wilting point (wp), plant-available water (paw)
#    from sand / clay / organic-matter fractions.
if "sand_topsoil" in df.columns and "clay_topsoil" in df.columns:
    sand = df["sand_topsoil"] / 100.0
    clay = df["clay_topsoil"] / 100.0
    om   = df["om_topsoil"] / 100.0 if "om_topsoil" in df.columns else 0.02

    fc_ = (
        -0.251 * sand + 0.195 * clay + 0.011 * om
        + 0.006 * (sand * om) - 0.027 * (clay * om)
        + 0.452 * (sand * clay) + 0.299
    )
    df["fc"] = fc_ + 1.283 * fc_**2 - 0.374 * fc_ - 0.015

    wp_ = (
        -0.024 * sand + 0.487 * clay + 0.006 * om
        + 0.005 * (sand * om) - 0.013 * (clay * om)
        + 0.068 * (sand * clay) + 0.031
    )
    df["wp"]  = wp_ + 0.14 * wp_ - 0.02
    df["paw"] = df["fc"] - df["wp"]

# 6. Rolling precipitation memory
if "prcp" in df.columns:
    df["prcp_3d"]  = df["prcp"].rolling(3,  min_periods=1).sum()
    df["prcp_7d"]  = df["prcp"].rolling(7,  min_periods=1).sum()
    df["prcp_30d"] = df["prcp"].rolling(30, min_periods=1).sum()
    df["prcp_90d"] = df["prcp"].rolling(90, min_periods=1).sum()

    # Antecedent Precipitation Index (API) with clay-dependent decay coefficient k
    # k = 0.88 + 0.10 * clay_fraction  (higher clay → slower drainage → higher k)
    if "clay_topsoil" in df.columns:
        k_vals = (0.88 + 0.10 * df["clay_topsoil"] / 100.0).values
    else:
        k_vals = np.full(len(df), 0.96)

    prcp_vals = df["prcp"].values
    api = [0.0]
    for i in range(len(prcp_vals)):
        api.append(api[-1] * k_vals[i] + prcp_vals[i])
    df["api"] = api[1:]

# 7. Rolling temperature memory
if "temp" in df.columns:
    df["temp_7d"]  = df["temp"].rolling(7,  min_periods=1).mean()
    df["temp_30d"] = df["temp"].rolling(30, min_periods=1).mean()

# 8. VPD approximation (only if vpd column is missing)
#    VPD = saturation vapour pressure − actual vapour pressure
if "vpd" not in df.columns and "temp" in df.columns and "rhum" in df.columns:
    es = 0.6108 * np.exp(17.27 * df["temp"] / (df["temp"] + 237.3))
    ea = es * (df["rhum"] / 100.0)
    df["vpd"] = es - ea

# 9. Add integer Year column (used by Temporal Split and Sequence Builder)
df["Year"] = df.index.year

result = df.fillna(0)
print(f"Feature engineering complete: {result.shape[0]} rows × {result.shape[1]} columns")
print(f"Years: {sorted(result['Year'].unique().tolist())}")
print(f"Columns: {list(result.columns)}")
`

// ── Node definitions ────────────────────────────────────────────────────────

export const lstmSoilMoistureTemplate: GraphTemplate = {
  nodes: [
    // ── 1. DATA SOURCE ───────────────────────────────────────────────────────
    {
      id: "csv_src",
      type: "graphNode",
      position: { x: 50, y: 220 },
      data: {
        nodeInfo: {
          node_id: "csv_source",
          display_name: "Daily Weather + Soil CSV",
          category: "Sources",
          endpoint: "",
          description: "Load daily weather and soil data from a CSV file",
          inputs: [],
          outputs: ["dataframe"],
          params: [],
          params_schema: csvSourceSchema,
        },
        params: {
          file_path: "data/training_data_cleaned.csv",
          separator: ",",
          encoding: "utf-8",
        },
      },
    } satisfies GraphFlowNode,

    // ── 2. FEATURE ENGINEERING ───────────────────────────────────────────────
    {
      id: "feat_eng",
      type: "graphNode",
      position: { x: 330, y: 220 },
      data: {
        nodeInfo: {
          node_id: "python_code",
          display_name: "Feature Engineering",
          category: "Transforms",
          endpoint: "",
          description:
            "Saxton-Rawls pedotransfer, rolling precip sums, API, VPD, adds Year column",
          inputs:  ["dataframe"],
          outputs: ["dataframe"],
          params:  [],
          params_schema: pythonCodeSchema,
        },
        params: {
          code: FEATURE_ENGINEERING_CODE,
          timeout_seconds: 120,
        },
      },
    } satisfies GraphFlowNode,

    // ── 3. TEMPORAL SPLIT ────────────────────────────────────────────────────
    {
      id: "temp_split",
      type: "graphNode",
      position: { x: 640, y: 220 },
      data: {
        nodeInfo: {
          node_id: "temporal_split",
          display_name: "Temporal Split",
          category: "Transforms",
          endpoint: "",
          description: "Split data by year group into train / test / holdout",
          inputs:  ["dataframe"],
          outputs: ["train", "test", "holdout"],
          params:  [],
          params_schema: temporalSplitSchema,
        },
        params: {
          date_column:   "Year",
          test_years:    [2019, 2021],
          holdout_years: [2022, 2023],
        },
      },
    } satisfies GraphFlowNode,

    // ── 4. SEQUENCE BUILDER ──────────────────────────────────────────────────
    {
      id: "seq_build",
      type: "graphNode",
      position: { x: 960, y: 220 },
      data: {
        nodeInfo: {
          node_id: "sequence_builder",
          display_name: "Sequence Builder",
          category: "Modeling",
          endpoint: "",
          description:
            "Build 3-D sliding-window sequences for LSTM; fit MinMaxScaler on train only",
          inputs:  ["train", "test", "holdout"],
          outputs: ["artifact_path"],
          params:  [],
          params_schema: sequenceBuilderSchema,
        },
        params: {
          target_column:   "soil_moisture",
          feature_columns: [],
          seq_length:      30,
          year_column:     "Year",
        },
      },
    } satisfies GraphFlowNode,

    // ── 5. LSTM TRAINER ──────────────────────────────────────────────────────
    {
      id: "lstm_train",
      type: "graphNode",
      position: { x: 1270, y: 220 },
      data: {
        nodeInfo: {
          node_id: "lstm_trainer",
          display_name: "LSTM Trainer",
          category: "Modeling",
          endpoint: "",
          description:
            "Bidirectional LSTM (PyTorch): Input → BiLSTM(64) → Dropout → Linear(16) → ReLU → Linear(1)",
          inputs:  ["sequences"],
          outputs: ["model", "metrics", "artifact_path", "history", "feature_names"],
          params:  [],
          params_schema: lstmTrainerSchema,
        },
        params: {
          lstm_units:    64,
          dropout:       0.2,
          learning_rate: 0.001,
          epochs:        20,
          batch_size:    64,
          bidirectional: true,
          model_name:    "lstm_soil_moisture",
        },
      },
    } satisfies GraphFlowNode,

    // ── 6a. LSTM PREDICTOR — test split ─────────────────────────────────────
    {
      id: "lstm_pred_test",
      type: "graphNode",
      position: { x: 1580, y: 80 },
      data: {
        nodeInfo: {
          node_id: "lstm_predictor",
          display_name: "LSTM Predict (Test)",
          category: "Modeling",
          endpoint: "",
          description: "Run inference on the test-year split",
          inputs:  ["model", "sequences"],
          outputs: ["predictions", "artifact_path"],
          params:  [],
          params_schema: lstmPredictorSchema,
        },
        params: { split: "test" },
      },
    } satisfies GraphFlowNode,

    // ── 6b. LSTM PREDICTOR — holdout split ───────────────────────────────────
    {
      id: "lstm_pred_hold",
      type: "graphNode",
      position: { x: 1580, y: 380 },
      data: {
        nodeInfo: {
          node_id: "lstm_predictor",
          display_name: "LSTM Predict (Holdout)",
          category: "Modeling",
          endpoint: "",
          description: "Run inference on the held-out final evaluation split",
          inputs:  ["model", "sequences"],
          outputs: ["predictions", "artifact_path"],
          params:  [],
          params_schema: lstmPredictorSchema,
        },
        params: { split: "holdout" },
      },
    } satisfies GraphFlowNode,

    // ── 7a. PLOT — test set forecast ─────────────────────────────────────────
    {
      id: "plot_test",
      type: "graphNode",
      position: { x: 1870, y: 80 },
      data: {
        nodeInfo: {
          node_id: "plot",
          display_name: "Test Set Forecast",
          category: "Visualization",
          endpoint: "",
          description: "Actual vs. predicted soil moisture — test years",
          inputs:  ["dataframe"],
          outputs: ["figure"],
          params:  [],
          params_schema: plotSchema,
        },
        params: {
          plot_type:    "line",
          x_column:     "sample_index",
          y_column:     "actual",
          color_column: "predicted",
          title:        "Test Set: Actual vs Predicted Soil Moisture",
        },
      },
    } satisfies GraphFlowNode,

    // ── 7b. PLOT — holdout set forecast ──────────────────────────────────────
    {
      id: "plot_hold",
      type: "graphNode",
      position: { x: 1870, y: 380 },
      data: {
        nodeInfo: {
          node_id: "plot",
          display_name: "Holdout Set Forecast",
          category: "Visualization",
          endpoint: "",
          description: "Actual vs. predicted soil moisture — holdout years (unseen)",
          inputs:  ["dataframe"],
          outputs: ["figure"],
          params:  [],
          params_schema: plotSchema,
        },
        params: {
          plot_type:    "line",
          x_column:     "sample_index",
          y_column:     "actual",
          color_column: "predicted",
          title:        "Holdout Set: Actual vs Predicted Soil Moisture (Unseen)",
        },
      },
    } satisfies GraphFlowNode,
  ],

  edges: [
    // csv_source → feature engineering
    {
      id: "e_csv_feat",
      source: "csv_src",  sourceHandle: "dataframe",
      target: "feat_eng", targetHandle: "dataframe",
    } satisfies Edge,

    // feature engineering → temporal split
    {
      id: "e_feat_split",
      source: "feat_eng",  sourceHandle: "dataframe",
      target: "temp_split", targetHandle: "dataframe",
    } satisfies Edge,

    // temporal split → sequence builder (3 ports)
    {
      id: "e_split_train",
      source: "temp_split", sourceHandle: "train",
      target: "seq_build",  targetHandle: "train",
    } satisfies Edge,
    {
      id: "e_split_test",
      source: "temp_split", sourceHandle: "test",
      target: "seq_build",  targetHandle: "test",
    } satisfies Edge,
    {
      id: "e_split_holdout",
      source: "temp_split", sourceHandle: "holdout",
      target: "seq_build",  targetHandle: "holdout",
    } satisfies Edge,

    // sequence builder → lstm trainer (sequences artifact)
    {
      id: "e_seq_trainer",
      source: "seq_build",  sourceHandle: "artifact_path",
      target: "lstm_train", targetHandle: "sequences",
    } satisfies Edge,

    // sequence builder → both predictors (same artifact, no re-scaling needed)
    {
      id: "e_seq_pred_test",
      source: "seq_build",      sourceHandle: "artifact_path",
      target: "lstm_pred_test", targetHandle: "sequences",
    } satisfies Edge,
    {
      id: "e_seq_pred_hold",
      source: "seq_build",      sourceHandle: "artifact_path",
      target: "lstm_pred_hold", targetHandle: "sequences",
    } satisfies Edge,

    // lstm trainer model → both predictors
    {
      id: "e_model_pred_test",
      source: "lstm_train",     sourceHandle: "model",
      target: "lstm_pred_test", targetHandle: "model",
    } satisfies Edge,
    {
      id: "e_model_pred_hold",
      source: "lstm_train",     sourceHandle: "model",
      target: "lstm_pred_hold", targetHandle: "model",
    } satisfies Edge,

    // predictors → plots
    {
      id: "e_pred_test_plot",
      source: "lstm_pred_test", sourceHandle: "predictions",
      target: "plot_test",      targetHandle: "dataframe",
    } satisfies Edge,
    {
      id: "e_pred_hold_plot",
      source: "lstm_pred_hold", sourceHandle: "predictions",
      target: "plot_hold",      targetHandle: "dataframe",
    } satisfies Edge,
  ],
}
