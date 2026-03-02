API Reference — Key Routers & Endpoints
======================================

Router files live under `backend/app/api/routes/`. Each file declares an `APIRouter` with a `prefix` and `tags` and is included by `backend/app/api/main.py` under the `/api/v1` prefix.

Primary routers and highlights
-----------------------------
- `backend/app/api/routes/data.py` — prefix `/data` — endpoints: `GET /{key}` (fetch tabular datasource), `GET /{key}/distinct/{column}`
- `backend/app/api/routes/datasources.py` — prefix `/datasources` — `GET /` lists registered datasources
- `backend/app/api/routes/graphs.py` — prefix `/graphs` — endpoints: `GET /nodes`, `GET /datasource-keys`, `GET /datasource-info/{key}`, `POST /upload`, workflow CRUD, `POST /validate`, `POST /run`, `GET /{run_id}/status`, `GET /{run_id}/result`, `GET /artifacts/{path}`, `POST /export/python`
- `backend/app/api/routes/ingest.py` — prefix `/ingest` — `POST /run`, `GET /status/{id}`
- `backend/app/api/routes/training.py` — prefix `/models` — training and model endpoints
- `backend/app/api/routes/utils.py` — prefix `/utils` — `GET /health-check/`

How to add a new router
------------------------
1. Create `backend/app/api/routes/<name>.py` with `router = APIRouter(prefix="/<name>", tags=["<name>"])`.
2. Define endpoints on `router`.
3. Add `api_router.include_router(<name>.router)` to `backend/app/api/main.py`.
4. Restart backend and verify `http://localhost:8000/docs` shows new endpoints.

Settings referenced by API
--------------------------
- Settings object: `backend/app/core/config.py` (`settings.API_V1_STR` controls `/api/v1` prefix, `ARTIFACTS_BASE` controls artifact path, Postgres settings affect DB connectivity).
