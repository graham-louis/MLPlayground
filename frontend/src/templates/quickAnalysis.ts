/**
 * Quick Analysis Template
 *
 * A simple, effective 6-node pipeline:
 *   Database Source → Filter → Drop NA → Train Model → Predict → Plot
 *
 * This is the "hello world" of MLPlayground graph workflows.
 * It loads a single datasource, applies a basic filter, cleans
 * the data, trains a Random Forest, and visualises residuals.
 */
import type { Edge } from "@xyflow/react"
import type { GraphFlowNode, GraphTemplate } from "../graphTypes"

/* ── Reusable schema fragments ────────────────────────────────── */
const dbSchema = {
  properties: {
    datasource_key: { type: "string", title: "Datasource" },
    filters_json: { type: "string", title: "Filters (JSON)", default: "{}" },
    limit: { type: "integer", title: "Limit", default: 50000 },
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
    },
    value: { type: "string", title: "Value" },
  },
  required: ["column", "operator", "value"],
}

const dropNaSchema = {
  properties: {
    columns: {
      type: "array",
      items: { type: "string" },
      title: "Columns",
      default: [],
    },
  },
}

const trainerSchema = {
  properties: {
    model_type: {
      type: "string",
      title: "Model Type",
      enum: ["linear_regression", "random_forest", "gradient_boosting"],
      default: "random_forest",
    },
    target_column: { type: "string", title: "Target Column", default: "value" },
    feature_columns: {
      type: "array",
      items: { type: "string" },
      title: "Feature Columns",
      default: [],
    },
    test_size: { type: "number", title: "Test Size", default: 0.2 },
    random_state: { type: "integer", title: "Random State", default: 42 },
  },
}

const plotSchema = {
  properties: {
    plot_type: {
      type: "string",
      title: "Plot Type",
      enum: ["scatter", "line", "histogram", "bar", "box"],
      default: "scatter",
    },
    x_column: { type: "string", title: "X Column" },
    y_column: { type: "string", title: "Y Column" },
    color_column: { type: "string", title: "Color Column" },
    title: { type: "string", title: "Title" },
  },
}

const predictorSchema = {
  properties: {
    target_column: {
      type: "string",
      title: "Target Column",
      default: "value",
    },
    feature_columns: {
      type: "array",
      items: { type: "string" },
      title: "Feature Columns",
      default: [],
    },
    id_columns: {
      type: "array",
      items: { type: "string" },
      title: "ID Columns",
      default: [],
    },
    output_column_name: {
      type: "string",
      title: "Output Column Name",
      default: "predicted_yield",
    },
  },
}

/* ── Nodes ────────────────────────────────────────────────────── */
export const quickAnalysisTemplate: GraphTemplate = {
  nodes: [
    /* 1 — Load data */
    {
      id: "qa1",
      type: "graphNode",
      position: { x: 50, y: 180 },
      data: {
        nodeInfo: {
          node_id: "database_source",
          display_name: "Load Data",
          category: "Sources",
          endpoint: "",
          description: "Load a datasource from the database",
          inputs: [],
          outputs: ["dataframe"],
          params: [],
          params_schema: dbSchema,
        },
        params: {
          datasource_key: "yields",
          filters_json: '{"state": "North Carolina"}',
          limit: 50000,
        },
      },
    } satisfies GraphFlowNode,

    /* 2 — Filter rows */
    {
      id: "qa2",
      type: "graphNode",
      position: { x: 320, y: 180 },
      data: {
        nodeInfo: {
          node_id: "filter",
          display_name: "Filter Rows",
          category: "Transforms",
          endpoint: "",
          description: "Keep only rows matching a condition",
          inputs: ["dataframe"],
          outputs: ["dataframe"],
          params: [],
          params_schema: filterSchema,
        },
        params: { column: "crop", operator: "==", value: "CORN" },
      },
    } satisfies GraphFlowNode,

    /* 3 — Drop NA */
    {
      id: "qa3",
      type: "graphNode",
      position: { x: 590, y: 180 },
      data: {
        nodeInfo: {
          node_id: "drop_na",
          display_name: "Drop NA",
          category: "Transforms",
          endpoint: "",
          description: "Remove rows with missing values",
          inputs: ["dataframe"],
          outputs: ["dataframe"],
          params: [],
          params_schema: dropNaSchema,
        },
        params: { columns: [] },
      },
    } satisfies GraphFlowNode,

    /* 4 — Train model */
    {
      id: "qa4",
      type: "graphNode",
      position: { x: 860, y: 120 },
      data: {
        nodeInfo: {
          node_id: "trainer",
          display_name: "Train Model",
          category: "Modeling",
          endpoint: "",
          description: "Train a regression model on the cleaned data",
          inputs: ["dataframe"],
          outputs: ["model", "metrics", "artifact_path", "feature_names"],
          params: [],
          params_schema: trainerSchema,
        },
        params: {
          model_type: "random_forest",
          target_column: "value",
          feature_columns: [],
          test_size: 0.2,
          random_state: 42,
        },
      },
    } satisfies GraphFlowNode,

    /* 5 — Predict (to get residuals for the plot) */
    {
      id: "qa5",
      type: "graphNode",
      position: { x: 1130, y: 180 },
      data: {
        nodeInfo: {
          node_id: "predictor",
          display_name: "Predict",
          category: "Modeling",
          endpoint: "",
          description:
            "Generate predictions + residuals for plotting",
          inputs: ["model", "dataframe", "feature_names"],
          outputs: ["predictions"],
          params: [],
          params_schema: predictorSchema,
        },
        params: {
          target_column: "value",
          feature_columns: [],
          id_columns: ["year", "county"],
          output_column_name: "predicted_yield",
        },
      },
    } satisfies GraphFlowNode,

    /* 6 — Plot results */
    {
      id: "qa6",
      type: "graphNode",
      position: { x: 1400, y: 180 },
      data: {
        nodeInfo: {
          node_id: "plot",
          display_name: "Plot Results",
          category: "Visualization",
          endpoint: "",
          description: "Scatter plot of actual vs predicted values",
          inputs: ["dataframe"],
          outputs: ["figure"],
          params: [],
          params_schema: plotSchema,
        },
        params: {
          plot_type: "scatter",
          x_column: "actual",
          y_column: "predicted_yield",
          color_column: "",
          title: "Actual vs Predicted",
        },
      },
    } satisfies GraphFlowNode,
  ],

  /* ── Edges ──────────────────────────────────────────────────── */
  edges: [
    // Source → Filter
    {
      id: "e-qa1-qa2",
      source: "qa1",
      sourceHandle: "dataframe",
      target: "qa2",
      targetHandle: "dataframe",
    } satisfies Edge,
    // Filter → Drop NA
    {
      id: "e-qa2-qa3",
      source: "qa2",
      sourceHandle: "dataframe",
      target: "qa3",
      targetHandle: "dataframe",
    } satisfies Edge,
    // Drop NA → Trainer
    {
      id: "e-qa3-qa4",
      source: "qa3",
      sourceHandle: "dataframe",
      target: "qa4",
      targetHandle: "dataframe",
    } satisfies Edge,
    // Trainer model → Predictor
    {
      id: "e-qa4m-qa5",
      source: "qa4",
      sourceHandle: "model",
      target: "qa5",
      targetHandle: "model",
    } satisfies Edge,
    // Trainer feature_names → Predictor
    {
      id: "e-qa4f-qa5",
      source: "qa4",
      sourceHandle: "feature_names",
      target: "qa5",
      targetHandle: "feature_names",
    } satisfies Edge,
    // Drop NA dataframe → Predictor (same cleaned data for residual analysis)
    {
      id: "e-qa3-qa5",
      source: "qa3",
      sourceHandle: "dataframe",
      target: "qa5",
      targetHandle: "dataframe",
    } satisfies Edge,
    // Predictor predictions → Plot
    {
      id: "e-qa5-qa6",
      source: "qa5",
      sourceHandle: "predictions",
      target: "qa6",
      targetHandle: "dataframe",
    } satisfies Edge,
  ],
}
