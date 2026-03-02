Project Conventions & Notes
===========================

- Router registration: all routers under `backend/app/api/routes/` are included by `backend/app/api/main.py`.
- Plugin auto-discovery: `backend/app/api/main.py` imports any `ds_*.py` in `backend/app/ingest/` and `node_*.py` in `backend/app/nodes/` at startup; naming matters.
- Dynamic datasource tables: datasources use `_get_table()` to create tables at runtime (these are not managed by Alembic).
- Migrations: add schema migrations under `backend/app/alembic/versions/` and run via `alembic upgrade head` (container prestart script handles this in Docker flows).
- Frontend route generation: after adding routes, run `npm run build` to regenerate `routeTree.gen.ts` when necessary.
- Artifacts: saved to `ARTIFACTS_BASE` (default `/app/artifacts`); backend serves artifacts via `GET /api/v1/graphs/artifacts/{path}`.

Testing conventions
-------------------
- Backend tests live in `backend/tests/` — run with `pytest`.
- Frontend tests use `vitest` (see `frontend/package.json` scripts).

When to ask maintainers
-----------------------
- Before changing `ARTIFACTS_BASE`, public API route prefixes, or persistent database schemas.
