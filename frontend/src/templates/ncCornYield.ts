/**
 * NC Corn Yield Model — Final Goal Workflow
 *
 * Demonstrates the end-to-end MLPlayground pipeline described in features.md:
 *
 *   1. Pull historical corn-yield, weather, and soil data for North Carolina
 *      from the MLPlayground database.
 *   2. Join and clean the data, then train a Random Forest regression model
 *      whose target is "value" (yield in Bu/Acre or kg/ha).
 *   3. Run the model back on the training data and ► PLOT the residuals
 *      (actual vs predicted scatter) to evaluate fit quality.
 *   4. Fetch NOAA GSOY historical + forecasted weather for NC (2015 → 2026)
 *      via the "noaa_gsoy" remote datasource adapter.
 *   5. Prepare the NOAA data (rename columns, approximate GDD, fill median
 *      NC soil values) so it matches the training feature schema.
 *   6. Apply the trained model to the prepared NOAA data and ► PLOT the
 *      predicted yield time series (2015 → 2026).
 *
 * How to run this template:
 *   • Load the template from the toolbar "Load Template" menu.
 *   • Click ▶ Run to execute the full graph.
 *   • After a successful run, open the Dashboard tab to view the residual
 *     scatter and the 2026 yield forecast line chart.
 *   • Use the "Export as Python" button to download a standalone script.
 *
 * NOAA API token:
 *   The NOAA Remote Fetch node requires a free token from
 *   https://www.ncdc.noaa.gov/cdo-web/token stored in NOAA_CDO_TOKEN.
 *   Without it the NOAA branch will error; the training branch still runs.
 */
import type { Edge } from "@xyflow/react"
import type { GraphFlowNode, GraphTemplate } from "../graphTypes"

// ── Shared schema snippets ──────────────────────────────────────────────────

const dbSchema = {
  properties: {
    datasource_key: { type: "string", title: "Datasource" },
    filters_json: { type: "string", title: "Filters (JSON)", default: "{}" },
    limit: { type: "integer", title: "Row Limit", default: 10000 },
  },
  required: ["datasource_key"],
}

const filterSchema = {
  properties: {
    column: { type: "string", title: "Column" },
    operator: {
      type: "string",
      title: "Operator",
      enum: ["==", "!=", ">", "<", ">=", "<="],
      default: "==",
    },
    value: { type: "string", title: "Value" },
  },
  required: ["column", "operator", "value"],
}

const joinSchema = {
  properties: {
    on: { type: "array", items: { type: "string" }, title: "Join Keys" },
    how: {
      type: "string",
      title: "How",
      enum: ["inner", "left", "right", "outer"],
      default: "inner",
    },
  },
  required: ["on"],
}

const plotSchema = {
  properties: {
    plot_type: {
      type: "string",
      title: "Plot Type",
      enum: ["scatter", "line", "histogram", "bar", "box"],
      default: "scatter",
    },
    x_column: { type: "string", title: "X Column", default: "" },
    y_column: { type: "string", title: "Y Column", default: "" },
    color_column: { type: "string", title: "Colour Column", default: "" },
    title: { type: "string", title: "Title", default: "" },
  },
}

const predictorSchema = {
  properties: {
    target_column: {
      type: "string",
      title: "Target Column",
      description: "If set, computes actual, residual, and pct_error. Leave blank for pure inference.",
      default: "",
    },
    feature_columns: {
      type: "array",
      items: { type: "string" },
      title: "Feature Columns (override)",
      description: "Override the feature list coming from feature_names input. Leave empty to use wired feature_names.",
      default: [],
    },
    id_columns: {
      type: "array",
      items: { type: "string" },
      title: "ID / Pass-through Columns",
      description: "Columns to carry through to output (e.g. year, county). Not used as features.",
      default: [],
    },
    output_column_name: {
      type: "string",
      title: "Output Column Name",
      description: "Name of the predicted-value column in the output DataFrame.",
      default: "predicted_yield",
    },
  },
}

// ── Python prep code for NOAA data ─────────────────────────────────────────
//
// Renames NOAA GSOY columns to match the training-time feature names, fills in
// approximate median soil values for North Carolina agricultural land, and
// computes a rough Growing Degree Day approximation.

const NOAA_PREP_CODE = `\
# ─────────────────────────────────────────────────────────────────────────────
# Prepare NOAA GSOY weather data for yield prediction.
#
# Inputs  : df  (NOAA dataframe — real data through 2024)
# Outputs : result  (historical rows + a synthetic 2025 & 2026 forecast row)
#
# Strategy for the 2026 forecast:
#   The NOAA CDO API only serves completed calendar years, so 2025 / 2026
#   records do not exist yet.  We extrapolate avg_temp and precipitation for
#   2025 and 2026 using a simple linear trend over the most recent 5 years,
#   then apply the same GDD and soil-fill logic as the historical rows.
# ─────────────────────────────────────────────────────────────────────────────

import pandas as pd
import numpy as np

# 1. Rename NOAA GSOY columns → training feature names
result = df.rename(columns={
    "tavg": "avg_temp",       # Annual average temperature (°C)
    "prcp": "precipitation",  # Annual total precipitation (mm)
})

# 2. Approximate Growing Degree Days (GDD10, base 10 °C)
#    GDD_annual ≈ max(0, avg_temp − 10) × growing_season_days
result["gdd"] = (result["avg_temp"] - 10).clip(lower=0) * 180  # ~180 growing days in NC

# 3. Fill in median NC agricultural soil values (USDA NRCS state averages)
#    These are used as default features when no county-level soil data is available.
result["ph"]             = 6.2   # pH (dimensionless)
result["organic_matter"] = 2.1   # Organic matter (%)
result["sand_pct"]       = 45.0  # Sand content (%)
result["clay_pct"]       = 22.0  # Clay content (%)

# 4. Drop rows where key weather features are missing
required_cols = ["avg_temp", "precipitation"]
result = result.dropna(subset=required_cols).reset_index(drop=True)

# 5. Tag with crop context (used as an ID column, not a feature)
result["crop"]  = "CORN"
result["state"] = "NC"

# 6. Extrapolate 2025 and 2026 via linear trend over the 5 most recent years
#    This produces *forecast* rows — clearly labelled in the output.
def _linear_extrap(series: pd.Series, years: pd.Series, target_year: int) -> float:
    """Fit a 1-D linear trend to the 5 most recent points and predict target_year."""
    recent = series.iloc[-5:]
    yr_recent = years.iloc[-5:]
    if len(recent) < 2:
        return float(recent.mean())
    coeffs = np.polyfit(yr_recent.astype(float), recent.astype(float), deg=1)
    return float(np.polyval(coeffs, target_year))

if len(result) >= 2:
    for forecast_year in [2025, 2026]:
        if forecast_year not in result["year"].values:
            t_proj = _linear_extrap(result["avg_temp"],      result["year"], forecast_year)
            p_proj = _linear_extrap(result["precipitation"],  result["year"], forecast_year)
            # Clamp to physically reasonable bounds
            t_proj = float(np.clip(t_proj, -5, 40))
            p_proj = float(np.clip(p_proj, 0, 5000))
            gdd_proj = max(0.0, t_proj - 10) * 180
            forecast_row = pd.DataFrame([{
                "year":           forecast_year,
                "avg_temp":       round(t_proj, 2),
                "precipitation":  round(p_proj, 1),
                "gdd":            round(gdd_proj, 1),
                "ph":             6.2,
                "organic_matter": 2.1,
                "sand_pct":       45.0,
                "clay_pct":       22.0,
                "crop":           "CORN",
                "state":          "NC",
            }])
            result = pd.concat([result, forecast_row], ignore_index=True)
            print(f"Appended synthetic {forecast_year} forecast row:  avg_temp={t_proj:.2f}°C  prcp={p_proj:.0f}mm")

result = result.sort_values("year").reset_index(drop=True)
print(f"NOAA prep: {len(result)} rows ({result['year'].min()}–{result['year'].max()}, last two are forecast)")
print(result[["year", "avg_temp", "precipitation", "gdd"]].to_string(index=False))
`

// ── Node definitions ────────────────────────────────────────────────────────

const predictorNodeInfo = (displayName: string) => ({
  node_id: "predictor",
  display_name: displayName,
  category: "Modeling",
  endpoint: "",
  description:
    "Apply a trained model to a DataFrame. Wire model and feature_names from a Trainer node.",
  inputs: ["model", "dataframe", "feature_names"],
  outputs: ["predictions"],
  params: ["target_column", "feature_columns", "id_columns", "output_column_name"],
  params_schema: predictorSchema,
})

// ── Template ────────────────────────────────────────────────────────────────

export const ncCornYieldTemplate: GraphTemplate = {
  nodes: [
    // ── DATA SOURCES ────────────────────────────────────────────────────────

    {
      id: "s_yields",
      type: "graphNode",
      position: { x: 50, y: 50 },
      data: {
        nodeInfo: {
          node_id: "database_source",
          display_name: "Yields (NC Corn)",
          category: "Sources",
          endpoint: "",
          description: "Crop yield records from the MLPlayground database",
          inputs: [],
          outputs: ["dataframe"],
          params: [],
          params_schema: dbSchema,
        },
        params: { datasource_key: "yields", filters_json: "{}", limit: 10000 },
      },
    } satisfies GraphFlowNode,

    {
      id: "s_weather",
      type: "graphNode",
      position: { x: 50, y: 220 },
      data: {
        nodeInfo: {
          node_id: "database_source",
          display_name: "Weather (NC Historical)",
          category: "Sources",
          endpoint: "",
          description: "Annual weather summaries from the MLPlayground database",
          inputs: [],
          outputs: ["dataframe"],
          params: [],
          params_schema: dbSchema,
        },
        params: { datasource_key: "weather", filters_json: "{}", limit: 10000 },
      },
    } satisfies GraphFlowNode,

    {
      id: "s_soil",
      type: "graphNode",
      position: { x: 50, y: 390 },
      data: {
        nodeInfo: {
          node_id: "database_source",
          display_name: "Soil (NC)",
          category: "Sources",
          endpoint: "",
          description: "Soil property data from the MLPlayground database",
          inputs: [],
          outputs: ["dataframe"],
          params: [],
          params_schema: dbSchema,
        },
        params: { datasource_key: "soil", filters_json: "{}", limit: 5000 },
      },
    } satisfies GraphFlowNode,

    // ── FILTERS ─────────────────────────────────────────────────────────────

    {
      id: "f_state",
      type: "graphNode",
      position: { x: 310, y: 50 },
      data: {
        nodeInfo: {
          node_id: "filter",
          display_name: "Filter: NC",
          category: "Transforms",
          endpoint: "",
          description: "Keep only North Carolina rows",
          inputs: ["dataframe"],
          outputs: ["dataframe"],
          params: [],
          params_schema: filterSchema,
        },
        params: { column: "state", operator: "==", value: "North Carolina" },
      },
    } satisfies GraphFlowNode,

    {
      id: "f_crop",
      type: "graphNode",
      position: { x: 560, y: 50 },
      data: {
        nodeInfo: {
          node_id: "filter",
          display_name: "Filter: Corn",
          category: "Transforms",
          endpoint: "",
          description: "Keep only corn crop rows",
          inputs: ["dataframe"],
          outputs: ["dataframe"],
          params: [],
          params_schema: filterSchema,
        },
        params: { column: "crop", operator: "==", value: "CORN" },
      },
    } satisfies GraphFlowNode,

    // ── JOINS ────────────────────────────────────────────────────────────────

    {
      id: "j_weather",
      type: "graphNode",
      position: { x: 810, y: 150 },
      data: {
        nodeInfo: {
          node_id: "join",
          display_name: "Join: Yields + Weather",
          category: "Transforms",
          endpoint: "",
          description: "Inner join on year / state / county",
          inputs: ["left", "right"],
          outputs: ["dataframe"],
          params: [],
          params_schema: joinSchema,
        },
        params: { on: ["year", "state", "county"], how: "inner" },
      },
    } satisfies GraphFlowNode,

    {
      id: "j_soil",
      type: "graphNode",
      position: { x: 1050, y: 240 },
      data: {
        nodeInfo: {
          node_id: "join",
          display_name: "Join: + Soil",
          category: "Transforms",
          endpoint: "",
          description: "Left join to add soil properties",
          inputs: ["left", "right"],
          outputs: ["dataframe"],
          params: [],
          params_schema: joinSchema,
        },
        params: { on: ["state", "county"], how: "left" },
      },
    } satisfies GraphFlowNode,

    // ── FEATURE PREP ─────────────────────────────────────────────────────────

    {
      id: "t_select",
      type: "graphNode",
      position: { x: 1290, y: 240 },
      data: {
        nodeInfo: {
          node_id: "select_columns",
          display_name: "Select Features",
          category: "Transforms",
          endpoint: "",
          description: "Keep the model feature set + target",
          inputs: ["dataframe"],
          outputs: ["dataframe"],
          params: [],
          params_schema: {
            properties: {
              columns: {
                type: "array",
                items: { type: "string" },
                title: "Columns",
                default: [],
              },
            },
            required: ["columns"],
          },
        },
        params: {
          columns: [
            "year", "state", "county",
            "value",              // target: corn yield
            "avg_temp",           // annual average temperature
            "precipitation",      // annual total precipitation
            "gdd",                // growing degree days
            "ph",                 // soil pH
            "organic_matter",     // soil organic matter %
            "sand_pct",           // % sand
            "clay_pct",           // % clay
          ],
        },
      },
    } satisfies GraphFlowNode,

    {
      id: "t_dropna",
      type: "graphNode",
      position: { x: 1530, y: 240 },
      data: {
        nodeInfo: {
          node_id: "drop_na",
          display_name: "Drop NA",
          category: "Transforms",
          endpoint: "",
          description: "Remove any rows with missing values",
          inputs: ["dataframe"],
          outputs: ["dataframe"],
          params: [],
          params_schema: {
            properties: {
              columns: {
                type: "array",
                items: { type: "string" },
                title: "Subset Columns (empty = all)",
                default: [],
              },
            },
          },
        },
        params: { columns: [] },
      },
    } satisfies GraphFlowNode,

    // ── TRAINING ─────────────────────────────────────────────────────────────

    {
      id: "m_trainer",
      type: "graphNode",
      position: { x: 1770, y: 160 },
      data: {
        nodeInfo: {
          node_id: "trainer",
          display_name: "Train Corn Yield Model",
          category: "Modeling",
          endpoint: "",
          description:
            "Random Forest regression model — predicts corn yield (Bu/Acre) from weather and soil features.",
          inputs: ["dataframe"],
          outputs: ["model", "metrics", "artifact_path", "feature_names"],
          params: [],
          params_schema: {
            properties: {
              model_type: {
                type: "string",
                title: "Model Type",
                enum: ["linear_regression", "random_forest", "gradient_boosting"],
                default: "random_forest",
              },
              target_column: {
                type: "string",
                title: "Target Column",
                default: "value",
                description: "Column to predict (crop yield).",
              },
              feature_columns: {
                type: "array",
                items: { type: "string" },
                title: "Feature Columns",
                default: [],
                description:
                  "Numeric feature columns. Leave empty to auto-select all numeric columns except target.",
              },
              test_size: { type: "number", title: "Test Fraction", default: 0.2 },
              random_state: { type: "integer", title: "Random Seed", default: 42 },
            },
          },
        },
        params: {
          model_type: "random_forest",
          target_column: "value",
          feature_columns: [
            "avg_temp", "precipitation", "gdd",
            "ph", "organic_matter", "sand_pct", "clay_pct",
          ],
          test_size: 0.2,
          random_state: 42,
        },
      },
    } satisfies GraphFlowNode,

    // ── RESIDUAL ANALYSIS ─────────────────────────────────────────────────────
    // Predict on the full clean training set to visualise fit quality.

    {
      id: "r_pred",
      type: "graphNode",
      position: { x: 2010, y: 50 },
      data: {
        nodeInfo: predictorNodeInfo("Predict (Training Set)"),
        params: {
          target_column: "value",
          feature_columns: [],        // auto from feature_names input
          id_columns: ["year", "county"],
          output_column_name: "predicted_yield",
        },
      },
    } satisfies GraphFlowNode,

    {
      id: "r_plot",
      type: "graphNode",
      position: { x: 2250, y: 50 },
      data: {
        nodeInfo: {
          node_id: "plot",
          display_name: "Plot: Actual vs Predicted",
          category: "Visualization",
          endpoint: "",
          description:
            "Residual scatter — points on the diagonal indicate perfect fit.",
          inputs: ["dataframe"],
          outputs: ["figure"],
          params: [],
          params_schema: plotSchema,
        },
        params: {
          plot_type: "scatter",
          x_column: "actual",
          y_column: "predicted_yield",
          color_column: "year",
          title: "Actual vs Predicted Corn Yield (NC, Training Set)",
        },
      },
    } satisfies GraphFlowNode,

    // ── 2026 YIELD FORECAST ───────────────────────────────────────────────────
    // Fetch NOAA historical + 2026 weather → prep → predict → plot time series.

    {
      id: "n_noaa",
      type: "graphNode",
      position: { x: 1770, y: 430 },
      data: {
        nodeInfo: {
          node_id: "remote_fetch",
          display_name: "NOAA Weather (NC 2015–2024)",
          category: "Sources",
          endpoint: "",
          description:
            "Annual GSOY climate for NC through 2024 (last completed year). The prep node extrapolates 2025 & 2026. Requires NOAA_CDO_TOKEN env var.",
          inputs: [],
          outputs: ["dataframe"],
          params: ["datasource_key", "scope_params_json"],
          params_schema: {
            properties: {
              datasource_key: {
                type: "string",
                title: "Datasource Key",
                default: "noaa_gsoy",
              },
              scope_params_json: {
                type: "string",
                title: "Scope Params (JSON)",
                description: "Parameters passed to the noaa_gsoy datasource fetch().",
                default: "{}",
              },
            },
            required: ["datasource_key"],
          },
        },
        params: {
          datasource_key: "noaa_gsoy",
          scope_params_json: JSON.stringify({
            state: "NC",
            start_year: 2015,
            end_year: 2024,   // NOAA CDO API only serves completed calendar years
            variables: ["TAVG", "PRCP"],
          }),
        },
        label: "NOAA NC (2015–2024)",
      },
    } satisfies GraphFlowNode,

    {
      id: "n_prep",
      type: "graphNode",
      position: { x: 2010, y: 430 },
      data: {
        nodeInfo: {
          node_id: "python_code",
          display_name: "Prep NOAA for Prediction",
          category: "Transforms",
          endpoint: "",
          description:
            "Rename NOAA columns, approximate GDD, and fill in default NC soil values to match the training feature schema.",
          inputs: ["dataframe"],
          outputs: ["dataframe"],
          params: ["code", "timeout_seconds"],
          params_schema: {
            properties: {
              code: {
                type: "string",
                title: "Code",
                description:
                  "df = NOAA dataframe. Assign output to result. pd and np are available.",
                default: "result = df.copy()",
                ui_widget: "monaco",
                language: "python",
              },
              timeout_seconds: {
                type: "integer",
                title: "Timeout (s)",
                default: 30,
              },
            },
          },
        },
        params: {
          code: NOAA_PREP_CODE,
          timeout_seconds: 30,
        },
      },
    } satisfies GraphFlowNode,

    {
      id: "n_pred",
      type: "graphNode",
      position: { x: 2250, y: 430 },
      data: {
        nodeInfo: predictorNodeInfo("Predict 2026 Yield"),
        params: {
          target_column: "",          // no actual data for 2026 — pure inference
          feature_columns: [],        // auto from feature_names input
          id_columns: ["year", "state"],
          output_column_name: "predicted_yield",
        },
      },
    } satisfies GraphFlowNode,

    {
      id: "n_plot",
      type: "graphNode",
      position: { x: 2490, y: 430 },
      data: {
        nodeInfo: {
          node_id: "plot",
          display_name: "Plot: Yield Forecast 2015–2026",
          category: "Visualization",
          endpoint: "",
          description:
            "Line chart of predicted NC corn yield — 2015 to 2026. The rightmost point is the 2026 forecast.",
          inputs: ["dataframe"],
          outputs: ["figure"],
          params: [],
          params_schema: plotSchema,
        },
        params: {
          plot_type: "line",
          x_column: "year",
          y_column: "predicted_yield",
          color_column: "",
          title: "NC Corn Yield Forecast 2015–2026 (2025–2026 extrapolated)",
        },
      },
    } satisfies GraphFlowNode,
  ],

  edges: [
    // Sources → Filters
    {
      id: "e_yields_fstate",
      source: "s_yields", sourceHandle: "dataframe",
      target: "f_state",  targetHandle: "dataframe",
    } satisfies Edge,
    {
      id: "e_fstate_fcrop",
      source: "f_state", sourceHandle: "dataframe",
      target: "f_crop",  targetHandle: "dataframe",
    } satisfies Edge,

    // Filtered corn → Join1 (left)
    {
      id: "e_fcrop_jweather",
      source: "f_crop",    sourceHandle: "dataframe",
      target: "j_weather", targetHandle: "left",
    } satisfies Edge,
    // Weather → Join1 (right)
    {
      id: "e_weather_jweather",
      source: "s_weather", sourceHandle: "dataframe",
      target: "j_weather", targetHandle: "right",
    } satisfies Edge,

    // Join1 → Join2 (left)
    {
      id: "e_jweather_jsoil",
      source: "j_weather", sourceHandle: "dataframe",
      target: "j_soil",    targetHandle: "left",
    } satisfies Edge,
    // Soil → Join2 (right)
    {
      id: "e_soil_jsoil",
      source: "s_soil", sourceHandle: "dataframe",
      target: "j_soil", targetHandle: "right",
    } satisfies Edge,

    // Join2 → Select → DropNA → Trainer
    {
      id: "e_jsoil_select",
      source: "j_soil",   sourceHandle: "dataframe",
      target: "t_select", targetHandle: "dataframe",
    } satisfies Edge,
    {
      id: "e_select_dropna",
      source: "t_select", sourceHandle: "dataframe",
      target: "t_dropna", targetHandle: "dataframe",
    } satisfies Edge,
    {
      id: "e_dropna_trainer",
      source: "t_dropna",  sourceHandle: "dataframe",
      target: "m_trainer", targetHandle: "dataframe",
    } satisfies Edge,

    // Trainer → Predict (training data) — residual analysis
    {
      id: "e_trainer_model_rpred",
      source: "m_trainer", sourceHandle: "model",
      target: "r_pred",    targetHandle: "model",
    } satisfies Edge,
    {
      id: "e_dropna_rpred",
      source: "t_dropna", sourceHandle: "dataframe",
      target: "r_pred",   targetHandle: "dataframe",
    } satisfies Edge,
    {
      id: "e_trainer_feat_rpred",
      source: "m_trainer", sourceHandle: "feature_names",
      target: "r_pred",    targetHandle: "feature_names",
    } satisfies Edge,

    // Residual predictor → Plot
    {
      id: "e_rpred_rplot",
      source: "r_pred", sourceHandle: "predictions",
      target: "r_plot", targetHandle: "dataframe",
    } satisfies Edge,

    // NOAA fetch → Prep code
    {
      id: "e_noaa_prep",
      source: "n_noaa", sourceHandle: "dataframe",
      target: "n_prep", targetHandle: "dataframe",
    } satisfies Edge,

    // Trainer → Predict 2026 (model + feature_names from trainer)
    {
      id: "e_trainer_model_npred",
      source: "m_trainer", sourceHandle: "model",
      target: "n_pred",    targetHandle: "model",
    } satisfies Edge,
    {
      id: "e_trainer_feat_npred",
      source: "m_trainer", sourceHandle: "feature_names",
      target: "n_pred",    targetHandle: "feature_names",
    } satisfies Edge,
    // Prepped NOAA data → Predict 2026
    {
      id: "e_prep_npred",
      source: "n_prep", sourceHandle: "dataframe",
      target: "n_pred", targetHandle: "dataframe",
    } satisfies Edge,

    // Predict 2026 → Plot
    {
      id: "e_npred_nplot",
      source: "n_pred", sourceHandle: "predictions",
      target: "n_plot", targetHandle: "dataframe",
    } satisfies Edge,
  ],
}
