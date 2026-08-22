"""Tests for PostgreSQL job persistence (job_store.persist_job)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.schemas import Location, OptimizeRequest, OptimizeResponse, VehicleRoute, VehicleSpec
from app.services.job_store import persist_job

_COMPANY_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
_JOB_ID = uuid.UUID("00000000-0000-0000-0000-00000000000a")


def _make_response() -> OptimizeResponse:
    return OptimizeResponse(
        job_id=str(_JOB_ID),
        status="success",
        solver_time_seconds=0.123,
        total_locations=2,
        assigned_count=1,
        unassigned_count=0,
        vehicles_used=1,
        total_distance_km=45.0,
        total_time_minutes=90.0,
        vehicles=[
            VehicleRoute(
                vehicle_id=1,
                route=[0, 1, 0],
                route_labels=["Depot", "Stop 1", "Depot"],
                distance_km=45.0,
                time_minutes=90.0,
                packages_delivered=1,
            ),
        ],
        unassigned=[],
        unassigned_labels=[],
        matrix_source="haversine",
    )


def _make_request() -> OptimizeRequest:
    return OptimizeRequest(
        depots=[
            Location(id=0, lat=51.5074, lon=-0.1278, demand=0, label="Depot"),
            Location(id=9, lat=51.5, lon=-0.1, demand=0, label="Depot 2"),
        ],
        deliveries=[Location(id=1, lat=51.51, lon=-0.12, demand=1, label="Stop 1")],
        vehicles=VehicleSpec(count=1, capacity=50),
        routing_backend="haversine",
    )


class TestPersistJob:
    @pytest.fixture
    def db(self):
        db = AsyncMock()
        db.add = MagicMock()
        return db

    async def test_uses_depots_list_not_single_depot(self, db):
        await persist_job(db, _COMPANY_ID, _make_request(), _make_response())
        assert db.add.call_count == 1 + 1 + 1 + 2  # job + route + delivery + 2 depots
        added = [call.args[0] for call in db.add.call_args_list]
        depots = [obj for obj in added if getattr(obj, "is_depot", False)]
        assert len(depots) == 2
        assert [d.location_id for d in depots] == [0, 9]

    async def test_flushes_job_before_adding_children(self, db):
        await persist_job(db, _COMPANY_ID, _make_request(), _make_response())
        # job must be flushed before the final flush of children
        assert db.flush.await_count == 2
        first_flush = db.flush.await_args_list[0]
        assert first_flush is not None

    async def test_persists_job_row(self, db):
        await persist_job(db, _COMPANY_ID, _make_request(), _make_response())
        job = db.add.call_args_list[0].args[0]
        assert job.job_id == _JOB_ID
        assert job.company_id == _COMPANY_ID
        assert job.routing_backend == "haversine"
        assert job.assigned_count == 1
