# MLPlayground

A Streamlit-based AutoML playground for data ingestion, profiling, and quick model comparison using PyCaret.

## Features
- Upload and profile datasets
- Compare machine learning models (classification/regression)
- Integrate external data (USDA NASS, SSURGO, weather)
- Persist and share data and models
- Scalable architecture with database-backed storage

## Quick Start

### Local (with Docker Compose)
```sh
docker-compose up --build
```
Visit [http://localhost:8501](http://localhost:8501) in your browser.

### Database Migrations
After first startup, run migrations inside the app container:
```sh
docker-compose exec app alembic upgrade head
```

## Project Structure

```
MLPlayground/
├── db/
│   ├── models.py
│   ├── init_db.py
│   ├── migrate.py
│   └── migrations/
│       ├── env.py
│       ├── script.py.mako
│       └── versions/
├── src/
│   ├── AutoML.py
│   ├── pages/
│   └── utils/
├── requirements.txt
├── Dockerfile
├── compose.yaml
└── ...
```

## Database Directory (`db/`)

The `db/` directory contains all code and configuration for database integration and migrations:

- **`models.py`**: SQLAlchemy ORM models for all tables (e.g., `Yield`, `Weather`, `Soil`).
  ```python
  from sqlalchemy import Column, Integer, String, Float
  from sqlalchemy.ext.declarative import declarative_base
  Base = declarative_base()

  class Yield(Base):
      __tablename__ = 'yields'
      id = Column(Integer, primary_key=True)
      county = Column(String)
      # ... other columns ...
  ```
- **`init_db.py`**: Script to create all tables directly from models (for dev/testing).
  ```python
  from db.models import Base
  from sqlalchemy import create_engine
  engine = create_engine("sqlite:///mlplayground.db")
  Base.metadata.create_all(engine)
  ```
- **`migrate.py`**: Script to run Alembic migrations programmatically.
  ```python
  from alembic import command, config
  alembic_cfg = config.Config("alembic.ini")
  command.upgrade(alembic_cfg, 'head')
  ```
- **`migrations/`**: Alembic migration environment.
  - `env.py`: Migration config, loads models and sets up DB connection.
  - `script.py.mako`: Template for new migration scripts.
  - `versions/`: Auto-generated migration scripts (one per schema change).

## Example: Adding a New Table
1. Edit `db/models.py` to add a new model.
2. Run inside the app container:
   ```sh
   alembic revision --autogenerate -m "Add new table"
   alembic upgrade head
   ```

## Troubleshooting
- If tables are missing, ensure migrations are generated and applied.
- To reset the database, remove the Docker volume:
  ```sh
  docker-compose down
  docker volume rm mlplayground_pgdata
  docker-compose up --build
  ```

---

For more details, see the code comments in each file or ask for help!

## FastAPI backend integration

This project uses a small FastAPI service to provide a modular, testable, and network-accessible data layer for the Streamlit app. The FastAPI backend sits between the Streamlit UI and the database and exposes lightweight JSON endpoints for the main domain objects (`yields`, `weather`, `soil`).

Why FastAPI?
- Separation of concerns: moves DB access and heavier data processing out of the Streamlit process so the UI stays responsive.
- Reusability: the API can be used by other services or scripts (not only Streamlit).
- Testability: endpoints are easier to test and mock in CI compared to direct DB access inside the UI process.
- Performance: enables scaling the backend independently and caching at the HTTP layer (or via reverse proxies).

Available endpoints
- `GET /yields/` — query yields with params like `state`, `crop`, `year` and returns a JSON list of records.
- `GET /weather/` — query weather with params like `state`, `county`, `year` and returns JSON.
- `GET /soil/` — query soil with params like `state`, `county`, `district` and returns JSON.

How Streamlit uses the API
- The Streamlit pages call the FastAPI endpoints via `src/utils/db_access.py` which wraps HTTP calls and converts responses into `pandas.DataFrame` objects. Query parameters are passed from the UI controls (state, crop, year etc.).
- The fetched DataFrames are placed into `st.session_state['df']` for downstream pages (profiling and modeling) to consume.

Diagnostics and troubleshooting
- If an endpoint returns 404 it usually means the router wasn't registered or the running service is out-of-sync with the source code. Check the API container logs for import-time exceptions.
- A lightweight `/openapi.json` is available from FastAPI; it lists registered paths and is useful to confirm which routes the running server exposes.
- To seed sample data for development use the Streamlit `0_DBTest` page or run `db/init_db.py` (dev-only) to create tables and insert test rows.

Running the API (development)
1. With Docker Compose (recommended dev flow): the API runs as part of `docker-compose up --build` and is available at the hostname `api` in the compose network. Streamlit in the same compose stack communicates with it at `http://api:8000`.
2. Locally without Docker: from the repo root, install requirements and run Uvicorn inside the `backend` package:

```bash
# from repo root
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Notes
- The backend is intentionally small — it provides thin, well-documented endpoints and delegates heavy lifting (ETL, aggregation) to dedicated utilities or background jobs in future iterations.
- When adding new endpoints, follow the router pattern in `backend/` and update `src/utils/db_access.py` and the Streamlit pages to consume the new endpoints.

Project abstract & goals
-------------------------
Climate variability presents a significant challenge to agricultural planning, and existing predictive models are often static, opaque, and require specialized expertise. To address this, MLPlayground provides an interactive AutoML web portal for on-demand, localized crop yield forecasting with a core focus on machine-learning explainability.

Key goals:
- Simple, interactive forecasting: users select a crop and a geographical region to trigger an automated pipeline that trains a custom model in real-time.
- Integrated data sources: historical yield data (USDA NASS) is combined with climate data (NASA NLDAS) and soil data (SSURGO) to produce a richer feature set.
- Automated agronomic features: the pipeline automatically engineers features such as Growing Degree Days (GDD) and seasonal aggregates to improve predictive signal.
- Regional models and evaluation: the portal supports building region-specific models (for example, Piedmont vs Coastal Plains in NC) to capture local climate-crop relationships.
- Explainability first: every prediction is accompanied by model-agnostic explanations using SHAP and LIME so users can understand the climatic drivers behind forecasts.

Intended audience
- Agronomists and extension agents who want quick, transparent forecasts for decision support.
- Data scientists exploring domain-specific feature engineering and model explainability in agriculture.
- Developers interested in building production-ready AutoML pipelines with clear separation between UI, API, and data layers.

If you'd like, I can add a separate `docs/DATA_FLOW.md` that diagrams the end-to-end pipeline (data sources → ETL → API → Streamlit → Model + Explanations) and include sample commands to reproduce the Piedmont vs Coastal Plains analysis used in our experiments.
