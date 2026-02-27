

Summary plan — node-based workflow editor for data preparation & modeling (ComfyUI-inspired)

### Overview

- Visual graph editor where nodes represent data sources, transforms, feature engineering, training, evaluation, and export.
- Backend executes subgraphs, caches intermediate artifacts, stores models/metrics under artifacts/, and exposes APIs for the frontend to run graphs and fetch artifacts.


### Key components

Frontend: React + TypeScript app (use existing frontend). UI: node canvas (react-flow), inspector, property editor, logs/preview pane, artifacts browser.
Backend: Python FastAPI service (in repo backend/). Execution engine runs nodes, returns outputs, exposes run/poll/result endpoints.
Executor: graph builder + execution engine supporting partial execution, caching, and idempotent node runs.
Storage: artifacts/ for model/artifact files; metadata in DB via SQLAlchemy (db/models.py). Use existing Alembic migrations.
Worker/Queue: lightweight job runner (RQ/Celery/Prefect) for long runs; sync path for quick steps.

### Node model & schema

Each node implements a schema:
- id, display_name, category, inputs (type + optional), outputs (type), params (typed)
- run(inputs, params) -> outputs (serializable; can reference artifact file paths)
- Built-in types: DataFrame, Table, Array, Numeric, Model, Metric, Artifact (file path), Plot/Image.
- Provide Python base class for nodes and registration API (like ComfyUI ComfyNode).
- Allow custom node packages (plugin dirs) loaded at startup.


### Graph execution semantics

Directed acyclic graph (DAG). Execution engine:
Topologically sorts and runs required nodes.
Supports partial runs: run only downstream of changed nodes.
Cache node outputs keyed by node config + upstream outputs hash.
Return operation id + polling endpoint for async runs.
Provide preview nodes (like PreviewImage) for inspecting intermediate DataFrames or plots.
Support streaming logs and result streaming for UIs.


### Node categories (initial)

Sources: CSV, Parquet, Database (use db_access helpers), API.
Transforms: Filter, Join, GroupBy, Impute, Encode, Scale, Custom Python UDF.
Feature engineering: FeatureUnion, PCA, TimeFeature, Windowing.
Modeling: Trainer (sklearn/PyCaret/PyTorch), HyperparameterSearch, SaveModel.
Evaluation: Metrics node, CrossVal, PlotROC, SHAP explainer (save SHAP artifacts).
Utilities: Split, Cache, SaveArtifact, LoadArtifact, Preview.


### APIs (minimal)

POST /graphs/validate -> validate graph JSON
POST /graphs/run -> enqueue run, returns run_id
GET /graphs/{run_id}/status -> status + logs
GET /graphs/{run_id}/result -> outputs metadata and artifact URLs
GET /artifacts/{path} -> download artifact
GET /nodes -> list available node types and schemas


### Frontend UX flow

Drag & drop nodes from palette, wire outputs -> inputs.
Node inspector to edit params.
Run button: run entire graph or selection; show run status/toasts.
Artifacts pane to download models/plots; preview DataFrame/plots inline.
Tests/examples: include template workflows (seeded JSON) in repository.



### Persistence & conventions (align with repo)

Store canonical UI data keys (if Streamlit used elsewhere follow .github rules). Here: use artifacts/, db/models.py for run metadata.
Use src/utils/db_access.py pattern if retrieving backend data. Expose helper fetchers for frontend tests to mock.
Save models and explainability artifacts to artifacts/shap/, artifacts/lime/ as per instructions.


### Tech stack & libs

Frontend: react, typescript, react-flow, Zustand or Redux, Vite (existing), React Testing Library/Jest (tests present).
Backend: FastAPI, Pydantic node schemas, SQLAlchemy, Alembic (migrations), RQ/Celery for async worker, uvicorn.
Execution: pure-Python node registry + GraphBuilder-style utility (inspiration: comfy_execution.GraphBuilder).
Container: docker-compose (use existing dev-compose commands).


### Security & operational

Sandbox user-provided Python UDFs (limit resources) — run in worker container/process.
Artifact retention policy and storage quotas.
Auth for artifact/graph endpoints (API keys/session).



### MVP roadmap (4 sprints)

Sprint 0 (design, infra): node schema, registry, GraphBuilder prototype; expose GET /nodes.
Sprint 1 (core execution): implement sources, basic transforms (filter/join/split), simple trainer node (sklearn), run API + sync execution.
Sprint 2 (frontend): canvas with react-flow, palette, node inspector, run flow integration, preview node.
Sprint 3 (async, caching, artifacts): worker queue, partial execution & caching, artifact browser, SHAP node, add tests & docs.


### Testing & examples

Add unit tests for node execution and GraphBuilder (like ComfyUI tests).
Provide example workflows in repo frontend/test/ or dedicated templates folder.
Next steps (pick one)

I can scaffold: (1) Python Node base + GraphBuilder; or (2) React palette + simple node renderer using react-flow. Which to generate first?