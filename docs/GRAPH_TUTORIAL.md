# Building a Node-Based ML Workflow Engine in Python

A guided tutorial for implementing the graph execution system described in `GRAPH_PLAN.md`.

---

## Who This Is For

This tutorial is for developers who already know Python basics and want to learn how production-quality backend systems are designed. Rather than handing you finished code, it walks through *why* each decision is made — the trade-offs, the patterns, and the pitfalls. By the end you will have built a ComfyUI-inspired workflow engine on top of the MLPlayground FastAPI service.

---

## Part 0 — Orientation: Know the Terrain Before You Build

Before writing a single line of new code, read the existing codebase. This is non-negotiable in professional engineering. Time spent understanding what exists saves hours of duplicated work and mismatched abstractions.

### The directory you care about most

Open `backend/app/` in your editor. You will see four sub-packages that matter here:

- **`nodes/`** — Contains `base.py` (the abstract node class), `registry.py` (a stub with only a docstring), and `toy_node.py` (a working example). This is your main construction site.
- **`api/routes/`** — The FastAPI route handlers. `graphs.py` exists but is currently empty. You will fill it in.
- **`ingest/`** — A fully working plugin system that loads data sources. This is your *design template*. Study it carefully.
- **`core/`** — Database config, connection factory. You will need this for the `GraphRun` persistence layer.

### Read `ingest/base.py` and `ingest/registry.py` first

These two files together demonstrate every pattern you are about to implement for nodes:

- A **registry** object that holds a keyed dictionary of registered items.
- A **base class** that calls into the registry automatically via Python's `__init_subclass__` hook.
- A **generic query layer** that routes API calls to whatever concrete subclass is registered.

When you build `nodes/registry.py` and strengthen `nodes/base.py`, you are doing the same thing. Understanding the existing solution first means you will make consistent, idiomatic choices.

### Read `api/routes/training.py` next

This is the most complex route file in the project. Notice:

- Pydantic `BaseModel` subclasses define the *shape* of requests and responses — not plain dicts.
- Model artifacts are saved to disk with `joblib`, and their metadata goes into the database. This is the artifact persistence pattern you will reuse.
- The `_load_joined_data` helper is a private function (prefixed with `_`) that is not an endpoint itself — it is shared logic extracted to avoid duplication. You will write helpers like this inside the execution engine.

### Map GRAPH_PLAN.md to files

| GRAPH_PLAN.md concept | Where it lives (or will live) |
|---|---|
| Node schema (id, inputs, outputs, params) | `nodes/base.py` — needs strengthening |
| Node registry + `GET /nodes` | `nodes/registry.py` — needs implementation |
| Graph execution engine + caching | `nodes/` — new file: `executor.py` |
| API endpoints (run/status/result) | `api/routes/graphs.py` — currently empty |
| GraphRun persistence | `db_models.py` — add `GraphRun` model + migration |
| Async worker queue | New: `workers/` directory |
| Artifact files | `artifacts/` — already exists on disk |

Now you have a map. Start building.

---

## Part 1 — Sprint 0: The Node Foundation

The goal of Sprint 0 is narrow but critical: define what a "node" *is*, register all known nodes at startup, and expose that registry through the API. No execution yet — just the vocabulary.

### Why start with the schema?

In software, a schema is a contract. If you start writing execution logic before deciding what a node's inputs and outputs look like, you will have to rewrite everything when the schema changes. Define it first, lock it down, then build everything else on top.

### Strengthening `BaseNode`

Open `nodes/base.py`. The current `BaseNode` class is a good start, but it has a problem: `inputs`, `outputs`, and `params` are typed as `list[IOTypes]`, which means the node declares only the *types* of its slots — not their names. A node with two `NUMERIC` inputs is ambiguous: which argument is which?

**Design decision:** Change each slot from a bare type to a small descriptor object that pairs a name with a type. Something like:

```python
# Illustrative — do not paste as-is
class IOSlot:
    name: str
    type: IOTypes
    required: bool = True
```

This is analogous to how `ingest/base.py` uses a `Column` descriptor — name + Python type together. The pattern is consistent across the codebase.

Once you have `IOSlot`, update `BaseNode` so that `inputs`, `outputs`, and `params` are `list[IOSlot]`. The `ToyNode` in `toy_node.py` then becomes:

```python
inputs = [
    IOSlot(name="x", type=IOTypes.NUMERIC),
    IOSlot(name="y", type=IOTypes.NUMERIC),
]
outputs = [IOSlot(name="result", type=IOTypes.NUMERIC)]
```

This is more verbose, but the benefit is that the execution engine can now *map by name*, not by position. That matters as soon as nodes have optional inputs.

**Using Pydantic for params:** Node parameters (like `separator` on a CSV node, or `n_estimators` on a trainer) are different from inputs — they are configured by the user in the UI, not wired from other nodes. Model them as a Pydantic `BaseModel` subclass:

```python
class CsvSourceParams(BaseModel):
    file_path: str
    separator: str = ","
    encoding: str = "utf-8"
```

Why Pydantic? Because FastAPI uses it for request validation, and because Pydantic gives you automatic type coercion, default values, and JSON serialisation for free. When the frontend sends a node's configuration as JSON, Pydantic parses and validates it in one line.

**The `run()` signature:** Right now, `run(*args, **kwargs)` is too loose. A better contract:

```python
def run(self, inputs: dict[str, Any], params: BaseModel) -> dict[str, Any]:
```

Both inputs and outputs are keyed dicts matching the slot names. The execution engine calls `node.run(inputs={"x": 2.0, "y": 3.0}, params=node_params)` and the node returns `{"result": 5.0}`. This maps cleanly to the graph wiring: each edge connects `output_slot_name` of one node to `input_slot_name` of another.

### Building `NodeRegistry`

Now open `nodes/registry.py`. The docstring is already there — it tells you exactly what to build. Compare with `ingest/registry.py` and you will see the structure you need.

A registry is simply a class that wraps a `dict`. It needs three methods:

- `register(node_class)` — stores the class (or an instance) keyed by `node_id`
- `get(node_id)` — retrieves one entry
- `list()` — returns all entries for the `GET /nodes` endpoint

**Why a class instead of a module-level dict?**

A module-level dict would work, but a class lets you add behaviour later (e.g., logging on registration, validating that node_id is unique, loading plugin packages). It also makes testing easier — you can instantiate a fresh registry in each test rather than fighting global state.

**The singleton:** Like `DatasourceRegistry`, create a single `NODE_REGISTRY = NodeRegistry()` instance at the bottom of the file. All other modules import this instance, not the class. This is Python's preferred pattern for singletons — no metaclass magic, no `__new__` tricks.

### Self-registration with `__init_subclass__`

This is the most elegant Python pattern in the codebase. Read it carefully in `BaseDatasource`:

```python
def __init_subclass__(cls, **kwargs):
    super().__init_subclass__(**kwargs)
    if not getattr(cls, "key", ""):
        return  # skip abstract intermediate classes
    instance = cls()
    BaseDatasource._instances[cls.key] = instance
```

When Python *defines* a subclass (at import time, not at runtime), it calls `__init_subclass__` on the parent. This means the subclass registers itself automatically — the developer writing `CsvSourceNode` does not need to call `NODE_REGISTRY.register(CsvSourceNode)` anywhere. They just define the class in a file that gets imported.

Add the same hook to `BaseNode`. The guard against abstract intermediate classes is important: if someone makes a `BaseSourceNode(BaseNode)` as an intermediate abstract class (no `node_id` yet), it should not be registered. Check for a non-empty `node_id` before registering.

### Wiring up `GET /nodes`

Open `api/routes/graphs.py`. It is empty. Add a router:

```python
router = APIRouter(prefix="/graphs", tags=["graphs"])

@router.get("/nodes")
def list_nodes():
    # Return serialised schema for every registered node
    ...
```

For the response, you want each node's `node_id`, `display_name`, `category`, `inputs`, `outputs`, and `params schema`. Use Pydantic response models here — do not return raw dicts. This documents your API automatically in the OpenAPI UI at `/api/v1/openapi.json`.

Then register the router in `api/main.py`, following the exact same pattern used for `data.router`, `training.router`, etc.

**Test it manually:** Start the backend with `uvicorn app.main:app --reload` and open `http://localhost:8000/api/v1/openapi.json`. Your new endpoint should appear. If it does not, check that the router was included in `api_router` and that node files are being imported at startup.

### Auto-discovering node files

Look at how `api/main.py` discovers datasource plugins:

```python
for _plugin_path in sorted(_ingest_dir.glob("ds_*.py")):
    importlib.import_module(_module_name)
```

This loop imports every file matching the pattern at startup, which triggers `__init_subclass__` for every concrete datasource. Add the same mechanism for nodes: loop over `nodes/node_*.py` (or whatever naming convention you choose) and import them. This means adding a new node is as simple as dropping a file into the `nodes/` directory — no manual registration list to maintain.

### Writing the first real node: `CsvSourceNode`

Create `nodes/node_sources.py`. Define `CsvSourceNode(BaseNode)` with:

- `node_id = "csv_source"`
- `category = "Sources"`
- No inputs (source nodes have none — they produce data from configuration)
- One output: `IOSlot(name="dataframe", type=IOTypes.DATAFRAME)`
- A params class with `file_path`, `separator`, `encoding`

In `run()`, use `pandas.read_csv(params.file_path, sep=params.separator, encoding=params.encoding)` and return `{"dataframe": df}`.

**Why pandas?** The plan's `IOTypes.DATAFRAME` maps naturally to a pandas `DataFrame`. It's the lingua franca of Python data manipulation, already used throughout `training.py` and the ingest layer. When a node outputs a DataFrame, the next node receives a DataFrame — the execution engine passes Python objects in memory between nodes.

**Fix `toy_node.py` while you are here:** The test function is broken — it calls `assert result == 5` without defining `result`. This is a good moment to learn a Python testing discipline: always assign the return value before asserting it.

---

## Part 2 — Sprint 1: The Execution Engine

You now have a vocabulary (nodes, slots, params) and a registry. Sprint 1 adds the engine that takes a graph description — a JSON document listing nodes and the edges connecting them — and executes it.

### Defining the graph JSON schema

Before building the engine, define what the engine's input looks like. A graph has two things:

1. **Nodes:** each identified by a unique instance id (not the `node_id` type), with a chosen node type and parameter values.
2. **Edges:** each connecting one node's output slot to another node's input slot.

A minimal schema in Pydantic:

```python
class NodeInstance(BaseModel):
    instance_id: str       # unique within this graph, e.g. "node_0"
    node_type: str         # maps to NodeRegistry, e.g. "csv_source"
    params: dict           # raw dict — validated against the node's params model at runtime

class Edge(BaseModel):
    source_instance_id: str
    source_slot: str
    target_instance_id: str
    target_slot: str

class GraphSpec(BaseModel):
    nodes: list[NodeInstance]
    edges: list[Edge]
```

Why separate `instance_id` from `node_type`? Because the same node type can appear multiple times in a single graph (e.g., two CSV sources loading different files). The `instance_id` is the unique identity of *this particular use* of a node.

### Understanding Directed Acyclic Graphs (DAGs)

A graph in this system is a DAG: edges point from producers to consumers, and there are no cycles (a node cannot depend on its own output, directly or indirectly). This constraint is not arbitrary — it guarantees that there is always a valid execution order.

**Why no cycles?** If node A depends on B and B depends on A, there is no way to run either first. Execution would deadlock. ML pipelines are naturally acyclic: data flows forward from sources through transforms to outputs.

**Topological sort:** Given a DAG, a topological sort produces a linear ordering of nodes such that every producer comes before its consumers. Kahn's algorithm is the most intuitive implementation:

1. Build an *in-degree* map: for each node, count how many edges point *into* it.
2. Start a queue with all nodes that have in-degree zero (no dependencies — the sources).
3. Process the queue: pop a node, add it to the sorted output, then decrement the in-degree of every node it points to. If a node's in-degree reaches zero, add it to the queue.
4. If the sorted output contains all nodes, the sort succeeded. If nodes remain (in-degree never reached zero), you have a cycle — raise an error.

You do not need a graph library for this. Implement it yourself with a `dict` for in-degrees and a `collections.deque` for the queue. Doing it by hand teaches you far more than importing `networkx`.

### `GraphBuilder`: from JSON to executable plan

Create `nodes/executor.py`. Define a `GraphBuilder` class that takes a `GraphSpec` and produces an ordered execution plan.

The `build()` method should:

1. Look up each `node_type` in `NODE_REGISTRY`. Raise a `ValueError` if a type is not found — failing early with a clear message is better than a confusing `KeyError` later.
2. Build an adjacency structure from the edges.
3. Run topological sort to get an ordered list of `instance_id`s.
4. Return the ordered plan (list of node instances + edges, in execution order).

**Why a separate `GraphBuilder` instead of putting this logic in the API route?**

Separation of concerns. The API route's job is to receive an HTTP request, call the business logic, and return an HTTP response. The business logic (validating the graph, sorting nodes, executing them) belongs in a class that has no knowledge of HTTP. This makes the execution engine independently testable — you can write unit tests for `GraphBuilder` without spinning up a FastAPI app.

### The sync execution engine

Add an `execute(plan, params_map)` method to the executor:

1. Initialise an empty `outputs` dict: `{instance_id: {slot_name: value}}`.
2. For each node in topological order:
   - Collect its inputs by looking up the source slots in `outputs` (using the edge list).
   - Retrieve the registered node class from `NODE_REGISTRY`.
   - Parse the raw params dict into the node's typed params model.
   - Call `node.run(inputs=..., params=...)`.
   - Store the returned dict in `outputs[instance_id]`.
3. Return the final `outputs` dict.

**Error handling:** Wrap each `node.run()` call in a `try/except`. On failure, record the error message and the `instance_id`, then stop execution (or skip downstream nodes, depending on your policy). Do not let one broken node crash the whole process silently.

### The `GraphRun` database model

Every run needs to be tracked so the frontend can poll for status. Add a `GraphRun` model to `db_models.py`. Mirror the `ModelRunBase` pattern: use `SQLModel` as the base class (it gives you both SQLAlchemy table mapping and Pydantic serialisation in one class).

Fields you need at minimum: `run_id` (UUID string), `status` (pending/running/success/error), `graph_spec` (the JSON of the submitted graph, stored as a string), `result` (JSON of outputs, null until complete), `error` (error message, null on success), `created_at`, `updated_at`.

**Why store `graph_spec` as a string?** PostgreSQL has a native `JSONB` type, but SQLite (used in testing) does not. Storing JSON as `TEXT` keeps the code portable. You can always query it with `json.loads()` when you need it back.

**Creating the migration:** The project uses Alembic. After adding `GraphRun` to `db_models.py`, run:

```
docker-compose exec app alembic revision --autogenerate -m "add_graph_runs"
docker-compose exec app alembic upgrade head
```

Look at the generated file under `app/alembic/versions/`. Check that it creates the `graph_runs` table with the correct columns. Alembic's `--autogenerate` flag is convenient but not infallible — always review the generated migration before applying it.

### The run/status/result endpoints

Now fill in `api/routes/graphs.py` with three endpoints:

**`POST /graphs/run`:** Accepts a `GraphSpec`, creates a `GraphRun` row in the database with status `pending`, and — for now — executes the graph synchronously before returning. Return the `run_id`. You will add async execution in Sprint 3.

**`GET /graphs/{run_id}/status`:** Looks up the `GraphRun` by `run_id`, returns `status`, `created_at`, and any `error` message. This is the polling endpoint the frontend calls after submitting a run.

**`GET /graphs/{run_id}/result`:** Returns the full `result` JSON if status is `success`, or raises a `409 Conflict` if the run is still pending or failed. A `409` (not a `404`) is correct here because the resource *exists* — it is just not ready yet.

**`POST /graphs/validate`:** Does everything `POST /graphs/run` does except actually executing. Parse the graph, run topological sort, look up all node types — return `{"valid": true}` or an error detail. This endpoint lets the frontend give instant feedback before the user clicks Run.

---

## Part 3 — Sprint 2: Building Out the Node Library

With the execution engine working on `ToyNode`, it is time to build nodes that do real work. Sprint 2 is mostly Python — you are implementing the node categories from GRAPH_PLAN.md.

### General principle: nodes should be stateless

A node's `run()` method receives all the data it needs in `inputs` and `params`. It must not store state between calls, read from global variables, or have side effects beyond returning outputs and optionally writing to `artifacts/`. This makes nodes reproducible, cacheable, and easy to test in isolation.

### Source nodes

**`DatabaseSourceNode`:** This node loads data from the MLPlayground database using the existing `BaseDatasource` plugin system. In `run()`:

```python
from app.ingest.base import BaseDatasource
ds = BaseDatasource._instances.get(params.datasource_key)
rows, _ = ds.query(state=params.state, ...)
return {"dataframe": pd.DataFrame(rows)}
```

Notice how this delegates entirely to the existing `BaseDatasource.query()`. The node is a thin wrapper — it bridges the graph execution world and the data layer that already exists. This is the right level of abstraction.

**Why reuse `BaseDatasource._instances` rather than querying the database directly?** Because `BaseDatasource.query()` already handles lazy table creation, column mapping, and pagination. Duplicating that logic in a node would create two places to maintain the same behaviour.

### Transform nodes

Transform nodes take a DataFrame in and return a DataFrame out. They are all structurally similar:

- Input: `IOSlot(name="dataframe", type=IOTypes.DATAFRAME)`
- Output: `IOSlot(name="dataframe", type=IOTypes.DATAFRAME)`
- Params: whatever controls the transformation

**`FilterNode`:** Params include `column`, `operator` (one of `=`, `>`, `<`, `>=`, `<=`, `!=`), and `value`. In `run()`, apply the filter using pandas boolean indexing. Validate the operator against a known list before applying it — never pass user-controlled strings directly into `eval()` or SQL.

**`JoinNode`:** Params include `how` (inner/left/right/outer) and `on` (list of column names). Use `pd.merge()`. Think about what happens if the join key columns do not exist in one of the DataFrames — raise a clear `ValueError` rather than letting pandas produce a confusing error.

**`GroupByNode`:** Params include `group_columns` and an `aggregations` map (`{column_name: agg_function}`). Use `df.groupby().agg()`. Why expose aggregation as a dict rather than a single function? Because real use cases group by county and year while computing the mean of weather and the sum of yield — multiple aggregations at once.

### Modeling nodes

**`TrainerNode`:** Look at `training.py` — almost all the logic you need is already there. The node wraps it:

- Inputs: `dataframe` (the prepared feature+target DataFrame)
- Params: `model_type`, `target_column`, `feature_columns`, `test_size`
- Outputs: `model` (the fitted sklearn object), `metrics` (r2, rmse as a dict), `artifact_path` (the path to the saved `.pkl` file)

The key change from the existing `/train` endpoint is that the node does not load its own data — it receives a DataFrame from an upstream node. This is the whole point of the graph: separating data loading from model training, so you can swap either independently.

**Saving the artifact:** Use `joblib.dump()` just like `training.py` does. Save to `artifacts/models/{run_id}_{instance_id}.pkl`. Return the path as an `ARTIFACT` output slot. Downstream nodes (like `SHAPNode`) can receive this path as an input.

### Evaluation nodes

**`MetricsNode`:** Receives `predictions` and `actuals` arrays (or a DataFrame with those columns), computes R², RMSE, MAE. Returns a dict of metrics. Keeping metrics in a dedicated node means you can swap the model node without losing the evaluation logic.

**`SHAPNode`:** Receives a `model` and a `dataframe` (the test set). Uses the `shap` library to compute SHAP values. Save the SHAP summary plot to `artifacts/shap/{run_id}_{instance_id}.png`. Return the artifact path.

**Why save to `artifacts/shap/` specifically?** The project's `.github/copilot-instructions.md` specifies this path. Consistency with established conventions matters — other tools (artifact browser, model management UI) expect to find SHAP artifacts there.

### Utility nodes

**`SplitNode`:** Takes a DataFrame, splits it into train and test subsets. Params: `test_size`, `random_state`. Outputs: `train_df`, `test_df`. Use `sklearn.model_selection.train_test_split` — do not reimplement it.

**`PreviewNode`:** Takes any DataFrame input and returns it unchanged, but additionally computes a preview (first 20 rows as a list of dicts). The preview is returned as a second output slot so the frontend can display it inline without downloading the full dataset.

**`SaveArtifactNode`:** Takes a DataFrame and a file path param, saves as CSV or Parquet (chosen by the file extension). Returns the saved path as an `ARTIFACT` output. This is how graph runs export their results to `artifacts/`.

---

## Part 4 — Sprint 3: Async Execution, Caching, and the Artifact Browser

Sprint 3 makes the system production-capable: long-running graphs do not block the web server, repeated runs on unchanged data return instantly from cache, and the frontend can browse and download artifacts.

### Why `asyncio` alone is not enough

FastAPI is an async framework, so you might think you can just use `async def` and `await` for long-running node execution. This works for I/O-bound work (network calls, database queries) but *not* for CPU-bound work like model training. Python's GIL means only one thread executes Python bytecode at a time. An LSTM training for 30 seconds in an `async` function will still block the entire event loop, making the API unresponsive for that duration.

The solution is to push CPU-bound work to a separate *process* (not thread). Tools like **RQ** (Redis Queue) or **Celery** do exactly this: the web server enqueues a job and returns immediately; a worker process picks up the job and runs it independently.

### The async execution flow

With a worker queue, `POST /graphs/run` changes:

1. Receive the `GraphSpec`, create a `GraphRun` row in the DB with status `pending`.
2. Serialise the graph spec and the `run_id`, enqueue the job to Redis (with RQ: `queue.enqueue(execute_graph, run_id, graph_spec_json)`).
3. Return `{"run_id": run_id}` immediately — the HTTP response goes out *before* any node runs.

The worker function `execute_graph(run_id, graph_spec_json)` runs in a separate process:

1. Load the graph spec, run `GraphBuilder.build()` and `execute()`.
2. On success: update `GraphRun.status = "success"`, store the result JSON, update `updated_at`.
3. On failure: update `GraphRun.status = "error"`, store the error message.

The frontend polls `GET /graphs/{run_id}/status` until it sees `success` or `error`.

**RQ setup:** Add a `workers/` directory. Create `workers/graph_worker.py` with the `execute_graph` function. Add an RQ worker startup command to `docker-compose.yml` (a separate service running `rq worker`). RQ requires Redis — add a Redis service to the compose file if one does not already exist.

### Content-addressable caching

Caching is one of the most impactful performance optimisations for an ML workflow engine. The idea: if a node's inputs and params have not changed since the last run, skip re-running it and return the cached outputs.

**The cache key:** Use a hash of the node's configuration and its upstream outputs. Python's `hashlib` module makes this straightforward:

```python
import hashlib, json

def compute_node_hash(node_type: str, params: dict, input_hashes: dict[str, str]) -> str:
    payload = {
        "node_type": node_type,
        "params": params,
        "inputs": input_hashes,   # each input's value is itself a hash of its producer
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
```

The `sort_keys=True` argument to `json.dumps` is critical — it ensures the same dict always produces the same string regardless of insertion order.

**Where to store cached outputs:** For DataFrames, write them to a file in `artifacts/cache/{hash}.parquet`. For scalar values, store them in the database. For model objects, use `joblib` as you do for regular artifacts.

**Partial execution:** During `GraphBuilder.build()`, compute the hash for every node in topological order. If a node's hash is already in the cache, mark it as `cached=True` in the execution plan. In the executor, skip `node.run()` for cached nodes and load outputs from the cache store instead. Only nodes downstream of *changed* nodes need to re-run.

### The artifact browser endpoint

The plan specifies `GET /artifacts/{path}` to download artifact files. Add this to `graphs.py`:

```python
from fastapi.responses import FileResponse
from pathlib import Path

ARTIFACTS_ROOT = Path("/app/artifacts")

@router.get("/artifacts/{path:path}")
def download_artifact(path: str):
    full_path = (ARTIFACTS_ROOT / path).resolve()
    if not str(full_path).startswith(str(ARTIFACTS_ROOT)):
        raise HTTPException(status_code=403, detail="Access denied.")
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(full_path)
```

**Why the `resolve()` + `startswith` check?** This guards against *path traversal attacks*. A malicious client could send `path = "../../etc/passwd"`. Without the check, `ARTIFACTS_ROOT / "../../etc/passwd"` resolves to `/etc/passwd`. The `resolve()` call expands `..` to absolute paths, and `startswith` verifies the result is still inside `ARTIFACTS_ROOT`. Never skip this check for user-provided file paths.

### Sandboxing custom Python UDF nodes

GRAPH_PLAN.md includes a `Custom Python UDF` transform. This is a node whose logic is user-supplied code. Running arbitrary user code in the web server process is dangerous — a user could call `os.system()`, read environment variables containing secrets, or consume all available memory.

**Minimum viable sandboxing:**

1. Run UDF nodes in the *worker process* only, never in the web server.
2. Use Python's `RestrictedPython` package to parse and compile the user code with import restrictions.
3. Set resource limits on the worker process using `resource.setrlimit()` before executing UDFs (limit CPU time, memory, file size).
4. Consider running UDFs in a separate Docker container with no network access and read-only filesystem mounts.

Sandboxing is a deep topic. For an MVP, at minimum run UDFs in the worker (not the web server) and document the restrictions clearly in the API response for `GET /nodes` for the UDF node.

---

## Putting It All Together

After these four sprints, your system has:

- A **type-safe node registry** that auto-discovers nodes at startup, mirroring the existing datasource registry.
- A **DAG execution engine** that topologically sorts nodes, calls them in order, and passes typed outputs between them.
- A **full API** covering graph validation, async run submission, status polling, result retrieval, and artifact download.
- A **library of concrete nodes** spanning sources, transforms, modeling, evaluation, and utilities.
- A **caching layer** that skips unchanged nodes on re-runs.
- A **worker queue** that keeps the API responsive during long model-training runs.

The design decisions throughout have been guided by two principles:

1. **Consistency with what already exists.** Every new pattern mirrors an existing one (NodeRegistry mirrors DatasourceRegistry, nodes save artifacts the same way training.py does). This makes the codebase navigable.
2. **Separation of concerns.** HTTP routing, graph execution, node logic, and artifact storage are independent layers. You can test, swap, or extend each layer without touching the others.

These are not theoretical ideals — they are the practical habits that make a codebase maintainable six months after it was written.
