Plugins — Datasources & Nodes
=============================

Overview
--------
Two plugin types are auto-discovered at backend startup: datasources and nodes. Files must follow naming patterns so the import-time globs pick them up.

Datasources
-----------
- Location: `backend/app/ingest/`
- Filename pattern: `ds_<name>.py`
- Base class: `BaseDatasource` (see `backend/app/ingest/base.py`)
- Required class attributes:
  - `key: str` — unique id used by the API and table naming
  - `label: str`
  - `description: str`
  - `columns: list[Column]` — schema description
  - `scope_params: list[dict]` — parameters for fetching (e.g., states, years)
- Required method: `def fetch(self, **kwargs) -> Optional[pd.DataFrame]`
- Helpers available: `_get_table()` (lazily creates a SQLAlchemy Core table), `upsert(df)` and `query(...)`.
- Registration: `BaseDatasource.__init_subclass__` registers the class in `DATASOURCE_REGISTRY` automatically.

Nodes
-----
- Location: `backend/app/nodes/`
- Filename pattern: `node_<name>.py`
- Base class: `BaseNode` (see `backend/app/nodes/base.py`)
- Required class attributes:
  - `node_id: str` — unique identifier
  - `display_name: str`
  - `description: str`
  - `category: str`
  - `inputs: list[IOSlot]` and `outputs: list[IOSlot]`
  - `params: pydantic.BaseModel` — schema used to render node form in UI
- Required method: `def run(self, inputs: dict, params: BaseModel) -> dict`
- Registration: `BaseNode.__init_subclass__` instantiates and registers the node with `NODE_REGISTRY` (endpoint mapping created automatically).

Examples
--------
- See `backend/app/ingest/ds_yields.py` and `backend/app/nodes/node_modeling.py` for real examples.

Checklist to add a plugin
-------------------------
1. Create file `ds_<your>.py` or `node_<your>.py` in the appropriate folder.
2. Implement required attributes and `fetch` / `run` methods.
3. Start the backend and check that the plugin appears (API: `GET /api/v1/graphs/nodes` or `GET /api/v1/datasources`).
4. If missing, check import-time exceptions in startup logs (auto-discovery logs in `backend/app/api/main.py`).
