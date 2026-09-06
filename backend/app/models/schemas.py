from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ─────────────────────────────────────────────
# INPUT SCHEMAS
# ─────────────────────────────────────────────


class Location(BaseModel):
    id: int = Field(..., description="Unique location ID")
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lon: float = Field(..., ge=-180, le=180, description="Longitude")
    demand: int = Field(default=1, ge=0, description="Package demand at this location")
    label: str | None = Field(default=None, description="Human-readable name")
    priority: int = Field(default=1, ge=1, le=5, description="Priority (1=low, 5=high)")
    time_window_start: int | None = Field(default=None, ge=0, description="Earliest arrival (seconds from route start)")
    time_window_end: int | None = Field(default=None, ge=0, description="Latest arrival (seconds from route start)")

    @field_validator("lat")
    @classmethod
    def lat_precision(cls, v: float) -> float:
        return round(v, 6)

    @field_validator("lon")
    @classmethod
    def lon_precision(cls, v: float) -> float:
        return round(v, 6)

    @model_validator(mode="after")
    def time_window_valid(self) -> "Location":
        if self.time_window_start is not None and self.time_window_end is not None:
            if self.time_window_start > self.time_window_end:
                raise ValueError("time_window_start must be <= time_window_end")
        return self


class VehicleSpec(BaseModel):
    count: int = Field(default=18, ge=1, le=100, description="Number of vehicles")
    capacity: int = Field(default=50, ge=1, description="Max packages per vehicle")
    max_route_duration_seconds: int = Field(default=9000, ge=1, description="Max seconds per route (2.5 h = 9000 s)")
    speed_kmh: float = Field(default=30.0, gt=0, description="Average vehicle speed (used for time estimation)")
    solver_time_limit_seconds: int | None = Field(
        default=None, ge=1, le=600, description="Solver timeout in seconds (overrides server default)"
    )
    solver_algorithm: Literal["gls", "greedy"] | None = Field(
        default=None, description="Solver strategy: gls=guided local search, greedy=first solution only"
    )


class OptimizeRequest(BaseModel):
    job_id: str | None = Field(default=None, description="Optional client job ID")
    depots: list[Location] = Field(default=[], description="Depot locations (at least one required)")
    deliveries: list[Location] = Field(..., min_length=1, max_length=1000, description="Delivery stop locations")
    vehicles: VehicleSpec = Field(default_factory=VehicleSpec)
    routing_backend: Literal["haversine", "osrm", "ors"] | None = Field(
        default=None, description="Override routing backend: osrm | ors | haversine"
    )
    traffic: bool = Field(default=False, description="Use real-time traffic data (ORS only; requires ORS_API_KEY)")

    @model_validator(mode="before")
    @classmethod
    def handle_depot_alias(cls, data: Any) -> Any:
        """Support old-style 'depot' field for backward compatibility."""
        if isinstance(data, dict):
            if "depot" in data and "depots" not in data:
                data["depots"] = [data.pop("depot")]
            elif "depot" in data and "depots" in data:
                data.pop("depot")
        return data

    @model_validator(mode="after")
    def validate_request(self) -> "OptimizeRequest":
        if not self.depots:
            raise ValueError("At least one depot is required")
        depot_ids = [d.id for d in self.depots]
        if len(depot_ids) != len(set(depot_ids)):
            raise ValueError("Depot IDs must be unique")
        delivery_ids = [d.id for d in self.deliveries]
        if len(delivery_ids) != len(set(delivery_ids)):
            raise ValueError("Delivery location IDs must be unique")
        overlap = set(depot_ids) & set(delivery_ids)
        if overlap:
            raise ValueError(f"Depot IDs {overlap} conflict with delivery IDs")
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "depots": [{"id": 0, "lat": 51.5074, "lon": -0.1278, "demand": 0, "label": "London Depot"}],
                "deliveries": [
                    {"id": 1, "lat": 51.515, "lon": -0.072, "demand": 2, "label": "Stop A"},
                    {"id": 2, "lat": 51.508, "lon": -0.094, "demand": 1, "label": "Stop B"},
                ],
                "vehicles": {"count": 18, "capacity": 50, "max_route_duration_seconds": 9000},
            }
        }
    }


# ─────────────────────────────────────────────
# OUTPUT SCHEMAS
# ─────────────────────────────────────────────


class VehicleRoute(BaseModel):
    vehicle_id: int
    route: list[int] = Field(..., description="Ordered list of location IDs (starts & ends at depot)")
    route_labels: list[str | None] = Field(default_factory=list)
    distance_km: float
    time_minutes: float
    packages_delivered: int
    waypoints: list[dict] = Field(
        default_factory=list,
        description="[{lat, lon, id, status}] for mapping — status is pending|en_route|arrived|delivered",
    )
    arrival_times: list[int] = Field(default_factory=list, description="Scheduled arrival time (seconds) at each stop")


class OptimizeResponse(BaseModel):
    job_id: str
    status: str = "success"
    solver_time_seconds: float
    total_locations: int
    assigned_count: int
    unassigned_count: int
    vehicles_used: int
    total_distance_km: float
    total_time_minutes: float
    vehicles: list[VehicleRoute]
    unassigned: list[int] = Field(default_factory=list, description="IDs of unserved locations")
    unassigned_labels: list[str | None] = Field(default_factory=list)
    matrix_source: str = Field(description="Distance matrix source used")
    fuel_cost: float = Field(default=0.0, description="Estimated fuel cost ($)")
    driver_cost: float = Field(default=0.0, description="Estimated driver cost ($)")
    total_cost: float = Field(default=0.0, description="Total estimated cost ($)")


class DirectionStep(BaseModel):
    instruction: str = Field(..., description="Human-readable maneuver text")
    distance_m: float = Field(default=0.0, description="Distance covered by this step (meters)")
    duration_s: float = Field(default=0.0, description="Duration of this step (seconds)")
    lon: float = Field(..., ge=-180, le=180, description="Longitude at the maneuver point")
    lat: float = Field(..., ge=-90, le=90, description="Latitude at the maneuver point")
    maneuver: str | int | None = Field(default=None, description="Raw maneuver code/type from the router")


class DirectionsResponse(BaseModel):
    job_id: str
    route_index: int
    source: str = Field(description="Directions source used (osrm | ors | haversine)")
    steps: list[DirectionStep] = Field(default_factory=list)
    geometry: list[list[float]] = Field(
        default_factory=list, description="[[lon, lat], ...] flattened polyline across all legs"
    )


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    routing_backend: str
    redis_connected: bool = False


# ── Auth Schemas ──────────────────────────────


class UserRegister(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    company_name: str | None = Field(default=None, max_length=200)


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    company_id: str
    company_name: str
    is_active: bool
    created_at: str


# ── API Key Schemas ───────────────────────────


API_KEY_PERMISSIONS = ("optimize", "read")


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable key label")
    permissions: list[str] = Field(
        default_factory=lambda: ["optimize", "read"],
        description="Allowed permissions: optimize | read",
    )
    expires_at: datetime | None = Field(default=None, description="Optional expiry (ISO 8601)")

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: list[str]) -> list[str]:
        unknown = set(v) - set(API_KEY_PERMISSIONS)
        if unknown:
            raise ValueError(f"Invalid permissions: {sorted(unknown)}. Allowed: {list(API_KEY_PERMISSIONS)}")
        if not v:
            raise ValueError("At least one permission is required")
        return v


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    permissions: list[str]
    is_active: bool
    expires_at: str | None = None
    last_used_at: str | None = None
    created_at: str | None = None


class ApiKeyCreatedResponse(ApiKeyResponse):
    key: str = Field(..., description="Plaintext API key — shown once, store it safely")


# ── Driver Schemas ────────────────────────────


class DriverCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=5, max_length=20)


class DriverLocationUpdate(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


StopStatus = Literal["pending", "en_route", "arrived", "delivered"]


class StopStatusUpdate(BaseModel):
    status: StopStatus = Field(..., description="New stop status (pending → en_route → arrived → delivered)")


class DriverAssignment(BaseModel):
    job_id: str
    vehicle_id: int


class DriverResponse(BaseModel):
    id: str
    name: str
    phone: str
    status: str
    current_lat: float | None = None
    current_lon: float | None = None
    last_ping_at: str | None = None
    created_at: str | None = None
    assigned_route: dict | None = Field(default=None, description="Today's assigned vehicle route if any")

    model_config = {"from_attributes": True}


# ── Notification Schemas ───────────────────────


class NotificationConfigUpdate(BaseModel):
    sms_enabled: bool | None = None
    email_enabled: bool | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    triggers: list[str] | None = None


class NotificationConfigResponse(BaseModel):
    id: int
    sms_enabled: bool
    email_enabled: bool
    twilio_account_sid: str | None = None
    twilio_from_number: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_from_email: str | None = None
    triggers: list[str] = []
    created_at: str | None = None
    updated_at: str | None = None

    model_config = {"from_attributes": True}


class TriggerNotificationRequest(BaseModel):
    driver_id: str
    trigger: str = Field(..., pattern="^(out_for_delivery|arrived|delayed)$")
    customer_phone: str | None = None
    customer_email: str | None = None


class NotificationLogResponse(BaseModel):
    id: int
    channel: str
    recipient: str
    trigger: str
    message: str
    status: str
    error: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


# ── Billing Schemas ────────────────────────────


class PlanInfo(BaseModel):
    id: str
    name: str
    price_monthly: int
    max_optimizations_per_month: int
    max_locations_per_job: int
    allowed_backends: list[str]
    export_enabled: bool
    priority_support: bool
    max_users: int


class UsageInfo(BaseModel):
    plan: str
    monthly_optimizations_used: int
    monthly_optimizations_limit: int
    max_locations_per_job: int
    allowed_backends: list[str]
    export_enabled: bool
    max_users: int
    users_count: int | None = None
