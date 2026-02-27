# Contributing to MLPlayground

This guide explains how to add a new **data source** or **machine-learning model** to MLPlayground. It is written for researchers who are comfortable editing Python files but may not be familiar with web frameworks, databases, or TypeScript.

**Time estimate:** ~15 minutes for a new data source; ~30 minutes for a new model type.

---

## Adding a New Data Source

A "data source" is any external dataset you want to fetch and store — for example, satellite NDVI imagery, drought indices, pest-pressure scores, or market prices.

### Create one file — nothing else

Copy the template and rename it with a `ds_` prefix:

```bash
cp backend/app/ingest/template_datasource.py backend/app/ingest/ds_my_source.py
```

Open your new file and fill in the four `# TODO` sections:

1. **Identity** — set `key`, `label`, and `description` on the class
2. **Schema** — list your `Column("name", type)` entries
3. **Scope params** (optional) — adjust the ingest form defaults
4. **`fetch()` method** — call your API and return a DataFrame

That's the entire contribution.  You do **not** need to:
- Edit `db_models.py` — the table is created automatically from your `columns`
- Run Alembic — no migration needed
- Create an API route — data is queryable at `GET /api/v1/data/<key>` automatically
- Edit `main.py` — the `ds_*.py` naming convention triggers auto-discovery at startup

### Test it

```bash
docker compose up --build

# Trigger ingestion for your new source
curl -X POST http://localhost:8000/api/v1/ingest/run \
  -H "Content-Type: application/json" \
  -d '{"sources": ["my_source"], "scope": {"states": ["North Carolina"], "start_year": 2010, "end_year": 2022}}'

# Query the data
curl "http://localhost:8000/api/v1/data/my_source?state=North+Carolina"
```

The Explore page will have a new tab and the interactive API docs at `http://localhost:8000/docs` will list your new endpoint — all automatically.

See `backend/app/ingest/ds_weather_psa.py` for a complete real-world example.

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
| Defining a schema | ★☆☆☆☆ | List of `Column("name", type)` — no ORM knowledge needed |
| Adding a model type | ★★☆☆☆ | One dict entry + one elif branch |

**Overall:** A researcher comfortable with Python can add a new data source in ~15 minutes.

---

## Getting Help

- API documentation: http://localhost:8000/docs
- All endpoints return JSON; test them directly in your browser or with `curl`
- Backend logs: `docker compose logs backend -f`
- Database UI: http://localhost:8080 (Adminer)

