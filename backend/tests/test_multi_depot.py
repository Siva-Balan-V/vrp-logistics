"""Tests for Multi-Depot Support."""

import pytest

from app.models.schemas import Location, OptimizeRequest, VehicleSpec
from app.optimization.vrp_solver import VRPInput, solve_vrp
import numpy as np


class TestSchemaMultiDepot:
    def test_single_depot_backward_compat(self):
        """Old-style 'depot' field should be converted to 'depots' list."""
        req = OptimizeRequest(
            depot=Location(id=0, lat=51.5, lon=-0.1, demand=0),
            deliveries=[Location(id=1, lat=51.51, lon=-0.07, demand=1)],
        )
        assert len(req.depots) == 1
        assert req.depots[0].id == 0

    def test_multiple_depots(self):
        req = OptimizeRequest(
            depots=[
                Location(id=0, lat=51.5, lon=-0.1, demand=0),
                Location(id=10, lat=51.52, lon=-0.08, demand=0),
            ],
            deliveries=[Location(id=1, lat=51.51, lon=-0.07, demand=1)],
        )
        assert len(req.depots) == 2

    def test_depot_id_conflict_with_delivery(self):
        with pytest.raises(ValueError, match="conflict"):
            OptimizeRequest(
                depots=[Location(id=0, lat=51.5, lon=-0.1, demand=0)],
                deliveries=[Location(id=0, lat=51.51, lon=-0.07, demand=1)],
            )

    def test_duplicate_depot_ids(self):
        with pytest.raises(ValueError, match="unique"):
            OptimizeRequest(
                depots=[
                    Location(id=0, lat=51.5, lon=-0.1, demand=0),
                    Location(id=0, lat=51.52, lon=-0.08, demand=0),
                ],
                deliveries=[Location(id=1, lat=51.51, lon=-0.07, demand=1)],
            )

    def test_no_depots_fails(self):
        with pytest.raises(ValueError, match="depot"):
            OptimizeRequest(
                depots=[],
                deliveries=[Location(id=1, lat=51.51, lon=-0.07, demand=1)],
            )


class TestSolverMultiDepot:
    def _make_matrix(self, n):
        dist = np.random.rand(n, n) * 10
        dist = (dist + dist.T) / 2
        np.fill_diagonal(dist, 0)
        return dist, dist * 120  # dur = dist * 120 seconds

    def test_single_depot_solver(self):
        n = 5  # 1 depot + 4 deliveries
        dist, dur = self._make_matrix(n)
        inp = VRPInput(
            num_vehicles=3, vehicle_capacity=50,
            max_route_duration_seconds=9000,
            distance_matrix=dist, duration_matrix=dur,
            demands=[0, 1, 2, 1, 3],
            location_ids=[0, 1, 2, 3, 4],
            num_depots=1, solver_time_limit_seconds=10,
        )
        output = solve_vrp(inp)
        assert output.solver_time_seconds > 0

    def test_multi_depot_solver(self):
        n = 6  # 2 depots + 4 deliveries
        dist, dur = self._make_matrix(n)
        inp = VRPInput(
            num_vehicles=4, vehicle_capacity=50,
            max_route_duration_seconds=9000,
            distance_matrix=dist, duration_matrix=dur,
            demands=[0, 0, 1, 2, 1, 3],
            location_ids=[0, 10, 1, 2, 3, 4],
            num_depots=2, solver_time_limit_seconds=10,
        )
        output = solve_vrp(inp)
        assert output.solver_time_seconds > 0
        assert len(output.routes) >= 1

    def test_multi_depot_routes_start_at_depots(self):
        n = 5  # 2 depots + 3 deliveries
        dist, dur = self._make_matrix(n)
        inp = VRPInput(
            num_vehicles=3, vehicle_capacity=50,
            max_route_duration_seconds=9000,
            distance_matrix=dist, duration_matrix=dur,
            demands=[0, 0, 1, 2, 1],
            location_ids=[0, 10, 1, 2, 3],
            num_depots=2, solver_time_limit_seconds=10,
        )
        output = solve_vrp(inp)
        depot_ids = {0, 10}
        for route in output.routes:
            # Route should start and end at a depot
            assert route.location_ids[0] in depot_ids
            assert route.location_ids[-1] in depot_ids
