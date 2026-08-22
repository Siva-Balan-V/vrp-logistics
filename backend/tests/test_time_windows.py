"""Tests for Time Windows (VRPTW) feature."""

import numpy as np
import pytest

from app.models.schemas import Location, OptimizeRequest, VehicleSpec
from app.optimization.vrp_solver import VRPInput, solve_vrp


def _make_request_with_time_windows():
    return OptimizeRequest(
        depot=Location(id=0, lat=51.5074, lon=-0.1278, demand=0),
        deliveries=[
            Location(id=1, lat=51.51, lon=-0.07, demand=2, time_window_start=0, time_window_end=3600),
            Location(id=2, lat=51.52, lon=-0.08, demand=1, time_window_start=1800, time_window_end=5400),
            Location(id=3, lat=51.53, lon=-0.09, demand=3, time_window_start=900, time_window_end=4500),
        ],
        vehicles=VehicleSpec(count=5, capacity=50, max_route_duration_seconds=9000, speed_kmh=30),
    )


def _make_request_without_time_windows():
    return OptimizeRequest(
        depot=Location(id=0, lat=51.5074, lon=-0.1278, demand=0),
        deliveries=[
            Location(id=1, lat=51.51, lon=-0.07, demand=2),
            Location(id=2, lat=51.52, lon=-0.08, demand=1),
        ],
        vehicles=VehicleSpec(count=3, capacity=50, max_route_duration_seconds=9000, speed_kmh=30),
    )


class TestLocationSchema:
    def test_time_window_fields_optional(self):
        loc = Location(id=1, lat=51.5, lon=-0.1, demand=1)
        assert loc.time_window_start is None
        assert loc.time_window_end is None

    def test_time_window_fields_set(self):
        loc = Location(id=1, lat=51.5, lon=-0.1, demand=1, time_window_start=100, time_window_end=500)
        assert loc.time_window_start == 100
        assert loc.time_window_end == 500

    def test_time_window_start_greater_than_end_invalid(self):
        with pytest.raises(ValueError, match="time_window_start must be <= time_window_end"):
            Location(id=1, lat=51.5, lon=-0.1, demand=1, time_window_start=500, time_window_end=100)

    def test_time_window_only_start_set(self):
        loc = Location(id=1, lat=51.5, lon=-0.1, demand=1, time_window_start=100)
        assert loc.time_window_start == 100
        assert loc.time_window_end is None


class TestSolverTimeWindows:
    def _make_solver_input(self, time_windows=None):
        dist = np.array(
            [
                [0, 2.0, 3.0, 4.0],
                [2.0, 0, 1.5, 2.5],
                [3.0, 1.5, 0, 1.0],
                [4.0, 2.5, 1.0, 0],
            ]
        )
        dur = dist * 120  # 2 min per km
        return VRPInput(
            num_vehicles=3,
            vehicle_capacity=50,
            max_route_duration_seconds=9000,
            distance_matrix=dist,
            duration_matrix=dur,
            demands=[0, 2, 1, 3],
            location_ids=[0, 1, 2, 3],
            speed_kmh=30,
            solver_time_limit_seconds=10,
            time_windows=time_windows,
        )

    def test_solver_without_time_windows(self):
        inp = self._make_solver_input(time_windows=None)
        output = solve_vrp(inp)
        assert output.solver_time_seconds > 0
        assert len(output.routes) >= 1

    def test_solver_with_time_windows(self):
        time_windows = [(0, 9000), (0, 3600), (1800, 5400), (900, 4500)]
        inp = self._make_solver_input(time_windows=time_windows)
        output = solve_vrp(inp)
        assert output.solver_time_seconds > 0
        # Check arrival times exist
        for route in output.routes:
            assert len(route.arrival_times) == len(route.internal_indices)

    def test_arrival_times_respect_windows(self):
        time_windows = [(0, 9000), (0, 3600), (1800, 5400), (900, 4500)]
        inp = self._make_solver_input(time_windows=time_windows)
        output = solve_vrp(inp)
        for route in output.routes:
            for i, node in enumerate(route.internal_indices):
                tw_start, tw_end = time_windows[node]
                arrival = route.arrival_times[i]
                assert tw_start <= arrival <= tw_end, (
                    f"Node {node} arrival {arrival} not in window [{tw_start}, {tw_end}]"
                )

    def test_arrival_times_populated(self):
        inp = self._make_solver_input(time_windows=None)
        output = solve_vrp(inp)
        for route in output.routes:
            assert len(route.arrival_times) > 0
            assert all(isinstance(t, (int, float)) for t in route.arrival_times)
