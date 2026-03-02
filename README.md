# MLPlayground

**An extensible, researcher-friendly platform for tabular machine learning.**

MLPlayground is a digital data warehouse and modelling hub for tabular datasets. It ships with a working agriculture example domain (US crop yields, weather, soil) but is domain-agnostic — any tabular dataset can be plugged in by creating a single file.


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
| `ARTIFACTS_BASE` | `artifacts/` | Where trained model `.pkl` files and explainability outputs are saved (env var used by backend) |

---

## Project Structure

```
MLPlayground/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── db_models.py         # SQLModel definitions — ModelRun only
│   │   │                        # (domain tables are plugin-managed, not here)
│   │   ├── core/
│   │   │   ├── config.py        # Pydantic Settings (env vars)
│   │   │   └── db.py            # Engine + get_session dependency
│   │   ├── api/
│   │   │   ├── main.py          # Router aggregator + plugin auto-discovery
│   │   │   └── routes/
│   │   │       ├── data.py          # GET /api/v1/data/{key}  (generic, all sources)
│   │   │       │                    # GET /api/v1/data/{key}/distinct/{column}
│   │   │       ├── datasources.py   # GET /api/v1/datasources/
│   │   │       ├── ingest.py        # POST /api/v1/ingest/run
│   │   │       ├── training.py      # POST /api/v1/models/train  /predict  GET /
│   │   │       └── utils.py         # Health check
│   │   ├── ingest/
│   │   │   ├── base.py              # BaseDatasource ABC + auto-registration framework
│   │   │   ├── registry.py          # DATASOURCE_REGISTRY singleton
│   │   │   ├── runner.py            # Bulk ingest CLI (iterates all plugins)
│   │   │   ├── template_datasource.py  # Copy-paste template — start here
│   │   │   ├── _daymet_helpers.py   # Private: shared Daymet/SSURGO helpers
│   │   │   ├── ds_yields.py         # USDA NASS crop yields plugin
│   │   │   ├── ds_weather.py        # Daymet annual weather plugin
│   │   │   ├── ds_daily_weather.py  # Daymet daily weather plugin
│   │   │   ├── ds_soil.py           # SSURGO soil properties plugin
│   │   │   └── ds_weather_psa.py    # PSA daily weather plugin (example)
│   │   └── alembic/versions/        # DB migrations (001 → 004)
│   │                                # 004 drops domain tables (now plugin-managed)
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

## Plugin systems

Two plugin types are auto-discovered at backend startup:

- Datasources: add a single file named `ds_<name>.py` under `backend/app/ingest/` that subclasses `BaseDatasource` (see `backend/app/ingest/template_datasource.py`). The framework creates backing tables on first use and registers the source for the UI automatically.
- Nodes: add a file named `node_<name>.py` under `backend/app/nodes/` that subclasses `BaseNode`. Node Pydantic schemas are used to render parameter forms in the graph UI.

## API Reference

All endpoints are prefixed with `/api/v1`.

**Platform routes:**

| Method | Path | Description |
|---|---|---|
| `GET` | `/datasources/` | List all registered datasources with metadata |
| `GET` | `/data/{key}` | Query any registered datasource (state, county, year, skip, limit) |
| `GET` | `/data/{key}/distinct/{column}` | Distinct values for a column (used for dropdowns) |
| `POST` | `/models/train` | Train a model (linear, random forest, gradient boosting, LSTM, AutoML) |
| `POST` | `/models/predict` | Run prediction with a saved model |
| `GET` | `/models/` | List all saved model runs |
| `GET` | `/models/types` | List available model types |
| `POST` | `/ingest/run` | Trigger background ingestion job |
| `GET` | `/ingest/status/{job_id}` | Poll ingestion job status |
| `GET` | `/utils/health-check/` | Liveness probe |

Interactive documentation: **http://localhost:8000/docs**

---

## Adding a New Data Source

Adding a new data source requires **exactly one file**. No database migrations, no route files, no registry edits.

```sh
cp backend/app/ingest/template_datasource.py backend/app/ingest/ds_my_source.py
```

Open `ds_my_source.py` and fill in the four `# TODO` sections:

1. **Identity** — set `key`, `label`, `description` on the class
2. **Schema** — list your `Column("name", type)` entries
3. **Scope params** — adjust the ingest form defaults (optional)
4. **`fetch()` method** — call your API, return a DataFrame

That's it. The framework automatically:
- Creates the backing database table on first use (no Alembic needed)
- Registers the source in the UI (Explore tab + Ingest selector)
- Exposes `GET /api/v1/data/<key>` and `GET /api/v1/data/<key>/distinct/<column>`
- Wires up the ingest pipeline so the source can be ingested via `/ingest/run`

See `backend/app/ingest/ds_weather_psa.py` for a complete real-world example.

---

## Adding a New ML Model Type

1. Add an entry to `MODEL_REGISTRY` and extend `MODEL_TYPES` in `backend/app/api/routes/training.py`.
2. Add an `elif model_type == "my_model":` branch in the `train` endpoint that accepts `(X_train, y_train)`, fits, evaluates, and returns `feature_importances`.
3. The model type dropdown discovers types from `/api/v1/models/types` automatically.

---

## Project Goals

1. **Domain-agnostic** — the platform works identically for any tabular dataset.
2. **Data-driven UI** — the frontend reflects the datasource registry with zero manual wiring.
3. **Transparent** — every step from data fetching to model prediction is inspectable.
4. **Minimal friction** — adding a new source requires one file; adding a new model type requires one dict entry and one code branch.
