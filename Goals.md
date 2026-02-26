# MLPlayground — Agent Prompt & Project Specification

## Vision

MLPlayground is an extensible, researcher-friendly platform for **general-purpose tabular machine learning**. It is a digital data warehouse and modelling hub that must be **modular and dynamic**: adding a new data source or a new ML model should require touching as few files as possible, and the frontend should automatically reflect those additions without manual wiring.

The platform is **entirely domain-agnostic**. It ships with a concrete example domain (US agricultural data — crop yields, weather, soil) to demonstrate the architecture, but every component — data ingestion, exploration, model training, and prediction — must work identically for any tabular dataset. A researcher studying financial time-series, climate indices, genomics, or sensor telemetry should be able to plug in their data source and have a fully functional explore + model workflow with zero changes to core platform code.

---

## Current Architecture (as of this writing)

### Stack
- **Backend:** FastAPI (Python 3.11), SQLModel/SQLAlchemy ORM, PostgreSQL via asyncpg, Alembic migrations.
- **Frontend:** React + TypeScript, Vite bundler, TanStack Router (file-based routing), TanStack Query for data fetching, Chakra UI component library, Recharts for visualisation.
- **Infrastructure:** Docker Compose (`compose.yml`) — `backend` and `frontend` containers plus a `db` (Postgres) container. The frontend proxies `/api/` to `http://backend:8000`.

### Directory layout (key paths)
```
backend/app/
  main.py                  # FastAPI app entry point
  db_models.py            # SQLModel table definitions for the bundled example domain
  api/
    main.py                # Registers all routers onto api_router
    routes/
      training.py         # POST /api/v1/models/train  POST /api/v1/models/predict
      ingest.py            # POST /api/v1/ingest/run  GET /api/v1/ingest/status/{job_id}
      datasources.py       # GET /api/v1/datasources/  (registry metadata — to be built)
      utils.py             # GET /api/v1/utils/health-check/
      # --- example domain routes (illustrate the pattern; not hardwired to platform) ---
      yields.py            # GET /api/v1/yields/
      weather.py           # GET /api/v1/weather/
      daily_weather.py     # GET /api/v1/daily-weather/
      soil.py              # GET /api/v1/soil/
  core/
    config.py              # Pydantic Settings (reads env vars)
    db.py                  # Engine + get_session dependency
  ingest/
    runner.py              # Orchestrates bulk ingest; reads DATASOURCE_REGISTRY
    registry.py            # Central registry all datasource modules register into (to be built)
    template_datasource.py # Copy-paste template for new sources
    # --- example domain ingest modules (illustrate the pattern) ---
    yields_nass.py           # USDA NASS yield fetcher
    weather_daymet.py       # NASA NLDAS weather fetcher (annual + daily)
    soil_ssurgo.py         # USDA SSURGO soil fetcher
  alembic/
    versions/
      001_initial_schema.py
      002_add_daily_weather.py

frontend/src/
  routes/
    __root.tsx             # Root layout (nav bar)
    index.tsx              # Home / dashboard — lists registered datasources
    explore.tsx            # Data exploration — tabs driven by /api/v1/datasources/
    model.tsx              # Model training + prediction — features driven by registry
    ingest.tsx             # Ingest scope UI — datasources + scope params from registry
```

### Data models (current — agriculture example domain)
These tables ship as a working demonstration of the platform. They are **not** the platform itself; any domain can replace or extend them by following the same SQLModel pattern.

| Table | Key columns |
|---|---|
| `yields` | year, state, district, county, county_ansi, crop, value, unit |
| `weather` | year, state, county, avg_temp, precipitation, vp, srad, gdd |
| `daily_weather` | date, state, county, tmax, tmin, precip, srad, vp |
| `soil` | state, county, ph, organic_matter, sand_pct, clay_pct |

A new domain simply adds its own SQLModel tables and ingest module — the platform tables above are peers, not a prerequisite.

### API routes (current)

**Platform-level routes (always present):**
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/datasources/` | List all registered datasources with metadata (to be built) |
| POST | `/api/v1/models/train` | Train any regression/classification model against any registered datasource columns |
| POST | `/api/v1/models/predict` | Run prediction using a saved model run |
| GET | `/api/v1/models/` | List all saved model runs |
| GET | `/api/v1/models/types` | List available model type identifiers (to be built) |
| POST | `/api/v1/ingest/run` | Trigger ingestion for a selected set of datasources and scope params |
| GET | `/api/v1/ingest/status/{job_id}` | Poll ingestion job status |
| GET | `/api/v1/utils/health-check/` | Liveness probe |

**Example domain routes (agriculture — illustrate the route pattern):**
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/yields/` | Paginated yields; query params: state, crop, start_year, end_year |
| GET | `/api/v1/weather/` | Paginated annual weather; query params: state, start_year, end_year |
| GET | `/api/v1/daily-weather/` | Paginated daily weather; query params: state, county, start_date, end_date |
| GET | `/api/v1/soil/` | Paginated soil data; query params: state, county |

### ML model training (current state → target state)

**Current (agriculture-specific, to be refactored):** The `POST /api/v1/models/train` endpoint hard-joins Yield + Weather + Soil on `(year, state, county)` and accepts an agriculture-shaped `TrainRequest`. Trained models are held in memory.

**Target (domain-agnostic):** `TrainRequest` should describe the data in terms of the datasource registry — which datasources to join, which columns are features, which column is the target — not in terms of any fixed domain. Example of the target schema:
```json
{
  "datasources": ["yields", "weather", "soil"],
  "join_keys": ["year", "state", "county"],
  "feature_columns": ["avg_temp", "precipitation", "gdd", "ph", "organic_matter"],
  "target_column": "value",
  "filters": { "state": "Iowa", "crop": "CORN", "start_year": 1990, "end_year": 2022 },
  "model_type": "random_forest",
  "test_size": 0.2
}
```
The response `TrainResult` (r2, rmse, feature_importances, n_samples) is already domain-agnostic and should stay as-is.

---

## Design Principles (non-negotiable)

1. **Adding a data source must touch ≤ 5 files.** The template at `backend/app/ingest/template_datasource.py` defines the contract. Any new source must implement the same interface.
2. **Frontend tabs are data-driven.** The Explore page reads `DATA_TABS` and the Model page reads `AVAILABLE_FEATURES` from the API. Do not hardcode new sources into React — expose a `/api/v1/datasources/` metadata endpoint and drive the UI from it.
3. **All DB access through the ORM.** No raw SQL in routes. Use `sqlmodel.select` + the `get_session` dependency.
4. **Alembic for every schema change.** Create a new version file under `backend/app/alembic/versions/` for any model addition or column change.
5. **Pydantic schemas for every request/response.** Define `XBase`, `X` (table=True), `XPublic`, `XsPublic` pattern as in `db_models.py`.
6. **TypeScript strict mode on the frontend.** No `any` unless absolutely unavoidable.

---

## Planned Features (priority order)

### ✅ 1. Dynamic datasource registry (DONE)
**Goal:** Make the Explore page fully data-driven so adding a new ingest module automatically adds a tab.

**Built:**
- `backend/app/ingest/registry.py` — `DATASOURCE_REGISTRY` singleton; each ingest module registers itself at import time.
- `GET /api/v1/datasources/` endpoint returns `{ key, label, endpoint, columns, scope_params }` per source.
- `explore.tsx` fetches datasources from the API and renders one `<Tab>` per entry — zero frontend changes needed when a new source is added.

---

### ✅ 2. Ingestion scope UI (DONE)
**Goal:** Let users trigger ingestion for any combination of datasources and scope parameters, driven by the registry.

**Built:**
- Each datasource declares `scope_params` in the registry.
- `frontend/src/routes/ingest.tsx` — multi-select for sources, dynamic scope param form, live job polling.
- `POST /api/v1/ingest/run` + `GET /api/v1/ingest/status/{job_id}` — background job dispatch and polling.

---

### ✅ 3. Model persistence + saved-run gallery (DONE)
**Goal:** Trained models saved to disk and reloadable for inference without retraining.

**Built:**
- Models serialized to `artifacts/models/{run_id}.pkl` via `joblib`.
- `model_runs` DB table stores run metadata (Alembic migration `003_add_model_runs`).
- `GET /api/v1/models/` — lists all saved runs.
- `POST /api/v1/models/predict` — loads saved model and runs inference.
- "Saved Models" tab in `model.tsx` — lists runs and allows prediction without retraining.

---

### ✅ 4. LSTM / time-series model support (DONE)
**Goal:** Add an LSTM model type that treats each county as a time series.

**Built:**
- `model_type = "lstm"` branch in `training.py` — PyTorch LSTM, groups by county, sliding window sequences.
- Sequence length configurable via `TrainRequest`.
- Returns the same `TrainResult` schema as sklearn models.
- Frontend discovers it via `GET /api/v1/models/types` — no hardcoded changes needed.

---

### ✅ 5. Column-level stats and charting (DONE)
**Goal:** Clicking a numeric column in the Explore page shows a histogram.

**Built:**
- `explore.tsx` — clicking a `<Th>` cell opens a histogram modal (Recharts `<BarChart>`) using cached query data.

---

## Next Steps

- **Domain-agnostic training:** Refactor `TrainRequest` to describe datasources/join-keys/feature-columns generically (not hardcoded to `state`/`crop`/`year`). This unlocks the platform for non-agriculture domains.
- **Ingest progress streaming:** Replace polling with WebSocket or SSE for real-time ingest progress.
- **User-defined features:** Allow users to create computed columns in the Explore page (e.g. temperature × precipitation interaction).
- **Batch prediction:** Accept a CSV of feature rows and return predictions for all of them.
- **Authentication:** Add user accounts so researchers can have private model runs and datasets.

---

## How to add a new data source (step-by-step)

1. **Copy the template:** `cp backend/app/ingest/template_datasource.py backend/app/ingest/my_source.py`
2. **Fill in TODOs:** Set `DATASOURCE_NAME`, `DATASOURCE_DESCRIPTION`, `DATASOURCE_COLUMNS`, `SCOPE_PARAMS` (the filter dimensions your fetcher accepts), and implement `fetch_data(**scope) -> pd.DataFrame`.
3. **Add a SQLModel:** In `backend/app/db_models.py`, add `MySourceBase`, `MySource(table=True)`, `MySourcePublic`, `MySourcesPublic` following the existing pattern. Column names must match `DATASOURCE_COLUMNS`.
4. **Create an Alembic migration:** Inside the backend container run `alembic revision --autogenerate -m "add my_source table"`, then review the generated file.
5. **Register with the datasource registry:** At module import time, call `DATASOURCE_REGISTRY.register(DATASOURCE_NAME, module=<this module>, model=MySource, ...)`. The registry entry drives the Explore tab, the Ingest scope form, and the feature column picker in the Model page — all automatically.
6. **Add an API route:** Copy any existing route file (e.g. `yields.py`) to `my_source.py`, replace the SQLModel types and query filters, then add it to `backend/app/api/main.py` with `api_router.include_router(...)`.

The Explore page gains a new tab, the Ingest page gains the new source as a selectable option, and the Model page exposes the new columns as selectable features — all with **zero frontend changes**.

---

## How to add a new ML model type (step-by-step)

1. In `backend/app/api/routes/training.py`, extend the `MODEL_TYPES` Literal with the new type name and add a registration entry to the `MODEL_REGISTRY` dict: `{ "my_model": { "label": "My Model", "kind": "sklearn" | "pytorch" | "simulation" } }`.
2. In the `train` endpoint, add a new `elif model_type == "my_model":` branch. It must: accept an `(X_train, y_train)` numpy pair, fit, predict on `(X_test, y_test)`, compute `r2` and `rmse`, and return a `feature_importances` list. The rest of the pipeline (data join, split, serialisation) is handled by the platform and must not be re-implemented.
3. Register the type with `GET /api/v1/models/types` so the frontend `<Select>` discovers it automatically — never hardcode model names in React.

---

## Environment variables

**Platform-level (always required):**
| Variable | Purpose |
|---|---|
| `POSTGRES_USER` | DB username |
| `POSTGRES_PASSWORD` | DB password |
| `POSTGRES_DB` | DB name |
| `POSTGRES_SERVER` | DB hostname (default: `db` in compose) |

**Example domain — agriculture (only needed when using the bundled agriculture datasources):**
| Variable | Purpose |
|---|---|
| `NASS_API_KEY` | USDA NASS API key for crop yield ingestion |
| `INGEST_STATES` | Comma-separated US states to ingest (optional; defaults to a preset list) |
| `INGEST_START_YEAR` / `INGEST_END_YEAR` | Year bounds (default 1980–2022) |

New datasource modules should declare their own required env vars in their `DATASOURCE_DESCRIPTION` and read them via `app/core/config.py` (`Settings`).

---

## Running the project

```bash
# Start everything
docker compose up --build

# Apply migrations
docker compose exec backend alembic upgrade head

# List registered datasources
curl http://localhost:8000/api/v1/datasources/

# Trigger ingest for the bundled agriculture example domain
curl -X POST http://localhost:8000/api/v1/ingest/run \
  -H "Content-Type: application/json" \
  -d '{"sources": ["yields", "weather", "soil"], "scope": {"states": ["Iowa", "North Carolina"], "start_year": 1990, "end_year": 2022}}'

# Poll job status
curl http://localhost:8000/api/v1/ingest/status/<job_id>

# Frontend
open http://localhost:5173
```

---

## Conventions summary for AI agents

- **Never** access the DB directly from the frontend. All data goes through `/api/v1/`.
- **Always** define request/response schemas as Pydantic/SQLModel classes in `db_models.py` or inline in the route file.
- **Always** create an Alembic migration when changing a table definition.
- **Always** add the new router to `backend/app/api/main.py` with `api_router.include_router(...)`.
- **Always** use TanStack Query (`useQuery` / `useMutation`) for data fetching in React — never raw `fetch` or `useEffect` + `useState`.
- **Always** use Chakra UI components for layout and UI primitives — no raw HTML `<div>` grids.
- **Never** store secrets in code — use environment variables read via `app/core/config.py` (Pydantic `Settings`).
