from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Yield(Base):
    __tablename__ = 'yields'
    id = Column(Integer, primary_key=True)
    # Basic columns
    year = Column(Integer, nullable=False)
    # Spatial columns first
    state = Column(String, nullable=False)
    district = Column(String, nullable=True)     # Agricultural district
    county = Column(String, nullable=False)
    county_ansi = Column(String, nullable=True)  # County ANSI code
    # Crop columns
    crop = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=True)         # Unit of yield measurement

    # Additional models (Weather, Soil, etc.) can be added incrementally.

class Weather(Base):
    __tablename__ = 'weather'
    id = Column(Integer, primary_key=True)
    # Spatial columns
    county = Column(String, nullable=False)
    county_ansi = Column(String, nullable=True)
    state = Column(String, nullable=False)
    district = Column(String, nullable=True)
    # Other columns
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=True)
    day = Column(Integer, nullable=True)
    avg_temp = Column(Float, nullable=True)
    precipitation = Column(Float, nullable=True)
    min_temp = Column(Float, nullable=True)
    max_temp = Column(Float, nullable=True)
    # Add more weather metrics as needed

class Soil(Base):
    __tablename__ = 'soil'
    id = Column(Integer, primary_key=True)
    # Spatial columns
    county = Column(String, nullable=False)
    county_ansi = Column(String, nullable=True)
    state = Column(String, nullable=False)
    district = Column(String, nullable=True)
    # Other columns
    ph = Column(Float, nullable=True)
    organic_matter = Column(Float, nullable=True)
    sand_pct = Column(Float, nullable=True)
    silt_pct = Column(Float, nullable=True)
    clay_pct = Column(Float, nullable=True)
    # Add more soil properties as needed