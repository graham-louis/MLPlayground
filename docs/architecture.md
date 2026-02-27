# MLPlayground — Architecture & Design Diagrams

> All diagrams use [Mermaid](https://mermaid.js.org/). Render them in any Mermaid-compatible viewer (GitHub, VS Code extension, mermaid.live).

---

## 1. System Architecture

High-level view of all components and how they communicate.

```mermaid
graph TB
    subgraph Browser["Browser (React / TanStack Router)"]
        UI_Explore["Data Explorer <br>/explore"]
        UI_Ingest["Ingest\n/ingest"]
        UI_Model["Model Training\n/model"]
    end

    subgraph API["FastAPI Backend (:8000)"]
        RT_Data["/api/v1/data/{key}\nGeneric datasource query"]
        RT_DS["/api/v1/datasources/\nRegistry metadata"]
        RT_Ingest["/api/v1/ingest/\nrun · status/{job_id}"]
        RT_Models["/api/v1/models/\ntrain · predict · runs"]
    end

    subgraph Plugins["Datasource Plugins (ds_*.py)"]
        DS_Yields["ds_yields.py\ntable: yields"]
        DS_Weather["ds_weather.py\ntable: weather"]
        DS_DW["ds_daily_weather.py\ntable: daily_weather"]
        DS_Soil["ds_soil.py\ntable: soil"]
    end

    subgraph DB["PostgreSQL"]
        T_Plugin[("Plugin-managed tables\nyields · weather · soil\ndaily_weather · ...")]
        T_Runs[(model_runs\nAlembic-managed)]
    end

    subgraph Ext["External APIs"]
        NASS["USDA NASS\nCrop yields"]
        Daymet["NASA Daymet\nWeather"]
        SSURGO["USDA SSURGO\nSoil"]
    end

    subgraph Artifacts["Local Disk /app/artifacts"]
        PKL["Trained models\n*.pkl (joblib)"]
    end

    Browser -->|REST/JSON| API
    RT_Data --> Plugins
    RT_DS --> Plugins
    Plugins --> DB
    RT_Ingest -->|HTTP fetch| Ext
    RT_Models -->|save/load| Artifacts
    RT_Models --> DB

    classDef frontend fill:#3b82f6,color:#fff,stroke:#1d4ed8
    classDef api fill:#6366f1,color:#fff,stroke:#4338ca
    classDef plugin fill:#0d9488,color:#fff,stroke:#0f766e
    classDef db fill:#d97706,color:#fff,stroke:#b45309
    classDef ext fill:#ea580c,color:#fff,stroke:#c2410c
    classDef artifact fill:#475569,color:#fff,stroke:#334155

    class UI_Explore,UI_Ingest,UI_Model frontend
    class RT_Data,RT_DS,RT_Ingest,RT_Models api
    class DS_Yields,DS_Weather,DS_DW,DS_Soil plugin
    class T_Plugin,T_Runs db
    class NASS,Daymet,SSURGO ext
    class PKL artifact

    style Browser fill:#dbeafe,stroke:#93c5fd,color:#1e3a8a
    style API fill:#e0e7ff,stroke:#a5b4fc,color:#312e81
    style Plugins fill:#ccfbf1,stroke:#5eead4,color:#134e4a
    style DB fill:#fef3c7,stroke:#fcd34d,color:#78350f
    style Ext fill:#ffedd5,stroke:#fed7aa,color:#7c2d12
    style Artifacts fill:#f1f5f9,stroke:#cbd5e1,color:#1e293b
```

---

## 2. Data Flow — Ingestion → Training → Prediction

End-to-end lifecycle of data.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'actorBkg': '#e0e7ff', 'actorBorder': '#6366f1', 'actorTextColor': '#1e3a8a', 'activationBkgColor': '#bfdbfe', 'activationBorderColor': '#3b82f6', 'noteBkgColor': '#fef3c7', 'noteTextColor': '#78350f', 'loopTextColor': '#312e81'}}}%%

sequenceDiagram
    actor User
    participant FE as Frontend
    participant API as FastAPI
    participant Ingest as Ingest Module
    participant ExtAPI as External API
    participant DB as PostgreSQL
    participant ML as ML Module
    participant Disk as Artifacts Disk

    User->>FE: Select datasources + scope, click Ingest
    FE->>API: POST /api/v1/ingest/run {sources, scope}
    API-->>FE: {job_id}
    FE->>API: GET /api/v1/ingest/status/{job_id}  (poll every 2s)
    loop per county
        API->>Ingest: fetch_and_transform(county, year_range)
        Ingest->>ExtAPI: HTTP request
        ExtAPI-->>Ingest: raw data
        Ingest->>DB: UPSERT rows
        API-->>FE: {progress, status, message}
    end
    API-->>FE: {status: "done"}

    User->>FE: Configure model, click Train
    FE->>API: POST /api/v1/models/train {model_type, filters, features}
    API->>DB: SELECT joined data
    DB-->>API: DataFrame
    API->>ML: fit(X_train, y_train)
    ML-->>API: fitted model + metrics
    API->>Disk: joblib.dump(model, {run_id}.pkl)
    API->>DB: INSERT model_runs row
    API-->>FE: {run_id, r2, rmse, feature_importances}
    FE->>User: Show results + "Model Saved" alert

    User->>FE: Enter features, click Predict
    FE->>API: POST /api/v1/models/{run_id}/predict {features}
    API->>Disk: joblib.load({run_id}.pkl)
    API-->>FE: {predicted_yield, units}
    FE->>User: Show prediction
```

---

## 3. Database Schema

`model_runs` is the only Alembic-managed table. All datasource tables (yields, weather, etc.) are **plugin-managed** — created lazily by `BaseDatasource._get_table()` on first use. They do not appear in `db_models.py` and have no Alembic migrations.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#fef3c7', 'primaryBorderColor': '#d97706', 'primaryTextColor': '#78350f', 'lineColor': '#6b7280', 'attributeBackgroundColorEven': '#fffbeb', 'attributeBackgroundColorOdd': '#fef9c3'}}}%%
erDiagram
    MODEL_RUNS {
        string  run_id      PK
        string  model_type
        string  state
        string  crop
        int     start_year
        int     end_year
        float   r2
        float   rmse
        int     n_train
        int     n_test
        json    feature_columns
        json    filters
        json    datasources
        json    join_keys
        datetime created_at
    }

    PLUGIN_TABLES["Plugin-Managed Tables\n(schema from ds_*.py columns)"] {
        string  key
        string  columns     "Defined by BaseDatasource subclass"
        string  table_name  "e.g. yields, weather, soil, daily_weather"
        string  created_by  "BaseDatasource._get_table() on first upsert"
    }
```

---

## 4. Datasource Plugin System — Adding a New Data Source

All datasource functionality — table creation, API endpoint, Explore tab, Ingest selector — is handled by creating a single `ds_*.py` file.

```mermaid
flowchart TD
    A["Copy template\ncp template_datasource.py ds_my_source.py"] --> B["Set identity\nkey, label, description"]
    B --> C["Define schema\nColumn('name', type) list"]
    C --> D["Set scope_params\n(optional defaults)"]
    D --> E["Implement fetch()\nCall API → return DataFrame"]
    E --> F["Save file in\nbackend/app/ingest/ds_my_source.py"]
    F --> G["Restart backend\n(auto-discovery imports ds_*.py)"]
    G --> H["BaseDatasource.__init_subclass__\nauto-registers in DATASOURCE_REGISTRY\nauto-creates DB table on first use"]
    H --> I["Frontend auto-detects\nExplore tab + Ingest selector\ndriven by /api/v1/datasources/"]
    H --> J["GET /api/v1/data/my_source\navailable immediately"]

    classDef user fill:#3b82f6,color:#fff,stroke:#1d4ed8
    classDef framework fill:#0d9488,color:#fff,stroke:#0f766e
    classDef frontend fill:#6366f1,color:#fff,stroke:#4338ca

    class A,B,C,D,E,F user
    class G,H framework
    class I,J frontend
```

### Registry Entry Fields (set on the `BaseDatasource` subclass)

| Field | Purpose |
|-------|---------|
| `key` | Unique identifier (e.g. `"yields"`) — also the URL slug (`/api/v1/data/yields`) |
| `label` | Human-readable name shown in Explore tabs and Ingest selector |
| `description` | Tooltip text shown in the Explorer tab |
| `columns` | `Column("name", type)` list — defines the DB table schema and Explorer headers |
| `scope_params` | Filter inputs rendered in Ingest UI (state, year range, etc.) |
| `endpoint` | **Auto-set** to `/api/v1/data/<key>` — never set manually |

---

## 5. Model Registry — Adding a New Model Type

```mermaid
flowchart TD
    A[Choose model kind:\nsklearn / pytorch] --> B{Kind}

    B -->|sklearn| C[Add entry to MODEL_REGISTRY dict\nin backend/app/api/routes/training.py]
    B -->|pytorch| D[Implement custom training loop\ne.g. LSTM in training.py]

    C --> F[Add elif branch in /train endpoint\nfit model, compute metrics]
    D --> F

    F --> G[joblib.dump artifact\nInsert model_runs row]

    G --> H[Frontend shows model in\ndropdown and Saved Models tab]
    H --> I[GET /api/v1/models/types auto-includes it]

    classDef decision fill:#f8fafc,color:#1e293b,stroke:#94a3b8
    classDef api fill:#6366f1,color:#fff,stroke:#4338ca
    classDef ml fill:#16a34a,color:#fff,stroke:#15803d
    classDef artifact fill:#475569,color:#fff,stroke:#334155
    classDef frontend fill:#3b82f6,color:#fff,stroke:#1d4ed8

    class B,G decision
    class A,F api
    class C,D ml
    class G artifact
    class H,I frontend
```

---

## 6. Frontend Page Map

```mermaid
graph LR
    Nav["Nav Bar"] --> Explore["/explore\nData Explorer"]
    Nav --> Ingest["/ingest\nData Ingestion"]
    Nav --> Model["/model\nModel Training"]

    Explore --> ExTab1["Tabs (data-driven)\nfrom /api/v1/datasources/"]
    ExTab1 --> ExFilter["Filter: state · county · years · crop"]
    ExFilter --> ExTable["Data table\n+ column histogram on click"]

    Ingest --> InSel["Datasource multi-select"]
    InSel --> InScope["Scope params\n(state, year range)"]
    InScope --> InProgress["POST /ingest/run → job_id\nProgress bar polling"]

    Model --> MTrain["Train & Evaluate tab"]
    Model --> MPredict["Predict Yield tab"]
    Model --> MSaved["Saved Models tab"]

    MTrain --> MConfig["Model type (from API)\nState · Crop · Year range\nFeature columns"]
    MConfig --> MResults["R² · RMSE · Feature importances\nModel Saved badge"]
    MSaved --> MSTable["Table of runs\nSelect for prediction"]

    classDef nav fill:#1e293b,color:#fff,stroke:#0f172a
    classDef page fill:#3b82f6,color:#fff,stroke:#1d4ed8
    classDef tab fill:#6366f1,color:#fff,stroke:#4338ca
    classDef content fill:#dbeafe,color:#1e3a8a,stroke:#93c5fd

    class Nav nav
    class Explore,Ingest,Model page
    class ExTab1,InSel,MTrain,MPredict,MSaved tab
    class ExFilter,ExTable,InScope,InProgress,MConfig,MResults,MSTable content
```

---

## 7. Deployment (Docker Compose)

```mermaid
graph TB
    subgraph compose["docker-compose stack"]
        FE_SVC["frontend\n:3000 (Vite dev / nginx)"]
        API_SVC["backend (FastAPI/Uvicorn)\n:8000"]
        DB_SVC["postgres\n:5432"]
    end

    subgraph volumes["Named Volumes"]
        PG_DATA[("postgres_data")]
        ARTIFACTS[("./artifacts → /app/artifacts")]
    end

    FE_SVC -->|HTTP proxy /api/*| API_SVC
    API_SVC -->|SQLAlchemy| DB_SVC
    DB_SVC --- PG_DATA

    classDef frontend fill:#3b82f6,color:#fff,stroke:#1d4ed8
    classDef api fill:#6366f1,color:#fff,stroke:#4338ca
    classDef db fill:#d97706,color:#fff,stroke:#b45309
    classDef storage fill:#475569,color:#fff,stroke:#334155

    class FE_SVC frontend
    class API_SVC api
    class DB_SVC db
    class PG_DATA,ARTIFACTS storage

    style compose fill:#f8fafc,stroke:#cbd5e1,color:#1e293b
    style volumes fill:#f1f5f9,stroke:#94a3b8,color:#1e293b
    API_SVC --- ARTIFACTS
```
