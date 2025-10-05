from fastapi import FastAPI

from backend.weather import router as weather_router
from backend.yields import router as yields_router
from backend.soil import router as soil_router

app = FastAPI()


# Register routers
app.include_router(yields_router)
app.include_router(weather_router)
app.include_router(soil_router)
