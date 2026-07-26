"""Tests for Priority-Based Scheduling."""

import pytest

from app.models.schemas import Location, OptimizeRequest
from app.optimization.vrp_solver import VRPInput, solve_vrp
import numpy as np


class TestLocationPriority:
    def test_default_priority(self):
        loc = Location(id=1, lat=51.5, lon=-0.1, demand=1)
        assert loc.priority == 1

    def test_priority_range(self):
        for p in range(1, 6):
            loc = Location(id=1, lat=51.5, lon=-0.1, demand=1, priority=p)
            assert loc.priority == p

    def test_priority_too_low(self):
        with pytest.raises(ValueError):
            Location(id=1, lat=51.5, lon=-0.1, demand=1, priority=0)

    def test_priority_too_high(self):
        with pytest.raises(ValueError):
            Location(id=1, lat=51.5, lon=-0.1, demand=1, priority=6)


class TestSolverPriority:
    def _make_matrix(self, n):
        dist = np.random.rand(n, n) * 10
        dist = (dist + dist.T) / 2
        np.fill_diagonal(dist, 0)
        return dist, dist * 120

    def test_solver_with_priorities(self):
        n = 6  # 1 depot + 5 deliveries
        dist, dur = self._make_matrix(n)
        inp = VRPInput(
            num_vehicles=2, vehicle_capacity=50,
            max_route_duration_seconds=9000,
            distance_matrix=dist, duration_matrix=dur,
            demands=[0, 1, 1, 1, 1, 1],
            location_ids=[0, 1, 2, 3, 4, 5],
            priorities=[1, 5, 3, 2, 4, 1],
            solver_time_limit_seconds=10,
        )
        output = solve_vrp(inp)
        assert output.solver_time_seconds > 0
        assert len(output.routes) >= 1

    def test_solver_without_priorities(self):
        n = 5
        dist, dur = self._make_matrix(n)
        inp = VRPInput(
            num_vehicles=2, vehicle_capacity=50,
            max_route_duration_seconds=9000,
            distance_matrix=dist, duration_matrix=dur,
            demands=[0, 1, 1, 1, 1],
            location_ids=[0, 1, 2, 3, 4],
            priorities=None,
            solver_time_limit_seconds=10,
        )
        output = solve_vrp(inp)
        assert output.solver_time_seconds > 0
