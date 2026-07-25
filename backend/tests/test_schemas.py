"""Tests for Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.models.schemas import Location, OptimizeRequest, VehicleSpec


def test_location_lat_precision():
    """Latitude should be rounded to 6 decimal places."""
    loc = Location(id=1, lat=51.5074123456, lon=-0.1278, demand=1)
    assert loc.lat == round(51.5074123456, 6)


def test_location_lon_precision():
    """Longitude should be rounded to 6 decimal places."""
    loc = Location(id=1, lat=51.5074, lon=-0.1278123456, demand=1)
    assert loc.lon == round(-0.1278123456, 6)


def test_location_lat_bounds():
    """Latitude must be between -90 and 90."""
    with pytest.raises(ValidationError):
        Location(id=1, lat=91, lon=0, demand=1)
    with pytest.raises(ValidationError):
        Location(id=1, lat=-91, lon=0, demand=1)


def test_location_lon_bounds():
    """Longitude must be between -180 and 180."""
    with pytest.raises(ValidationError):
        Location(id=1, lat=0, lon=181, demand=1)
    with pytest.raises(ValidationError):
        Location(id=1, lat=0, lon=-181, demand=1)


def test_location_demand_non_negative():
    """Demand must be >= 0."""
    with pytest.raises(ValidationError):
        Location(id=1, lat=0, lon=0, demand=-1)


def test_optimize_request_unique_ids():
    """Delivery IDs must be unique."""
    depot = Location(id=0, lat=51.5074, lon=-0.1278, demand=0)
    deliveries = [
        Location(id=1, lat=51.51, lon=-0.07, demand=1),
        Location(id=1, lat=51.52, lon=-0.08, demand=1),
    ]
    with pytest.raises(ValidationError, match="unique"):
        OptimizeRequest(depot=depot, deliveries=deliveries)


def test_optimize_request_depot_delivery_id_conflict():
    """Depot ID must not conflict with delivery IDs."""
    depot = Location(id=1, lat=51.5074, lon=-0.1278, demand=0)
    deliveries = [Location(id=1, lat=51.51, lon=-0.07, demand=1)]
    with pytest.raises(ValidationError, match="conflict"):
        OptimizeRequest(depot=depot, deliveries=deliveries)


def test_optimize_request_valid():
    """Valid request should pass validation."""
    depot = Location(id=0, lat=51.5074, lon=-0.1278, demand=0)
    deliveries = [
        Location(id=1, lat=51.51, lon=-0.07, demand=1),
        Location(id=2, lat=51.52, lon=-0.08, demand=2),
    ]
    req = OptimizeRequest(depot=depot, deliveries=deliveries)
    assert len(req.deliveries) == 2


def test_vehicle_spec_defaults():
    """VehicleSpec should have sensible defaults."""
    vs = VehicleSpec()
    assert vs.count == 18
    assert vs.capacity == 50
    assert vs.max_route_duration_seconds == 9000
    assert vs.speed_kmh == 30.0


def test_vehicle_spec_validation():
    """VehicleSpec count must be between 1 and 100."""
    with pytest.raises(ValidationError):
        VehicleSpec(count=0)
    with pytest.raises(ValidationError):
        VehicleSpec(count=101)
