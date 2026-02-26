# Contributing to MLPlayground

This guide explains how to add a new **data source** or **machine-learning model** to MLPlayground. It is written for researchers who are comfortable editing Python files but may not be familiar with web frameworks, databases, or TypeScript.

**Time estimate:** ~1 hour for a new data source; ~30 minutes for a new model type.

---

## Adding a New Data Source

A "data source" is any external dataset you want to fetch and store — for example, satellite NDVI imagery, drought indices, pest-pressure scores, or market prices.

MLPlayground uses a **6-step pattern** for each data source:

| Step | File | What it does |
|---|---|---|
| 1 | `backend/app/ingest/your_source.py` | Fetch + clean the data; register with the datasource registry |
| 2 | `backend/app/db_models.py` | Define the database table (~15 lines) |
| 3 | Alembic migration | Create the table automatically |
| 4 | `backend/app/api/routes/your_source.py` | Expose the data as a REST endpoint |
| 5 | `backend/app/api/main.py` | Wire the endpoint into the app (2 lines) |
| 6 | `backend/app/ingest/runner.py` | Call your fetcher during ingestion |

### Step 1 — Write the ingest script and register it

Copy the template file and rename it:

```bash
cp backend/app/ingest/template_datasource.py backend/app/ingest/my_source.py
```

Open your new file and work through every `# TODO` comment. Set `DATASOURCE_NAME`, `DATASOURCE_COLUMNS`, and `SCOPE_PARAMS`, then implement `fetch_data(**scope) -> pd.DataFrame`.

At the bottom of the file, register with the datasource registry:

```python
DATASOURCE_REGISTRY.register(
    key=DATASOURCE_NAME,
    label="My Source",
    endpoint="/api/v1/my_source/",
    columns=DATASOURCE_COLUMNS,
    scope_params=SCOPE_PARAMS,
)
```

This registration drives the Explore tab, the Ingest scope form, and the Model feature picker — **all automatically, with zero frontend changes**.

### Step 2 — Add a database model

Open `backend/app/db_models.py` and add a new block at the bottom (copy the `Weather` block as a template):

```python
class MySourceBase(SQLModel):
    year: int
    state: str
    county: str
    my_metric: Optional[float] = None

class MySource(MySourceBase, table=True):
    __tablename__ = "my_source"
    id: Optional[int] = Field(default=None, primary_key=True)

class MySourcePublic(MySourceBase):
    id: int

class MySourcesPublic(SQLModel):
    data: list[MySourcePublic]
    count: int
```

### Step 3 — Run the database migration

```bash
docker compose exec backend alembic revision --autogenerate -m "Add my_source table"
docker compose exec backend alembic upgrade head
```

### Step 4 — Add an API route

```bash
cp backend/app/api/routes/weather.py backend/app/api/routes/my_source.py
```

Replace every occurrence of `Weather` / `weather` with your model names and adjust the query filters to match your columns.

### Step 5 — Wire the route into the app

Open `backend/app/api/main.py` and add two lines:

```python
from app.api.routes import my_source
api_router.include_router(my_source.router)
```

### Step 6 — Call the fetcher from the runner

Open `backend/app/ingest/runner.py` and add your fetcher to the per-source dispatch section (follow the existing pattern for `yields_nass`, `weather_daymet`, etc.).

### Test it

```bash
docker compose up --build

# Trigger ingestion for your new source
curl -X POST http://localhost:8000/api/v1/ingest/run \
  -H "Content-Type: application/json" \
  -d '{"sources": ["my_source"], "scope": {"states": ["North Carolina"], "start_year": 2010, "end_year": 2022}}'

# Check your new endpoint
curl "http://localhost:8000/api/v1/my_source/?state=North+Carolina"
```

The Explore page will have a new tab and the interactive API docs at `http://localhost:8000/docs` will list your new endpoint — all automatically.

---

## Adding a New Model Type

Models live in `backend/app/api/routes/training.py`. The frontend discovers model types from `/api/v1/models/types` — **never hardcode model names in React**.

### Step 1 — Add to `MODEL_REGISTRY` and `MODEL_TYPES`

```python
MODEL_TYPES = Literal["linear_regression", "random_forest", "gradient_boosting", "lstm", "my_new_model"]

MODEL_REGISTRY = {
    ...
    "my_new_model": {"label": "My New Model", "kind": "sklearn", "description": "...", "supports_predict": True},
}
```

### Step 2 — Add a training branch

In the `train_model` endpoint, add:

```python
elif req.model_type == "my_new_model":
    model = MyModelClass(...)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    rmse = mean_squared_error(y_test, y_pred, squared=False)
    importances = model.feature_importances_  # or coef_
```

The platform handles the data join, train/test split, serialization to `artifacts/models/`, and the `model_runs` DB record — you only implement the fit/predict logic.

---

## Difficulty Assessment (Researcher Perspective)

| Task | Difficulty | Notes |
|---|---|---|
| Writing a fetch function | ★★☆☆☆ | Template + examples make this straightforward |
| Registering with DATASOURCE_REGISTRY | ★☆☆☆☆ | Four lines; pattern matches template exactly |
| Adding a database model | ★★★☆☆ | Copy-paste pattern; ORM syntax may be unfamiliar |
| Running migrations | ★☆☆☆☆ | Two commands; hard to get wrong |
| Copying a route file | ★★☆☆☆ | Find-and-replace task |
| Adding a model type | ★★☆☆☆ | One dict entry + one elif branch |

**Overall:** A researcher comfortable with Python can add a new data source in ~1 hour without understanding the full stack.

---

## Getting Help

- API documentation: http://localhost:8000/docs
- All endpoints return JSON; test them directly in your browser or with `curl`
- Backend logs: `docker compose logs backend -f`
- Database UI: http://localhost:8080 (Adminer)
