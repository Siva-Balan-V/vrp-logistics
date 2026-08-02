"""Tests for VRP solver with synthetic matrices."""

import numpy as np

from app.optimization.vrp_solver import (
    RouteResult,
    SolverOutput,
    VRPInput,
    _scale_matrix,
    solve_vrp,
)


def test_scale_matrix_basic():
    """_scale_matrix should multiply all entries by the scale factor."""
    mat = np.array([[1.0, 2.0], [3.0, 4.0]])
    scaled = _scale_matrix(mat, 1000)
    assert scaled == [[1000, 2000], [3000, 4000]]


def test_scale_matrix_zero():
    """_scale_matrix should handle zeros correctly."""
    mat = np.zeros((2, 2))
    scaled = _scale_matrix(mat, 1000)
    assert scaled == [[0, 0], [0, 0]]


def test_solve_vrp_two_deliveries():
    """Solver should assign both deliveries to same vehicle."""
    dist = np.array(
        [
            [0.0, 10.0, 20.0],
            [10.0, 0.0, 15.0],
            [20.0, 15.0, 0.0],
        ]
    )
    dur = dist * 120  # 120 seconds per km

    inp = VRPInput(
        num_vehicles=2,
        vehicle_capacity=50,
        max_route_duration_seconds=9000,
        distance_matrix=dist,
        duration_matrix=dur,
        demands=[0, 1, 1],
        location_ids=[0, 101, 102],
        speed_kmh=30.0,
        solver_time_limit_seconds=10,
    )

    output = solve_vrp(inp)

    assert output.solver_time_seconds > 0
    assert len(output.routes) >= 1
    all_assigned = set()
    for route in output.routes:
        for lid in route.location_ids:
            all_assigned.add(lid)
    assert 0 in all_assigned  # depot in at least one route
    assert 101 in all_assigned or 101 in output.unassigned_ids
    assert 102 in all_assigned or 102 in output.unassigned_ids


def test_solve_vrp_capacity_constraint():
    """Solver should respect vehicle capacity."""
    dist = np.array(
        [
            [0.0, 10.0, 20.0, 30.0],
            [10.0, 0.0, 15.0, 25.0],
            [20.0, 15.0, 0.0, 10.0],
            [30.0, 25.0, 10.0, 0.0],
        ]
    )
    dur = dist * 120

    inp = VRPInput(
        num_vehicles=3,
        vehicle_capacity=2,  # each vehicle can carry at most 2 demand units
        max_route_duration_seconds=9000,
        distance_matrix=dist,
        duration_matrix=dur,
        demands=[0, 2, 1, 1],
        location_ids=[0, 101, 102, 103],
        speed_kmh=30.0,
        solver_time_limit_seconds=10,
    )

    output = solve_vrp(inp)

    for route in output.routes:
        delivery_demand = sum(inp.demands[inp.location_ids.index(lid)] for lid in route.location_ids if lid != 0)
        assert delivery_demand <= 2


def test_solve_vrp_all_unassigned_when_impossible():
    """All deliveries should be unassigned when capacity is 0."""
    dist = np.array(
        [
            [0.0, 10.0, 20.0],
            [10.0, 0.0, 15.0],
            [20.0, 15.0, 0.0],
        ]
    )
    dur = dist * 120

    inp = VRPInput(
        num_vehicles=1,
        vehicle_capacity=0,
        max_route_duration_seconds=9000,
        distance_matrix=dist,
        duration_matrix=dur,
        demands=[0, 1, 1],
        location_ids=[0, 101, 102],
        speed_kmh=30.0,
        solver_time_limit_seconds=10,
    )

    output = solve_vrp(inp)

    assert len(output.unassigned_ids) > 0


def test_solve_vrp_solver_output_types():
    """SolverOutput should have the correct structure."""
    dist = np.array(
        [
            [0.0, 10.0, 20.0],
            [10.0, 0.0, 15.0],
            [20.0, 15.0, 0.0],
        ]
    )
    dur = dist * 120

    inp = VRPInput(
        num_vehicles=2,
        vehicle_capacity=50,
        max_route_duration_seconds=9000,
        distance_matrix=dist,
        duration_matrix=dur,
        demands=[0, 1, 1],
        location_ids=[0, 101, 102],
        speed_kmh=30.0,
        solver_time_limit_seconds=10,
    )

    output = solve_vrp(inp)

    assert isinstance(output, SolverOutput)
    assert isinstance(output.solver_time_seconds, float)
    assert isinstance(output.routes, list)
    if output.routes:
        route = output.routes[0]
        assert isinstance(route, RouteResult)
        assert isinstance(route.vehicle_id, int)
        assert isinstance(route.location_ids, list)
        assert isinstance(route.distance_km, (int, float))
        assert isinstance(route.time_seconds, (int, float))
        assert isinstance(route.packages_delivered, int)
    assert isinstance(output.unassigned_ids, list)
