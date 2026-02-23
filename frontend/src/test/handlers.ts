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
  http.get("/api/v1/ingest/status", () =>
    HttpResponse.json({ status: "idle" })
  ),
  http.post("/api/v1/ingest/trigger", () =>
    HttpResponse.json({ message: "Data ingestion started in background." })
  ),
]

export const server = setupServer(...defaultHandlers)
