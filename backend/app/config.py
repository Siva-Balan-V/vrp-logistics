from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings

VALID_ROUTING_BACKENDS = ("osrm", "ors", "haversine")


class Settings(BaseSettings):
    # App
    APP_NAME: str = "VRP Logistics Optimizer"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "console"  # "console" | "json"
    LOG_FILE: str | None = None  # Path to log file (rotated) if set

    # API Keys
    ORS_API_KEY: str = ""  # OpenRouteService API key
    OSRM_BASE_URL: str = "http://router.project-osrm.org"

    # Routing preference: "osrm" | "ors" | "haversine"
    ROUTING_BACKEND: str = "haversine"

    # Redis (optional caching)
    REDIS_URL: str | None = None

    # Database (optional — app works without it)
    DATABASE_URL: str | None = None

    # JWT
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # VRP solver defaults
    DEFAULT_MAX_VEHICLES: int = 18
    DEFAULT_MAX_ROUTE_DURATION_SECONDS: int = 9000  # 2.5 hours
    DEFAULT_VEHICLE_CAPACITY: int = 50
    SOLVER_TIME_LIMIT_SECONDS: int = 60

    # Cost estimation defaults
    FUEL_COST_PER_KM: float = 0.35  # $ per km (including maintenance)
    DRIVER_COST_PER_HOUR: float = 25.0  # $ per hour

    # Stripe (legacy — replaced by Razorpay)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_PRO: str = ""
    STRIPE_PRICE_ENTERPRISE: str = ""

    # Razorpay / Billing
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # Notifications
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Rate limiting
    TRUST_PROXY_HEADERS: bool = False  # Honor X-Forwarded-For only when behind a trusted proxy

    # Batch processing
    OSRM_BATCH_SIZE: int = 100  # Max locations per OSRM request
    ORS_BATCH_SIZE: int = 50

    @field_validator("ROUTING_BACKEND")
    @classmethod
    def validate_routing_backend(cls, v: str) -> str:
        if v not in VALID_ROUTING_BACKENDS:
            raise ValueError(f"ROUTING_BACKEND must be one of {VALID_ROUTING_BACKENDS}, got {v!r}")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
