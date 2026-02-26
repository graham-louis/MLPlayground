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
        RT_Yields["/api/v1/yields/"]
        RT_Weather["/api/v1/weather/"]
        RT_Soil["/api/v1/soil/"]
        RT_DW["/api/v1/daily-weather/"]
        RT_Ingest["/api/v1/ingest/\nrun · status/{job_id}"]
        RT_Models["/api/v1/models/\ntrain · predict · runs"]
        RT_DS["/api/v1/datasources/"]
    end

    subgraph DB["PostgreSQL"]
        T_Yields[(yields)]
        T_Weather[(weather)]
        T_Soil[(soil)]
        T_DW[(daily_weather)]
        T_Runs[(model_runs)]
    end

    subgraph Ext["External APIs"]
        NASS["USDA NASS\nCrop yields"]
        NLDAS["NASA NLDAS-2\nWeather"]
        SSURGO["USDA SSURGO\nSoil"]
    end

    subgraph Artifacts["Local Disk /app/artifacts"]
        PKL["Trained models\n*.pkl (joblib)"]
    end

    Browser -->|REST/JSON| API
    API --> DB
    RT_Ingest -->|HTTP fetch| Ext
    RT_Models -->|save/load| Artifacts

    classDef frontend fill:#3b82f6,color:#fff,stroke:#1d4ed8
    classDef api fill:#6366f1,color:#fff,stroke:#4338ca
    classDef db fill:#d97706,color:#fff,stroke:#b45309
    classDef ext fill:#ea580c,color:#fff,stroke:#c2410c
    classDef artifact fill:#475569,color:#fff,stroke:#334155

    class UI_Explore,UI_Ingest,UI_Model frontend
    class RT_Yields,RT_Weather,RT_Soil,RT_DW,RT_Ingest,RT_Models,RT_DS api
    class T_Yields,T_Weather,T_Soil,T_DW,T_Runs db
    class NASS,NLDAS,SSURGO ext
    class PKL artifact

    style Browser fill:#dbeafe,stroke:#93c5fd,color:#1e3a8a
    style API fill:#e0e7ff,stroke:#a5b4fc,color:#312e81
    style DB fill:#fef3c7,stroke:#fcd34d,color:#78350f
    style Ext fill:#ffedd5,stroke:#fed7aa,color:#7c2d12
    style Artifacts fill:#f1f5f9,stroke:#cbd5e1,color:#1e293b
    style Sim fill:#ffe4e6,stroke:#fecdd3,color:#881337
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

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#fef3c7', 'primaryBorderColor': '#d97706', 'primaryTextColor': '#78350f', 'lineColor': '#6b7280', 'attributeBackgroundColorEven': '#fffbeb', 'attributeBackgroundColorOdd': '#fef9c3'}}}%%
erDiagram
    YIELDS {
        int     id          PK
        string  state
        string  county
        string  crop
        int     year
        float   value
        string  unit
    }

    WEATHER {
        int     id          PK
        string  state
        string  county
        int     year
        int     month
        float   avg_temp
        float   precipitation
    }

    SOIL {
        int     id          PK
        string  state
        string  county
        float   ph
        float   organic_matter
        float   sand_pct
        float   silt_pct
        float   clay_pct
        float   cec
        float   water_capacity
    }

    DAILY_WEATHER {
        int     id          PK
        string  state
        string  county
        int     year
        int     month
        int     day
        float   tmax
        float   tmin
        float   precip
        float   srad
        float   vp
        float   wind
    }

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

    YIELDS ||--o{ MODEL_RUNS : "trained on"
    WEATHER ||--o{ MODEL_RUNS : "trained on"
    SOIL ||--o{ MODEL_RUNS : "trained on"
    DAILY_WEATHER ||--o{ MODEL_RUNS : "trained on"
```

---

## 4. Datasource Registry — Adding a New Data Source

Step-by-step process to register a new datasource so it appears automatically in the Explorer and Ingest pages.

```mermaid
flowchart TD
    A[Create ingest module\nbackend/app/ingest/my_source.py] --> B[Implement fetch_and_transform\nReturns pandas DataFrame]
    B --> C[Implement save_to_db\nUpserts rows via SQLAlchemy]
    C --> D[Add SQLModel table\nbackend/app/models.py]
    D --> E[Create Alembic migration\nalembic revision --autogenerate]
    E --> F[Add FastAPI router\nbackend/app/api/routes/my_source.py]
    F --> G[Register with DatasourceRegistry\nDATASOURCE_REGISTRY.register in registry.py]
    G --> H[Include router in main.py]
    H --> I[Frontend auto-detects\nExplore tabs and Ingest scope\ndriven by /api/v1/datasources/]

    classDef ingest fill:#0d9488,color:#fff,stroke:#0f766e
    classDef db fill:#d97706,color:#fff,stroke:#b45309
    classDef api fill:#6366f1,color:#fff,stroke:#4338ca
    classDef frontend fill:#3b82f6,color:#fff,stroke:#1d4ed8

    class A,B,C ingest
    class D,E db
    class F,G,H api
    class I frontend
```

### Registry Entry Fields

| Field | Purpose |
|-------|---------|
| `key` | Unique identifier (e.g. `"yields"`) |
| `label` | Human-readable name shown in tabs |
| `endpoint` | API path for fetching data (e.g. `"/api/v1/yields/"`) |
| `columns` | Column definitions `{name, type}` shown in Explorer table headers |
| `scope_params` | Filter inputs rendered in Ingest UI (state, year range, etc.) |
| `description` | Tooltip text shown in Explorer tab |

---

## 5. Model Registry — Adding a New Model Type

```mermaid
flowchart TD
    A[Choose model kind:\nsklearn / pytorch / simulation] --> B{Kind}

    B -->|sklearn| C[Add entry to MODEL_REGISTRY dict\nin backend/app/api/routes/models.py]
    B -->|pytorch| D[Implement train_lstm in\nbackend/app/ingest/lstm_trainer.py]
    B -->|simulation| E[Implement runner in\nbackend/app/ingest/my_simulator.py]

    C --> F[Add elif branch in /train endpoint\nfit model, compute metrics]
    D --> F
    E --> F

    F --> G{supports_predict?}
    G -->|Yes| H[joblib.dump artifact\nInsert model_runs row]
    G -->|No - simulation| I[Return metrics only\nrun_id = None]

    H --> J[Frontend shows model in\ndropdown and Saved Models tab]
    I --> J

    J --> K[Predict endpoint\nGET /api/v1/models/types auto-includes it]

    classDef decision fill:#f8fafc,color:#1e293b,stroke:#94a3b8
    classDef api fill:#6366f1,color:#fff,stroke:#4338ca
    classDef ml fill:#16a34a,color:#fff,stroke:#15803d
    classDef sim fill:#e11d48,color:#fff,stroke:#be123c
    classDef artifact fill:#475569,color:#fff,stroke:#334155
    classDef frontend fill:#3b82f6,color:#fff,stroke:#1d4ed8

    class B,G decision
    class A,F api
    class C,D ml
    class E sim
    class H,I artifact
    class J,K frontend
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
