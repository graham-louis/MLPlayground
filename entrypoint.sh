#!/bin/bash
set -e

# Wait for DB to be ready (Postgres)
until pg_isready -h db -U mluser; do
  echo "Waiting for database..."
  sleep 2
done

# Check if the 'yields' table exists in the target DB
if ! PGPASSWORD=mlpass psql -h db -U mluser -d mlplayground -c '\dt yields' | grep yields; then
  echo "Initializing DB and ingesting data..."
  PYTHONPATH=. python db/init_db.py
  PYTHONPATH=. python backend/ingest/runner.py
else
  echo "DB already initialized, skipping init/ingest."
fi

# Start Streamlit (default CMD)
exec streamlit run src/AutoML.py --server.runOnSave false
