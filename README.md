# MLPlayground

**An extensible, researcher-friendly platform for tabular machine learning.**

MLPlayground is a digital data warehouse and modelling hub for tabular datasets. It ships with a working agriculture example domain (US crop yields, weather, soil) but is **fully domain-agnostic** — any tabular dataset can be plugged in with minimal code. Adding a new data source or ML model should not require touching the frontend.

Built on the [tiangolo full-stack FastAPI template](https://github.com/tiangolo/full-stack-fastapi-template).

---

## Architecture

| Layer | Technology |
|---|---|
| Backend | FastAPI + SQLModel + Alembic (PostgreSQL) |
| Frontend | React + Vite + TypeScript + Chakra UI + TanStack Router/Query |
| Infrastructure | Docker Compose |

---

## Quick Start

```sh
# 1. Add your USDA NASS API key (required for yield ingestion)
#    Register for free at https://quickstats.nass.usda.gov/api
echo "NASS_API_KEY=your_key_here" >> .env

# 2. Start everything
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost |
| Backend API | http://localhost:8000/api/v1 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Adminer (DB UI) | http://localhost:8080 |

---

## Local Development (without Docker)

```sh
# Backend
cd backend
pip install -e .
fastapi dev app/main.py

# Frontend (separate terminal)
cd frontend
npm install
npm run dev   # http://localhost:5173
```

---

## Data Ingestion

The database starts empty. Ingest data from the UI or via the API:

**From the UI:** Navigate to **Ingest** → select data sources and scope → click **Run Ingestion**.

**Via the API:**
```sh
# Trigger ingestion for selected sources and scope
curl -X POST http://localhost:8000/api/v1/ingest/run \
  -H "Content-Type: application/json" \
  -d '{"sources": ["yields", "weather", "soil"], "scope": {"states": ["Iowa", "North Carolina"], "start_year": 1990, "end_year": 2022}}'

# Poll job status
curl http://localhost:8000/api/v1/ingest/status/<job_id>
```

The bundled agriculture example ingests from three public sources:

| Source | Data | Key Required |
|---|---|---|
| USDA NASS QuickStats | Crop yields | Yes — `NASS_API_KEY` |
| Daymet (NASA) | Annual + daily weather | No |
| SSURGO (USDA NRCS) | Soil properties | No |

**Key environment variables:**

| Variable | Default | Description |
|---|---|---|
| `NASS_API_KEY` | *(required for yields)* | USDA NASS API key |
| `INGEST_STATES` | Preset list | Comma-separated US states to ingest |
| `INGEST_START_YEAR` | `1980` | First year to ingest |
| `INGEST_END_YEAR` | `2022` | Last year to ingest |
| `ARTIFACTS_DIR` | `artifacts/` | Where trained model `.pkl` files are saved |

---

## Project Structure

```
MLPlayground/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── db_models.py         # SQLModel table definitions (DB schema)
│   │   ├── core/
│   │   │   ├── config.py        # Pydantic Settings (env vars)
│   │   │   └── db.py            # Engine + get_session dependency
│   │   ├── api/
│   │   │   ├── main.py          # Router aggregator
│   │   │   └── routes/
│   │   │       ├── datasources.py   # GET /api/v1/datasources/
│   │   │       ├── ingest.py        # POST /api/v1/ingest/run
│   │   │       ├── training.py      # POST /api/v1/models/train  /predict  GET /
│   │   │       ├── yields.py        # Example domain: crop yields
│   │   │       ├── weather.py       # Example domain: annual weather
│   │   │       ├── daily_weather.py # Example domain: daily weather
│   │   │       ├── soil.py          # Example domain: soil
│   │   │       └── utils.py         # Health check
│   │   ├── ingest/
│   │   │   ├── runner.py            # Orchestrates bulk ingest
│   │   │   ├── registry.py          # DATASOURCE_REGISTRY singleton
│   │   │   ├── template_datasource.py  # Copy-paste template for new sources
│   │   │   ├── yields_nass.py       # USDA NASS yield fetcher
│   │   │   ├── weather_daymet.py    # Daymet annual weather fetcher
│   │   │   ├── daily_weather_utils.py # Daily weather DB persistence helpers
│   │   │   └── soil_ssurgo.py       # SSURGO soil fetcher
│   │   └── alembic/versions/        # DB migrations (001 → 003)
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   └── src/routes/
│       ├── __root.tsx     # Root layout + nav bar
│       ├── index.tsx      # Home / dashboard
│       ├── explore.tsx    # Data Explorer (tabs driven by /api/v1/datasources/)
│       ├── model.tsx      # Model Training + Prediction + Saved Models
│       └── ingest.tsx     # Ingest scope UI (sources + params driven by registry)
├── artifacts/models/      # Serialized .pkl model artifacts
├── docs/                  # Architecture diagrams (Mermaid)
├── compose.yml
└── .env
```

---

## API Reference

All endpoints are prefixed with `/api/v1`.

**Platform routes:**

| Method | Path | Description |
|---|---|---|
| `GET` | `/datasources/` | List all registered datasources with metadata |
| `POST` | `/models/train` | Train a model (linear, random forest, gradient boosting, LSTM) |
| `POST` | `/models/predict` | Run prediction with a saved model |
| `GET` | `/models/` | List all saved model runs |
| `GET` | `/models/types` | List available model types |
| `POST` | `/ingest/run` | Trigger background ingestion job |
| `GET` | `/ingest/status/{job_id}` | Poll ingestion job status |
| `GET` | `/utils/health-check/` | Liveness probe |

**Example domain routes:**

| Method | Path | Description |
|---|---|---|
| `GET` | `/yields/` | Crop yields (params: `state`, `crop`, `start_year`, `end_year`) |
| `GET` | `/weather/` | Annual weather (params: `state`, `county`, `year`) |
| `GET` | `/daily-weather/` | Daily weather (params: `state`, `county`, `start_date`, `end_date`) |
| `GET` | `/soil/` | Soil properties (params: `state`, `county`) |

Interactive documentation: **http://localhost:8000/docs**

---

## Adding a New Data Source

1. Copy the template: `cp backend/app/ingest/template_datasource.py backend/app/ingest/my_source.py`
2. Fill in `DATASOURCE_NAME`, `DATASOURCE_COLUMNS`, `SCOPE_PARAMS`, and implement `fetch_data(**scope) -> pd.DataFrame`.
3. Add a SQLModel table to `backend/app/db_models.py` (column names must match `DATASOURCE_COLUMNS`).
4. Create an Alembic migration: `docker compose exec backend alembic revision --autogenerate -m "add my_source"`.
5. Register with the registry by calling `DATASOURCE_REGISTRY.register(...)` at module import time.
6. Add an API route in `backend/app/api/routes/` and register it in `backend/app/api/main.py`.

The Explore page gains a new tab and the Ingest page gains the new source as a selectable option — **no frontend changes required**.

---

## Adding a New ML Model Type

1. Extend `MODEL_TYPES` Literal and add an entry to `MODEL_REGISTRY` in `backend/app/api/routes/training.py`.
2. Add an `elif model_type == "my_model":` branch in the `train` endpoint that accepts `(X_train, y_train)`, fits, evaluates on `(X_test, y_test)`, and returns `feature_importances`.
3. The model type dropdown in the frontend discovers types from `/api/v1/models/types` automatically.

---

## Project Goals

1. **Domain-agnostic** — the platform works identically for any tabular dataset.
2. **Data-driven UI** — the frontend reflects the datasource registry with zero manual wiring.
3. **Transparent** — every step from data fetching to model prediction is inspectable.
4. **Minimal friction** — adding a new source or model touches the fewest files possible.
