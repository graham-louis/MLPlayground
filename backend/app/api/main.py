from fastapi import APIRouter

from app.api.routes import daily_weather, ingest, models, soil, utils, weather, yields

api_router = APIRouter()
api_router.include_router(yields.router)
api_router.include_router(weather.router)
api_router.include_router(soil.router)
api_router.include_router(daily_weather.router)
api_router.include_router(ingest.router)
api_router.include_router(models.router)
api_router.include_router(utils.router)
