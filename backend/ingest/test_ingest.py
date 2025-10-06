import pytest
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.ingest.ssurgo import fetch_and_transform_soil
from backend.ingest.nldas import fetch_and_transform_weather
from backend.ingest.nass import fetch_and_transform_yield
from backend.ingest.runner import upsert_soil_to_db, upsert_weather_to_db, upsert_yield_to_db
import sys
import os

# Patch sys.path for db.models import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from db.models import Base, Soil, Weather, Yield

@pytest.fixture(scope="function")
def in_memory_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

def test_soil_fetch_and_upsert(in_memory_engine):
    df = fetch_and_transform_soil("Story", "Iowa")
    assert not df.empty
    upsert_soil_to_db(df, in_memory_engine)
    Session = sessionmaker(bind=in_memory_engine)
    with Session() as session:
        result = session.query(Soil).filter_by(county="Story", state="Iowa").first()
        assert result is not None
        assert result.ph is not None

def test_weather_fetch_and_upsert(monkeypatch, in_memory_engine):
    # Mock requests.get to return a small CSV for weather
    import io
    import requests
    class MockResponse:
        def __init__(self, text, status_code=200):
            self.text = text
            self.status_code = status_code
    def mock_get(url, params=None, **kwargs):
        csv = "date,max_air_temperature,min_air_temperature,avg_air_temperature,precipitation\n2020-05-01,25,10,17.5,2\n2020-06-01,30,15,22.5,5"
        return MockResponse(csv)
    monkeypatch.setattr(requests, "get", mock_get)
    annual_df = fetch_and_transform_weather("Story", "Iowa", 2020, 2020)
    assert not annual_df.empty
    upsert_weather_to_db(annual_df, in_memory_engine)
    Session = sessionmaker(bind=in_memory_engine)
    with Session() as session:
        result = session.query(Weather).filter_by(county="Story", state="Iowa", year=2020).first()
        assert result is not None
        assert result.avg_temp is not None

def test_yield_fetch_and_upsert(monkeypatch, in_memory_engine):
    # Mock requests.get to return a small JSON for yield
    import requests
    class MockResponse:
        def __init__(self, json_data, status_code=200):
            self._json = json_data
            self.status_code = status_code
        def json(self):
            return self._json
        @property
        def text(self):
            return str(self._json)
    def mock_get(url, params=None, **kwargs):
        data = [{"year": "2020", "Value": "200"}]
        return MockResponse({"data": data})
    monkeypatch.setattr(requests, "get", mock_get)
    df = fetch_and_transform_yield("dummy_key", "Story", "Iowa", 2020, 2020)
    assert not df.empty
    upsert_yield_to_db(df, in_memory_engine)
    Session = sessionmaker(bind=in_memory_engine)
    with Session() as session:
        result = session.query(Yield).filter_by(county="Story", state="Iowa", year=2020).first()
        assert result is not None
        assert result.value == 200
