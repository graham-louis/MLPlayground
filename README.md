# MLPlayground

A Streamlit-based AutoML playground for data ingestion, profiling, and quick model comparison using PyCaret.

## Features
- Upload and profile datasets
- Compare machine learning models (classification/regression)
- Integrate external data (USDA NASS, SSURGO, weather)
- Persist and share data and models
- Scalable architecture with database-backed storage

## Quick Start

### Local (with Docker Compose)
```sh
docker-compose up --build
```
Visit [http://localhost:8501](http://localhost:8501) in your browser.

### Database Migrations
After first startup, run migrations inside the app container:
```sh
docker-compose exec app alembic upgrade head
```

## Project Structure

```
MLPlayground/
├── db/
│   ├── models.py
│   ├── init_db.py
│   ├── migrate.py
│   └── migrations/
│       ├── env.py
│       ├── script.py.mako
│       └── versions/
├── src/
│   ├── AutoML.py
│   ├── pages/
│   └── utils/
├── requirements.txt
├── Dockerfile
├── compose.yaml
└── ...
```

## Database Directory (`db/`)

The `db/` directory contains all code and configuration for database integration and migrations:

- **`models.py`**: SQLAlchemy ORM models for all tables (e.g., `Yield`, `Weather`, `Soil`).
  ```python
  from sqlalchemy import Column, Integer, String, Float
  from sqlalchemy.ext.declarative import declarative_base
  Base = declarative_base()

  class Yield(Base):
      __tablename__ = 'yields'
      id = Column(Integer, primary_key=True)
      county = Column(String)
      # ... other columns ...
  ```
- **`init_db.py`**: Script to create all tables directly from models (for dev/testing).
  ```python
  from db.models import Base
  from sqlalchemy import create_engine
  engine = create_engine("sqlite:///mlplayground.db")
  Base.metadata.create_all(engine)
  ```
- **`migrate.py`**: Script to run Alembic migrations programmatically.
  ```python
  from alembic import command, config
  alembic_cfg = config.Config("alembic.ini")
  command.upgrade(alembic_cfg, 'head')
  ```
- **`migrations/`**: Alembic migration environment.
  - `env.py`: Migration config, loads models and sets up DB connection.
  - `script.py.mako`: Template for new migration scripts.
  - `versions/`: Auto-generated migration scripts (one per schema change).

## Example: Adding a New Table
1. Edit `db/models.py` to add a new model.
2. Run inside the app container:
   ```sh
   alembic revision --autogenerate -m "Add new table"
   alembic upgrade head
   ```

## Troubleshooting
- If tables are missing, ensure migrations are generated and applied.
- To reset the database, remove the Docker volume:
  ```sh
  docker-compose down
  docker volume rm mlplayground_pgdata
  docker-compose up --build
  ```

---

For more details, see the code comments in each file or ask for help!
