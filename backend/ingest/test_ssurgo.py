import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from db.models import Soil
from backend.ingest.ssurgo import fetch_and_transform_soil
from backend.ingest.runner import upsert_soil_to_db

def test_soil_ingest():
    # Use a test DB (sqlite in-memory for speed)
    engine = create_engine('sqlite:///:memory:')
    from db.models import Base
    Base.metadata.create_all(engine)
    # Use a real county/state for a live test, or mock fetch_and_transform_soil for CI
    df = fetch_and_transform_soil('Wake', 'North Carolina')
    if df is not None and not df.empty:
        upsert_soil_to_db(df, engine)
        with Session(engine) as session:
            result = session.query(Soil).filter_by(county='Wake').first()
            assert result is not None
            assert result.ph is not None
            assert result.sand_pct is not None
            print("Test passed: Soil upsert and fetch.")
    else:
        print("Test skipped: No soil data fetched (API/network issue or county not found).")

if __name__ == "__main__":
    test_soil_ingest()
