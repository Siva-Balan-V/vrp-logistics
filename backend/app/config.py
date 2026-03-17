from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "VRP Logistics Optimizer"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # API Keys
    ORS_API_KEY: str = ""          # OpenRouteService API key
    OSRM_BASE_URL: str = "http://router.project-osrm.org"

    # Routing preference: "osrm" | "ors" | "haversine"
    ROUTING_BACKEND: str = "haversine"

    # Redis (optional caching)
    REDIS_URL: Optional[str] = None

    # VRP solver defaults
    DEFAULT_MAX_VEHICLES: int = 18
    DEFAULT_MAX_ROUTE_DURATION_SECONDS: int = 9000  # 2.5 hours
    DEFAULT_VEHICLE_CAPACITY: int = 50
    SOLVER_TIME_LIMIT_SECONDS: int = 60

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000", "*"]

    # Batch processing
    OSRM_BATCH_SIZE: int = 100   # Max locations per OSRM request
    ORS_BATCH_SIZE: int = 50

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
