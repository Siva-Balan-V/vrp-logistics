from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
import uuid


# ─────────────────────────────────────────────
# INPUT SCHEMAS
# ─────────────────────────────────────────────

class Location(BaseModel):
    id: int = Field(..., description="Unique location ID (0 = depot)")
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lon: float = Field(..., ge=-180, le=180, description="Longitude")
    demand: int = Field(default=1, ge=0, description="Package demand at this location")
    label: Optional[str] = Field(default=None, description="Human-readable name")

    @field_validator("lat")
    @classmethod
    def lat_precision(cls, v: float) -> float:
        return round(v, 6)

    @field_validator("lon")
    @classmethod
    def lon_precision(cls, v: float) -> float:
        return round(v, 6)


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
    depot: Location = Field(..., description="Starting/ending depot location")
    deliveries: list[Location] = Field(
        ..., min_length=1, max_length=1000, description="Delivery stop locations"
    )
    vehicles: VehicleSpec = Field(default_factory=VehicleSpec)
    routing_backend: Optional[str] = Field(
        default=None, description="Override routing backend: osrm | ors | haversine"
    )

    @model_validator(mode="after")
    def unique_ids(self) -> "OptimizeRequest":
        ids = [d.id for d in self.deliveries]
        if len(ids) != len(set(ids)):
            raise ValueError("Delivery location IDs must be unique")
        if self.depot.id in ids:
            raise ValueError("Depot ID must not conflict with delivery IDs")
        return self

    model_config = {"json_schema_extra": {
        "example": {
            "depot": {"id": 0, "lat": 51.5074, "lon": -0.1278, "demand": 0, "label": "London Depot"},
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
