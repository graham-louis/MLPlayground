from fastapi import APIRouter

from app.api.routes import daily_weather, datasources, ingest, training, soil, utils, weather, yields, weather_psa
import app.ingest.weather_psa  # noqa: F401 — registers PSA datasource in DATASOURCE_REGISTRY at startup

api_router = APIRouter()
api_router.include_router(yields.router)
api_router.include_router(weather.router)
api_router.include_router(soil.router)
api_router.include_router(daily_weather.router)
api_router.include_router(ingest.router)
api_router.include_router(training.router)
api_router.include_router(utils.router)
api_router.include_router(datasources.router)
api_router.include_router(weather_psa.router)
