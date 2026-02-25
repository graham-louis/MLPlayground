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

export const defaultHandlers = [
  http.get("/api/v1/utils/health-check/", () =>
    HttpResponse.json({ status: "ok" })
  ),
  http.get("/api/v1/yields/crops", () =>
    HttpResponse.json(["CORN", "SOYBEANS", "WHEAT"])
  ),
  http.get("/api/v1/yields/states", () =>
    HttpResponse.json(["North Carolina", "Iowa", "Illinois"])
  ),
  http.get("/api/v1/yields/", () =>
    HttpResponse.json(YIELDS_RESPONSE)
  ),
  http.get("/api/v1/weather/", () =>
    HttpResponse.json(WEATHER_RESPONSE)
  ),
  http.get("/api/v1/soil/", () =>
    HttpResponse.json(SOIL_RESPONSE)
  ),
  http.get("/api/v1/daily-weather/", () =>
    HttpResponse.json(DAILY_WEATHER_RESPONSE)
  ),
  http.get("/api/v1/ingest/status", () =>
    HttpResponse.json({ status: "idle" })
  ),
  http.post("/api/v1/ingest/trigger", () =>
    HttpResponse.json({ message: "Data ingestion started in background." })
  ),
  http.post("/api/v1/ingest/trigger-daily-weather", () =>
    HttpResponse.json({ message: "Daily weather ingest started in background." })
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
]

export const server = setupServer(...defaultHandlers)
