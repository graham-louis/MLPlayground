import streamlit as st
from sqlalchemy import create_engine, text
import os

st.title("Database Connection Test")

# Use DATABASE_URL from environment or fallback to SQLite
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///mlplayground.db")
engine = create_engine(DATABASE_URL)

try:
    with engine.begin() as conn:
        # Try to list tables
        tables = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")).fetchall()
        st.success(f"Connected! Tables: {[t[0] for t in tables]}")
        # Try to insert and select from yields
        conn.execute(text("INSERT INTO yields (year, state, district, county, county_ansi, crop, value, unit) VALUES (2025, 'NC', 'Test District', 'Test County', '12345', 'CORN', 100.0, 'bushels') ON CONFLICT DO NOTHING;"))
        result = conn.execute(text("SELECT * FROM yields ORDER BY id DESC LIMIT 1;")).fetchone()
        # Use _mapping for SQLAlchemy 1.4+ Row to dict conversion
        st.write("Sample row from 'yields':", dict(result._mapping) if result else "No data")
except Exception as e:
    st.error(f"Database error: {e}")
