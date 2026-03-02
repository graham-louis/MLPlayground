MLPlayground — Architecture Overview
=================================

Summary
-------
MLPlayground is a visual ML pipeline builder. The frontend is a React/TypeScript app using an XYFlow graph canvas; the backend is a FastAPI service exposing graph execution, datasources, ingestion, and model training endpoints. Data and artifacts (models, SHAP/LIME outputs) live in the `artifacts/` directory.

Frontend
--------
- Location: `frontend/src/`
- Frameworks: React + Vite + TypeScript
- Routing: `@tanstack/react-router` (route files in `frontend/src/routes/` and generated `routeTree.gen.ts`)
- Graph canvas: `@xyflow/react` (templates in `frontend/src/templates/`)
- State + data: `zustand` + `@tanstack/react-query` + `axios`

Backend
-------
- Location: `backend/app/`
- Server: FastAPI (`backend/app/main.py`) mounting `api_router` at `/api/v1` (see `backend/app/api/main.py`).
- Routes: defined under `backend/app/api/routes/` (examples: `graphs.py`, `datasources.py`, `data.py`, `ingest.py`, `training.py`, `utils.py`).
- Settings: `backend/app/core/config.py` (Pydantic `Settings`, reads `.env`).
- DB: `sqlmodel` (SQLAlchemy) with session generator in `backend/app/core/db.py`.
- Migrations: Alembic under `backend/app/alembic/versions/`.

Plugin systems
--------------
- Datasources: subclass `BaseDatasource` in `backend/app/ingest/base.py`; file name pattern `ds_<name>.py` in `backend/app/ingest/` — auto-registered via `__init_subclass__`.
- Nodes: subclass `BaseNode` in `backend/app/nodes/base.py`; file name pattern `node_<name>.py` in `backend/app/nodes/` — also auto-registered. Node schemas (Pydantic) are used to render node parameter UIs.

Artifacts & Data
----------------
- Artifacts and model outputs: `backend/artifacts/` (path configurable via `ARTIFACTS_BASE` in settings).
- Example data: `data/sample.csv` and `backend/app/artifacts/` for training outputs.

Where to look first
-------------------
- `backend/app/api/main.py` — router registration and plugin auto-discovery.
- `backend/app/ingest/base.py` — datasource interface.
- `backend/app/nodes/base.py` — node interface and example nodes in `backend/app/nodes/`.
- `frontend/src/templates/` — graph templates to copy when adding starter graphs.