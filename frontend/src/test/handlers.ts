import { http, HttpResponse } from "msw"
import { setupServer } from "msw/node"

export const YIELDS_RESPONSE = {
  data: [
    { id: 1, year: 2020, county: "Wake", state: "North Carolina", crop: "CORN", value: 120.5, unit: "BU / ACRE" },
    { id: 2, year: 2021, county: "Wake", state: "North Carolina", crop: "CORN", value: 130.2, unit: "BU / ACRE" },
  ],
  count: 2,
}

export const WEATHER_RESPONSE = {
  data: [
    { id: 1, year: 2020, county: "Wake", state: "North Carolina", avg_temp: 18.5, precipitation: 450.0 },
  ],
  count: 1,
}

export const SOIL_RESPONSE = {
  data: [
    { id: 1, county: "Wake", state: "North Carolina", ph: 6.2, sand_pct: 55.0, clay_pct: 20.0 },
  ],
  count: 1,
}

export const DAILY_WEATHER_RESPONSE = {
  data: [
    { id: 1, year: 2020, day_of_year: 1, date: "2020-01-01", county: "Wake", state: "North Carolina", tmax: 12.5, tmin: 3.2, prcp: 0.0, srad: 85.0, vp: 900.0, dayl: 34560.0 },
  ],
  count: 1,
}

export const DATASOURCES_RESPONSE = {
  data: [
    { key: "yields",        label: "Crop Yields",     endpoint: "/api/v1/data/yields",        columns: ["year","state","county","crop","value"], scope_params: [{ name: "states", type: "string_list", label: "States", default: ["North Carolina"] }, { name: "start_year", type: "integer", label: "Start Year", default: 1980 }, { name: "end_year", type: "integer", label: "End Year", default: 2022 }], description: "USDA NASS crop yields." },
    { key: "weather",       label: "Annual Weather",  endpoint: "/api/v1/data/weather",       columns: ["year","state","county","avg_temp"],     scope_params: [],                          description: "Daymet annual weather." },
    { key: "soil",          label: "Soil Properties", endpoint: "/api/v1/data/soil",          columns: ["state","county","ph"],                  scope_params: [],                          description: "SSURGO soil." },
    { key: "daily_weather", label: "Daily Weather",   endpoint: "/api/v1/data/daily_weather", columns: ["year","day_of_year","date","tmax"],     scope_params: [],                          description: "Daymet daily." },
  ],
  count: 4,
}

export const MODEL_TYPES_RESPONSE: {key: string; label: string; kind: string; description: string; supports_predict: boolean}[] = [
  { key: "random_forest",     label: "Random Forest",                    kind: "sklearn",     description: "Ensemble trees.",    supports_predict: true },
  { key: "gradient_boosting", label: "Gradient Boosting",                kind: "sklearn",     description: "Boosted trees.",     supports_predict: true },
  { key: "linear_regression", label: "Linear Regression",                kind: "sklearn",     description: "Linear baseline.",   supports_predict: true },
  { key: "lstm",              label: "LSTM (Sequence Neural Network)",    kind: "pytorch",     description: "Recurrent NN.",      supports_predict: false },
  { key: "pycaret",          label: "AutoML (PyCaret)",                  kind: "pycaret",     description: "AutoML best model.", supports_predict: true },
]

export const MODEL_RUNS_RESPONSE = {
  data: [
    { id: 1, run_id: "abc-123-def", model_type: "random_forest", feature_columns: '["avg_temp","precipitation"]', filters: '{"state":"North Carolina","crop":"CORN","start_year":2000,"end_year":2022}', r2: 0.72, rmse: 12.3, n_samples: 200, created_at: "2026-01-15T10:00:00" },
  ],
  count: 1,
}

export const GRAPH_NODES_RESPONSE: {
  node_id: string; display_name: string; category: string; endpoint: string
  description: string; inputs: string[]; outputs: string[]; params: string[]
  params_schema: Record<string, unknown>
}[] = [
  {
    node_id: "csv_source",
    display_name: "CSV Source",
    category: "Sources",
    endpoint: "/api/v1/graphs/execute/csv_source",
    description: "Load a CSV file into a DataFrame.",
    inputs: [],
    outputs: ["df"],
    params: [],
    params_schema: {
      properties: { file_path: { type: "string", title: "File Path", default: "" }, rows: { type: "integer", title: "Max Rows", default: 1000 } },
      required: ["file_path"],
    },
  },
  {
    node_id: "filter",
    display_name: "Filter",
    category: "Transforms",
    endpoint: "/api/v1/graphs/execute/filter",
    description: "Filter rows by a column condition.",
    inputs: ["df"],
    outputs: ["df"],
    params: [],
    params_schema: {
      properties: {
        column: { type: "string", title: "Column" },
        op: { type: "string", title: "Operator", enum: ["==", "!=", ">", "<", ">=", "<="] },
        value: { type: "string", title: "Value" },
      },
      required: ["column", "op", "value"],
    },
  },
  {
    node_id: "preview",
    display_name: "Preview",
    category: "Utilities",
    endpoint: "/api/v1/graphs/execute/preview",
    description: "Preview first N rows of a DataFrame.",
    inputs: ["df"],
    outputs: [],
    params: [],
    params_schema: {
      properties: { rows: { type: "integer", title: "Rows", default: 10 } },
    },
  },
  {
    node_id: "database_source",
    display_name: "Database Source",
    category: "Sources",
    endpoint: "/api/v1/graphs/execute/database_source",
    description: "Query a registered datasource.",
    inputs: [],
    outputs: ["dataframe"],
    params: [],
    params_schema: {
      properties: {
        datasource_key: { type: "string", title: "Datasource", default: "" },
        filters_json: { type: "string", title: "Filters", default: "{}" },
        limit: { type: "integer", title: "Limit", default: 50000 },
      },
    },
  },
  {
    node_id: "join",
    display_name: "Join",
    category: "Transforms",
    endpoint: "/api/v1/graphs/execute/join",
    description: "Join two DataFrames.",
    inputs: ["left", "right"],
    outputs: ["dataframe"],
    params: [],
    params_schema: {
      properties: {
        on: { type: "array", items: { type: "string" }, title: "On" },
        how: { type: "string", title: "How", enum: ["inner", "left", "right", "outer"], default: "inner" },
      },
      required: ["on"],
    },
  },
  {
    node_id: "select_columns",
    display_name: "Select Columns",
    category: "Transforms",
    endpoint: "/api/v1/graphs/execute/select_columns",
    description: "Keep specific columns.",
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
  {
    node_id: "drop_na",
    display_name: "Drop NA",
    category: "Transforms",
    endpoint: "/api/v1/graphs/execute/drop_na",
    description: "Remove rows with missing values.",
    inputs: ["dataframe"],
    outputs: ["dataframe"],
    params: [],
    params_schema: {
      properties: {
        columns: { type: "array", items: { type: "string" }, title: "Columns", default: [] },
      },
    },
  },
  {
    node_id: "trainer",
    display_name: "Trainer",
    category: "Modeling",
    endpoint: "/api/v1/graphs/execute/trainer",
    description: "Train a machine learning model.",
    inputs: ["dataframe"],
    outputs: ["model", "metrics", "artifact_path", "feature_names"],
    params: [],
    params_schema: {
      properties: {
        model_type: { type: "string", title: "Model Type", enum: ["linear_regression", "random_forest", "gradient_boosting"], default: "random_forest" },
        target_column: { type: "string", title: "Target Column", default: "crop_yield" },
        feature_columns: { type: "array", items: { type: "string" }, title: "Feature Columns", default: [] },
        test_size: { type: "number", title: "Test Size", default: 0.2 },
        random_state: { type: "integer", title: "Random State", default: 42 },
      },
    },
  },
]

export const GRAPH_VALIDATE_RESPONSE = { valid: true, node_count: 3, edge_count: 2, ordered_node_ids: ["n1", "n2", "n3"] }

export const GRAPH_RUN_RESPONSE = { run_id: "test-run-001", status: "pending" }

export const GRAPH_STATUS_RESPONSE = {
  run_id: "test-run-001",
  status: "done",
  node_statuses: { n1: "done", n2: "done", n3: "cached" },
}

export const GRAPH_RESULT_RESPONSE = {
  run_id: "test-run-001",
  status: "done",
  result: {
    n3: {
      preview: { rows: [{ col1: "a", col2: 1 }, { col1: "b", col2: 2 }], columns: ["col1", "col2"] },
      dataframe: { __type__: "dataframe", shape: [2, 2], path: "/tmp/test.parquet" },
    },
  },
  node_statuses: { n1: "done", n2: "done", n3: "done" },
}

export const DATASOURCE_KEYS_RESPONSE = ["yields", "weather", "soil", "daily_weather"]

export const DATASOURCE_INFO_YIELDS = {
  key: "yields",
  columns: [
    { name: "year", type_str: "int" },
    { name: "state", type_str: "str" },
    { name: "county", type_str: "str" },
    { name: "crop", type_str: "str" },
  ],
  query_params: ["state", "county", "year", "crop"],
}

export const SAVED_WORKFLOWS_RESPONSE: { id: number; name: string; description: string | null; created_at: string; updated_at: string }[] = [
  { id: 1, name: "My Workflow", description: null, created_at: "2026-01-01T00:00:00", updated_at: "2026-01-01T00:00:00" },
]

export const SAVED_WORKFLOW_DETAIL = {
  id: 1,
  name: "My Workflow",
  description: null,
  created_at: "2026-01-01T00:00:00",
  updated_at: "2026-01-01T00:00:00",
  graph_spec: JSON.stringify({
    nodes: [
      { id: "n1", type: "graphNode", position: { x: 0, y: 0 }, data: { nodeInfo: { node_id: "csv_source", display_name: "CSV Source", category: "Sources", endpoint: "", description: "", inputs: [], outputs: ["df"], params: [], params_schema: { properties: { file_path: { type: "string", title: "File Path", default: "" } } } }, params: { file_path: "/data/sample.csv" } } },
    ],
    edges: [],
  }),
}

export const defaultHandlers = [
  http.get("/api/v1/graphs/nodes", () =>
    HttpResponse.json({ data: GRAPH_NODES_RESPONSE, count: GRAPH_NODES_RESPONSE.length })
  ),
  http.post("/api/v1/graphs/validate", () =>
    HttpResponse.json(GRAPH_VALIDATE_RESPONSE)
  ),
  http.post("/api/v1/graphs/run", () =>
    HttpResponse.json(GRAPH_RUN_RESPONSE)
  ),
  http.get("/api/v1/graphs/:runId/status", () =>
    HttpResponse.json(GRAPH_STATUS_RESPONSE)
  ),
  http.get("/api/v1/graphs/:runId/result", () =>
    HttpResponse.json(GRAPH_RESULT_RESPONSE)
  ),
  http.get("/api/v1/graphs/workflows", () =>
    HttpResponse.json(SAVED_WORKFLOWS_RESPONSE)
  ),
  http.get("/api/v1/graphs/workflows/:id", () =>
    HttpResponse.json(SAVED_WORKFLOW_DETAIL)
  ),
  http.post("/api/v1/graphs/workflows", () =>
    HttpResponse.json({ ...SAVED_WORKFLOW_DETAIL, id: 2, name: "New Workflow" }, { status: 201 })
  ),
  http.put("/api/v1/graphs/workflows/:id", () =>
    HttpResponse.json(SAVED_WORKFLOW_DETAIL)
  ),
  http.delete("/api/v1/graphs/workflows/:id", () =>
    new HttpResponse(null, { status: 204 })
  ),
  http.get("/api/v1/graphs/datasource-keys", () =>
    HttpResponse.json(DATASOURCE_KEYS_RESPONSE)
  ),
  http.get("/api/v1/graphs/datasource-info/:key", () =>
    HttpResponse.json(DATASOURCE_INFO_YIELDS)
  ),
  http.post("/api/v1/graphs/upload", () =>
    HttpResponse.json({ path: "/app/artifacts/uploads/test.csv", filename: "test.csv" })
  ),
  http.get("/api/v1/utils/health-check/", () =>
    HttpResponse.json({ status: "ok" })
  ),
  http.get("/api/v1/data/yields/distinct/crop", () =>
    HttpResponse.json(["CORN", "SOYBEANS", "WHEAT"])
  ),
  http.get("/api/v1/data/yields/distinct/state", () =>
    HttpResponse.json(["North Carolina", "Iowa", "Illinois"])
  ),
  http.get("/api/v1/data/yields", () =>
    HttpResponse.json(YIELDS_RESPONSE)
  ),
  http.get("/api/v1/data/weather", () =>
    HttpResponse.json(WEATHER_RESPONSE)
  ),
  http.get("/api/v1/data/soil", () =>
    HttpResponse.json(SOIL_RESPONSE)
  ),
  http.get("/api/v1/data/daily_weather", () =>
    HttpResponse.json(DAILY_WEATHER_RESPONSE)
  ),
  http.get("/api/v1/datasources/", () =>
    HttpResponse.json(DATASOURCES_RESPONSE)
  ),
  http.get("/api/v1/models/types", () =>
    HttpResponse.json(MODEL_TYPES_RESPONSE)
  ),
  http.get("/api/v1/models/", () =>
    HttpResponse.json(MODEL_RUNS_RESPONSE)
  ),
  http.post("/api/v1/ingest/run", () =>
    HttpResponse.json({ job_id: "test-job-123", status: "queued", progress: 0, message: "Queued", errors: [] })
  ),
  http.get("/api/v1/ingest/status/:jobId", () =>
    HttpResponse.json({ job_id: "test-job-123", status: "done", progress: 1.0, message: "Complete", errors: [] })
  ),
  http.get("/api/v1/models/features", () =>
    HttpResponse.json([
      "avg_temp", "precipitation", "gdd", "vp", "srad",
      "ph", "organic_matter", "sand_pct", "clay_pct",
    ])
  ),
  // Default: training returns no data (individual tests override this)
  http.post("/api/v1/models/train", () =>
    HttpResponse.json({ detail: "No data" }, { status: 404 })
  ),
  // Default: predict returns no data (individual tests override this)
  http.post("/api/v1/models/predict", () =>
    HttpResponse.json({ detail: "No data" }, { status: 404 })
  ),
  http.post(/\/api\/v1\/models\/.+\/predict/, () =>
    HttpResponse.json({ detail: "No data" }, { status: 404 })
  ),
]

export const server = setupServer(...defaultHandlers)
