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

export const defaultHandlers = [
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
