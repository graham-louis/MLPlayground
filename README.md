# MLPlayground

**An extensible, researcher-friendly platform for agricultural machine learning.**

MLPlayground is a tool designed for climate researchers, agronomists, and data scientists to explore relationships between climate, soil, and crop yields. Its core philosophy is **simplicity and extensibility** — adding a new data source or model should not require a degree in software engineering.

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
# 1. Copy and configure the environment file
cp .env .env.local   # optional — defaults work for local Docker

# 2. Add your USDA NASS API key (required for yield ingestion)
#    Register for free at https://quickstats.nass.usda.gov/api
echo "NASS_API_KEY=your_key_here" >> .env

# 3. Start everything
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

The database starts empty. Ingest data via:

**From the UI:** Open the Data Explorer → click **Run Data Ingestion**.

**Via the API:**
```sh
curl -X POST http://localhost:8000/api/v1/ingest/trigger
# Poll status:
curl http://localhost:8000/api/v1/ingest/status
```

**Via Docker Compose:**
```sh
docker compose exec backend python -m app.ingest.runner
```

Ingestion fetches data from three public sources:

| Source | Data | API |
|---|---|---|
| USDA NASS QuickStats | Crop yields | `NASS_API_KEY` required |
| Daymet (NASA) | Daily weather → growing-season features | No key needed |
| SSURGO (USDA NRCS) | Soil properties | No key needed |

**Configurable via environment variables:**

| Variable | Default | Description |
|---|---|---|
| `NASS_API_KEY` | *(required)* | USDA NASS API key |
| `INGEST_STATES` | Built-in list of 10 states | Comma-separated state names to ingest |
| `INGEST_START_YEAR` | `1980` | First year to ingest |
| `INGEST_END_YEAR` | `2022` | Last year to ingest |
| `DRY_RUN` | *(unset)* | Set to `1` to log without writing to DB |

---

## Project Structure

```
MLPlayground/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── models.py            # SQLModel models: Yield, Weather, Soil
│   │   ├── backend_pre_start.py # DB readiness check (retry loop)
│   │   ├── core/
│   │   │   ├── config.py        # pydantic-settings Settings class
│   │   │   └── db.py            # Shared SQLAlchemy engine + get_session
│   │   ├── api/
│   │   │   ├── main.py          # API router aggregator
│   │   │   └── routes/          # yields, weather, soil, ingest, utils
│   │   ├── ingest/              # Ingestion pipeline
│   │   │   ├── runner.py        # Orchestrates full ingestion run
│   │   │   ├── crop_nass.py     # USDA NASS yield fetcher
│   │   │   ├── climate_nldas.py # Daymet weather fetcher
│   │   │   └── soil_ssurgo.py   # SSURGO soil fetcher
│   │   └── alembic/             # Database migrations
│   ├── scripts/
│   │   └── prestart.sh          # Runs DB readiness check + alembic upgrade head
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── routeTree.gen.ts
│   │   └── routes/
│   │       ├── __root.tsx       # Root layout + nav bar
│   │       ├── index.tsx        # Home / dashboard
│   │       ├── explore.tsx      # Data Explorer
│   │       └── model.tsx        # Model Training (placeholder)
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── vite.config.ts
├── compose.yml
└── .env
```

---

## API Reference

All endpoints are prefixed with `/api/v1`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/yields/` | Query crop yields (params: `state`, `crop`, `start_year`, `end_year`) |
| `GET` | `/yields/crops` | Distinct crop names, optionally filtered by `state` |
| `GET` | `/yields/states` | Distinct state names |
| `GET` | `/weather/` | Query weather records (params: `state`, `county`, `year`) |
| `GET` | `/soil/` | Query soil records (params: `state`, `county`) |
| `POST` | `/ingest/trigger` | Start background ingestion (returns 409 if already running) |
| `GET` | `/ingest/status` | `{"status": "idle"\|"running"}` |
| `GET` | `/utils/health-check/` | Health check |

Interactive documentation: **http://localhost:8000/docs**

---

## Adding a New Data Source

1. Add a new Python module in `backend/app/ingest/` (e.g., `satellite_modis.py`) that returns a `pd.DataFrame`.
2. Add a corresponding SQLModel table to `backend/app/models.py`.
3. Generate and apply a migration:
   ```sh
   docker compose exec backend alembic revision --autogenerate -m "Add satellite table"
   docker compose exec backend alembic upgrade head
   ```
4. Add a route in `backend/app/api/routes/` and register it in `backend/app/api/main.py`.
5. Call your new fetcher from `backend/app/ingest/runner.py`.

---

## Project Goals

1. **Researcher-Centric** — built for domain experts, not software engineers.
2. **Plug-and-Play** — adding a new dataset is as simple as dropping a single script into `ingest/`.
3. **Transparent** — every step from data fetching to model prediction is inspectable.
