import type { Edge } from "@xyflow/react"
import type { GraphFlowNode, GraphTemplate } from "../graphTypes"

const dbSchema = {
  properties: {
    datasource_key: { type: "string", title: "Datasource" },
    filters_json: { type: "string", title: "Filters (JSON)", default: "{}" },
    limit: { type: "integer", title: "Limit", default: 5000 },
  },
  required: ["datasource_key"],
}

const joinSchema = {
  properties: {
    on: { type: "array", items: { type: "string" }, title: "On" },
    how: {
      type: "string",
      title: "How",
      enum: ["inner", "left", "right", "outer"],
      default: "inner",
    },
  },
  required: ["on"],
}

export const yieldPredictionTemplate: GraphTemplate = {
  nodes: [
    {
      id: "t1",
      type: "graphNode",
      position: { x: 50, y: 50 },
      data: {
        nodeInfo: {
          node_id: "database_source",
          display_name: "Yields",
          category: "Sources",
          endpoint: "",
          description: "Crop yields",
          inputs: [],
          outputs: ["dataframe"],
          params: [],
          params_schema: dbSchema,
        },
        params: { datasource_key: "yields", filters_json: "{}", limit: 5000 },
      },
    } satisfies GraphFlowNode,
    {
      id: "t2",
      type: "graphNode",
      position: { x: 50, y: 220 },
      data: {
        nodeInfo: {
          node_id: "database_source",
          display_name: "Weather",
          category: "Sources",
          endpoint: "",
          description: "Annual weather",
          inputs: [],
          outputs: ["dataframe"],
          params: [],
          params_schema: dbSchema,
        },
        params: { datasource_key: "weather", filters_json: "{}", limit: 5000 },
      },
    } satisfies GraphFlowNode,
    {
      id: "t3",
      type: "graphNode",
      position: { x: 50, y: 390 },
      data: {
        nodeInfo: {
          node_id: "database_source",
          display_name: "Soil",
          category: "Sources",
          endpoint: "",
          description: "Soil properties",
          inputs: [],
          outputs: ["dataframe"],
          params: [],
          params_schema: dbSchema,
        },
        params: { datasource_key: "soil", filters_json: "{}", limit: 5000 },
      },
    } satisfies GraphFlowNode,
    {
      id: "t4",
      type: "graphNode",
      position: { x: 330, y: 130 },
      data: {
        nodeInfo: {
          node_id: "join",
          display_name: "Join Yields + Weather",
          category: "Transforms",
          endpoint: "",
          description: "Join on year/state/county",
          inputs: ["left", "right"],
          outputs: ["dataframe"],
          params: [],
          params_schema: joinSchema,
        },
        params: { on: ["year", "state", "county"], how: "inner" },
      },
    } satisfies GraphFlowNode,
    {
      id: "t5",
      type: "graphNode",
      position: { x: 610, y: 200 },
      data: {
        nodeInfo: {
          node_id: "join",
          display_name: "Join + Soil",
          category: "Transforms",
          endpoint: "",
          description: "Join with soil on state/county",
          inputs: ["left", "right"],
          outputs: ["dataframe"],
          params: [],
          params_schema: joinSchema,
        },
        params: { on: ["state", "county"], how: "left" },
      },
    } satisfies GraphFlowNode,
    {
      id: "t6",
      type: "graphNode",
      position: { x: 890, y: 200 },
      data: {
        nodeInfo: {
          node_id: "select_columns",
          display_name: "Select Features",
          category: "Transforms",
          endpoint: "",
          description: "Keep relevant columns",
          inputs: ["dataframe"],
          outputs: ["dataframe"],
          params: [],
          params_schema: {
            properties: {
              columns: { type: "array", items: { type: "string" }, title: "Columns" },
            },
            required: ["columns"],
          },
        },
        params: {
          columns: [
            "year", "state", "county", "crop", "value",
            "avg_temp", "precipitation", "gdd",
            "ph", "organic_matter", "sand_pct", "clay_pct",
          ],
        },
      },
    } satisfies GraphFlowNode,
    {
      id: "t7",
      type: "graphNode",
      position: { x: 1120, y: 200 },
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
          params_schema: {
            properties: {
              columns: { type: "array", items: { type: "string" }, title: "Columns", default: [] },
            },
          },
        },
        params: { columns: [] },
      },
    } satisfies GraphFlowNode,
    {
      id: "t9",
      type: "graphNode",
      position: { x: 1350, y: 150 },
      data: {
        nodeInfo: {
          node_id: "trainer",
          display_name: "Train Yield Model",
          category: "Modeling",
          endpoint: "",
          description: "Random forest yield predictor",
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
              target_column: { type: "string", title: "Target Column", default: "crop_yield" },
              feature_columns: { type: "array", items: { type: "string" }, title: "Feature Columns", default: [] },
              test_size: { type: "number", title: "Test Size", default: 0.2 },
              random_state: { type: "integer", title: "Random State", default: 42 },
            },
          },
        },
        params: {
          model_type: "random_forest",
          target_column: "value",
          feature_columns: ["avg_temp", "precipitation", "gdd", "ph", "organic_matter", "sand_pct", "clay_pct"],
          test_size: 0.2,
          random_state: 42,
        },
      },
    } satisfies GraphFlowNode,
  ],
  edges: [
    { id: "et1-t4", source: "t1", sourceHandle: "dataframe", target: "t4", targetHandle: "left" } satisfies Edge,
    { id: "et2-t4", source: "t2", sourceHandle: "dataframe", target: "t4", targetHandle: "right" } satisfies Edge,
    { id: "et4-t5", source: "t4", sourceHandle: "dataframe", target: "t5", targetHandle: "left" } satisfies Edge,
    { id: "et3-t5", source: "t3", sourceHandle: "dataframe", target: "t5", targetHandle: "right" } satisfies Edge,
    { id: "et5-t6", source: "t5", sourceHandle: "dataframe", target: "t6", targetHandle: "dataframe" } satisfies Edge,
    { id: "et6-t7", source: "t6", sourceHandle: "dataframe", target: "t7", targetHandle: "dataframe" } satisfies Edge,
    { id: "et7-t9", source: "t7", sourceHandle: "dataframe", target: "t9", targetHandle: "dataframe" } satisfies Edge,
  ],
}
