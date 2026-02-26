from app.ingest.weather_psa import fetch_and_transform, upsert_weather_psa_to_db

# Example parameters
county = "Wake"
state = "North Carolina"
start_year = 2020
end_year = 2020

df = fetch_and_transform(county, state, start_year, end_year)
print(df)

upsert_weather_psa_to_db(df)
