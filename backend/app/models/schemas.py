from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any, Literal, Optional
import uuid


# ─────────────────────────────────────────────
# INPUT SCHEMAS
# ─────────────────────────────────────────────

class Location(BaseModel):
    id: int = Field(..., description="Unique location ID")
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lon: float = Field(..., ge=-180, le=180, description="Longitude")
    demand: int = Field(default=1, ge=0, description="Package demand at this location")
    label: Optional[str] = Field(default=None, description="Human-readable name")
    priority: int = Field(default=1, ge=1, le=5, description="Priority (1=low, 5=high)")
    time_window_start: Optional[int] = Field(default=None, ge=0, description="Earliest arrival (seconds from route start)")
    time_window_end: Optional[int] = Field(default=None, ge=0, description="Latest arrival (seconds from route start)")

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
    max_route_duration_seconds: int = Field(
        default=9000, ge=1, description="Max seconds per route (2.5 h = 9000 s)"
    )
    speed_kmh: float = Field(
        default=30.0, gt=0, description="Average vehicle speed (used for time estimation)"
    )


class OptimizeRequest(BaseModel):
    job_id: Optional[str] = Field(default=None, description="Optional client job ID")
    depots: list[Location] = Field(default=[], description="Depot locations (at least one required)")
    deliveries: list[Location] = Field(
        ..., min_length=1, max_length=1000, description="Delivery stop locations"
    )
    vehicles: VehicleSpec = Field(default_factory=VehicleSpec)
    routing_backend: Optional[Literal["haversine", "osrm", "ors"]] = Field(
        default=None, description="Override routing backend: osrm | ors | haversine"
    )

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

    model_config = {"json_schema_extra": {
        "example": {
            "depots": [{"id": 0, "lat": 51.5074, "lon": -0.1278, "demand": 0, "label": "London Depot"}],
            "deliveries": [
                {"id": 1, "lat": 51.515, "lon": -0.072, "demand": 2, "label": "Stop A"},
                {"id": 2, "lat": 51.508, "lon": -0.094, "demand": 1, "label": "Stop B"},
            ],
            "vehicles": {"count": 18, "capacity": 50, "max_route_duration_seconds": 9000}
        }
    }}


# ─────────────────────────────────────────────
# OUTPUT SCHEMAS
# ─────────────────────────────────────────────

class VehicleRoute(BaseModel):
    vehicle_id: int
    route: list[int] = Field(..., description="Ordered list of location IDs (starts & ends at depot)")
    route_labels: list[Optional[str]] = Field(default_factory=list)
    distance_km: float
    time_minutes: float
    packages_delivered: int
    waypoints: list[dict] = Field(default_factory=list, description="[{lat, lon, id}] for mapping")
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
    unassigned_labels: list[Optional[str]] = Field(default_factory=list)
    matrix_source: str = Field(description="Distance matrix source used")


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    routing_backend: str
    redis_connected: bool = False


# ── Auth Schemas ──────────────────────────────

class UserRegister(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    company_name: Optional[str] = Field(default=None, max_length=200)


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
