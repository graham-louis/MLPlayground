# Contributing to MLPlayground

This guide explains how to add a new **data source** or **machine-learning model** to MLPlayground. It is written for researchers who are comfortable editing Python files but may not be familiar with web frameworks, databases, or TypeScript.

**Time estimate:** ~1 hour for a new data source; ~30 minutes for a new model type.

---

## Adding a New Data Source

A "data source" is any external dataset you want to fetch and store — for example, satellite NDVI imagery, drought indices, pest-pressure scores, or market prices.

MLPlayground uses a **5-file pattern** for each data source:

| File | What it does | Do I need to change it? |
|---|---|---|
| `backend/app/ingest/your_source.py` | Fetches and cleans the data | **Yes — create this file** |
| `backend/app/models.py` | Defines the database table | **Yes — add ~15 lines** |
| `backend/app/api/routes/your_source.py` | Exposes the data as a REST endpoint | **Yes — copy an existing one** |
| `backend/app/api/main.py` | Wires the endpoint into the app | **Yes — add 2 lines** |
| `backend/app/ingest/runner.py` | Runs ingestion for all counties | **Yes — add ~5 lines** |

### Step 1 — Write the ingest script

Copy the template file and rename it:

```bash
cp backend/app/ingest/template_datasource.py backend/app/ingest/my_source.py
```

Open your new file and work through every `# TODO` comment. The key function to implement is:

```python
def fetch_and_transform(county_name, state_name, start_year, end_year) -> pd.DataFrame:
    ...
```

It must return a pandas DataFrame with at least these columns:

| Column | Type | Description |
|---|---|---|
| `year` | int | The year of the observation |
| `county` | str | County name (must match what was passed in) |
| `state` | str | State name (must match what was passed in) |
| `source` | str | Short name of your datasource |
| *(your columns)* | float | Your domain-specific measurements |

### Step 2 — Add a database model

Open `backend/app/models.py` and add a new block at the bottom (copy the `Weather` block as a template and rename it):

```python
# --- My New Source Models ---
class MySourceBase(SQLModel):
    year: int
    state: str
    county: str
    my_metric: Optional[float] = None    # add your columns here

class MySource(MySourceBase, table=True):
    __tablename__ = "my_source"          # must be lowercase, no spaces
    id: Optional[int] = Field(default=None, primary_key=True)

class MySourcePublic(MySourceBase):
    id: int

class MySourcesPublic(SQLModel):
    data: list[MySourcePublic]
    count: int
```

### Step 3 — Run the database migration

This creates the new table automatically. Run these two commands from your terminal (Docker must be running):

```bash
docker compose exec backend alembic revision --autogenerate -m "Add my_source table"
docker compose exec backend alembic upgrade head
```

If you see `INFO  [alembic.runtime.migration] Running upgrade` — you're done.

### Step 4 — Add an API route

Copy an existing route file:

```bash
cp backend/app/api/routes/weather.py backend/app/api/routes/my_source.py
```

Open `my_source.py` and replace every occurrence of `Weather` / `weather` / `WeathersPublic` with your model names. Adjust the query filters to match your columns.

Then open `backend/app/api/main.py` and add two lines (follow the existing pattern):

```python
from app.api.routes import my_source   # add to imports at top
api_router.include_router(my_source.router)   # add after the other include_router calls
```

### Step 5 — Register in the runner

Open `backend/app/ingest/runner.py`.

At the top, add an import:

```python
from app.ingest.my_source import fetch_and_transform as fetch_my_source
```

Inside the `main()` function, add a upsert function (copy `upsert_weather_to_db` as a template) and call it inside the per-county loop:

```python
try:
    my_df = fetch_my_source(county, state, start_year, end_year)
    upsert_my_source_to_db(my_df)
except Exception as exc:
    logger.error("MySource ingestion failed for %s, %s: %s", county, state, exc)
```

### Step 6 — Test it

```bash
# Start everything
docker compose up --build

# Trigger ingestion for one county to test
curl -X POST http://localhost:8000/api/v1/ingest/trigger

# Check your new endpoint
curl "http://localhost:8000/api/v1/my_source/?state=North+Carolina"
```

The interactive API docs at `http://localhost:8000/docs` will show your new endpoint automatically.

---

## Adding a New Model Type

Models live in `backend/app/api/routes/models.py`. Adding a new scikit-learn model takes **three steps**:

### Step 1 — Add the model to the map

Open `backend/app/api/routes/models.py` and find `model_map`:

```python
model_map = {
    "linear_regression":  LinearRegression(),
    "random_forest":      RandomForestRegressor(...),
    "gradient_boosting":  GradientBoostingRegressor(...),
    # Add your model here:
    "my_new_model":       MyModelClass(param1=..., param2=...),
}
```

### Step 2 — Update the type hint

In the same file, update `MODEL_TYPES`:

```python
MODEL_TYPES = Literal["linear_regression", "random_forest", "gradient_boosting", "my_new_model"]
```

### Step 3 — Add it to the frontend dropdown

Open `frontend/src/routes/model.tsx` and add your model to `MODEL_OPTIONS`:

```typescript
const MODEL_OPTIONS = [
  { value: "random_forest",     label: "Random Forest" },
  { value: "gradient_boosting", label: "Gradient Boosting" },
  { value: "linear_regression", label: "Linear Regression" },
  { value: "my_new_model",      label: "My New Model" },  // ← add this
]
```

That's it. The training form, results display, and feature importance chart will all work automatically.

---

## Difficulty Assessment (Researcher Perspective)

| Task | Difficulty | Notes |
|---|---|---|
| Writing a fetch function | ★★☆☆☆ | Template + examples make this straightforward |
| Adding a database model | ★★★☆☆ | Copy-paste pattern; ORM syntax may be unfamiliar |
| Running migrations | ★☆☆☆☆ | Two commands; hard to get wrong |
| Copying a route file | ★★☆☆☆ | Find-and-replace task |
| Registering in runner.py | ★★☆☆☆ | Three lines; template shows exact pattern |
| Adding a model type | ★★☆☆☆ | One dict entry + one type update |
| Editing the frontend dropdown | ★☆☆☆☆ | One line; no TypeScript knowledge required |

**Overall**: A researcher comfortable with Python can add a new data source in ~1 hour without understanding the full stack.

---

## Getting Help

- API documentation: http://localhost:8000/docs
- All endpoints return JSON; test them directly in your browser or with `curl`
- Backend logs: `docker compose logs backend -f`
- Database UI: http://localhost:8080 (Adminer)
