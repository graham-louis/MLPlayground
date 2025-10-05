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
        # Insert sample Yield row
        conn.execute(text("""
            INSERT INTO yields (year, state, district, county, county_ansi, crop, value, unit)
            VALUES (2025, 'NC', 'Test District', 'Test County', '12345', 'CORN', 100.0, 'bushels')
            ON CONFLICT DO NOTHING;
        """))
        result = conn.execute(text("SELECT * FROM yields ORDER BY id DESC LIMIT 1;")).fetchone()
        st.write("Sample row from 'yields':", dict(result._mapping) if result else "No data")

        # Insert sample Weather row (match schema)
        conn.execute(text("""
            INSERT INTO weather (state, county, year, month, day, min_temp, max_temp, avg_temp, precipitation, district, county_ansi)
            VALUES ('NC', 'Test County', 2025, 1, 1, 15.0, 30.0, 22.5, 2.5, 'Test District', '12345')
            ON CONFLICT DO NOTHING;
        """))
        wresult = conn.execute(text("SELECT * FROM weather ORDER BY id DESC LIMIT 1;")).fetchone()
        st.write("Sample row from 'weather':", dict(wresult._mapping) if wresult else "No data")

        # Insert sample Soil row (match schema)
        conn.execute(text("""
            INSERT INTO soil (state, county, ph, sand_pct, silt_pct, clay_pct, organic_matter, district, county_ansi)
            VALUES ('NC', 'Test County', 6.5, 40.0, 40.0, 20.0, 3.2, 'Test District', '12345')
            ON CONFLICT DO NOTHING;
        """))
        sresult = conn.execute(text("SELECT * FROM soil ORDER BY id DESC LIMIT 1;")).fetchone()
        st.write("Sample row from 'soil':", dict(sresult._mapping) if sresult else "No data")
except Exception as e:
    st.error(f"Database error: {e}")
