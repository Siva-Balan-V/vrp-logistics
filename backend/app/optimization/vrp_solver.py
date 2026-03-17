"""
VRP Solver – Google OR-Tools CVRPTW (Capacitated VRP with Time Windows)
=======================================================================

Mathematical model
──────────────────
  Sets:
    V = {0, …, n-1}   locations (0 = depot)
    K = {1, …, m}     vehicles

  Decision variables:
    x_{ijk} ∈ {0,1}   1 if vehicle k travels edge (i→j)
    t_{ik}            arrival time of vehicle k at location i

  Objective:
    Minimize Σ_{k} Σ_{i,j} distance_{ij} · x_{ijk}

  Constraints:
    1.  Each delivery visited by exactly one vehicle (or marked unassigned)
    2.  Flow conservation at each node
    3.  Route duration ≤ max_route_duration_seconds (per vehicle)
    4.  Capacity: Σ_{i on route k} demand_i ≤ vehicle_capacity
    5.  Sub-tour elimination (via time propagation in OR-Tools)

Algorithm
─────────
  OR-Tools RoutingModel with:
    - PATH_CHEAPEST_ARC first solution heuristic
    - GUIDED_LOCAL_SEARCH metaheuristic (proven best for VRP)
    - Time limit: configurable (default 60 s)
    - Soft constraint on unassigned nodes (penalty-based)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import structlog
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

logger = structlog.get_logger(__name__)

# ─────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────

@dataclass
class VRPInput:
    num_vehicles: int
    vehicle_capacity: int
    max_route_duration_seconds: int
    # n×n matrices (index 0 = depot)
    distance_matrix: np.ndarray        # kilometres
    duration_matrix: np.ndarray        # seconds
    demands: list[int]                 # demand[0] = 0 (depot)
    location_ids: list[int]            # mapping: internal_index → original_id
    speed_kmh: float = 30.0
    solver_time_limit_seconds: int = 60


@dataclass
class RouteResult:
    vehicle_id: int
    internal_indices: list[int]        # includes depot at start & end
    location_ids: list[int]
    distance_km: float
    time_seconds: float
    packages_delivered: int


@dataclass
class SolverOutput:
    routes: list[RouteResult] = field(default_factory=list)
    unassigned_internal: list[int] = field(default_factory=list)
    unassigned_ids: list[int] = field(default_factory=list)
    solver_time_seconds: float = 0.0
    objective_value: float = 0.0


# ─────────────────────────────────────────────
# MATRIX SCALING
# OR-Tools works with integers, so we scale
# ─────────────────────────────────────────────

_DIST_SCALE = 1000   # store metres (km × 1000) as integers
_TIME_SCALE = 1      # seconds are already integers


def _scale_matrix(mat: np.ndarray, scale: int) -> list[list[int]]:
    n = mat.shape[0]
    return [[int(mat[i, j] * scale) for j in range(n)] for i in range(n)]


# ─────────────────────────────────────────────
# MAIN SOLVER
# ─────────────────────────────────────────────

def solve_vrp(inp: VRPInput) -> SolverOutput:
    t0 = time.perf_counter()
    n = inp.distance_matrix.shape[0]

    # Scale matrices to integers
    dist_int = _scale_matrix(inp.distance_matrix, _DIST_SCALE)
    dur_int = _scale_matrix(inp.duration_matrix, _TIME_SCALE)
    max_dur_int = int(inp.max_route_duration_seconds * _TIME_SCALE)

    logger.info(
        "vrp_solver_start",
        n_locations=n,
        n_vehicles=inp.num_vehicles,
        max_duration_s=inp.max_route_duration_seconds,
    )

    # ── Routing Manager ──────────────────────────────────────────────────────
    manager = pywrapcp.RoutingIndexManager(n, inp.num_vehicles, 0)  # depot = 0
    routing = pywrapcp.RoutingModel(manager)

    # ── Distance callback ────────────────────────────────────────────────────
    def distance_callback(from_idx: int, to_idx: int) -> int:
        i = manager.IndexToNode(from_idx)
        j = manager.IndexToNode(to_idx)
        return dist_int[i][j]

    transit_cb_idx = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb_idx)

    # ── Time callback ────────────────────────────────────────────────────────
    def time_callback(from_idx: int, to_idx: int) -> int:
        i = manager.IndexToNode(from_idx)
        j = manager.IndexToNode(to_idx)
        return dur_int[i][j]

    time_cb_idx = routing.RegisterTransitCallback(time_callback)

    # ── Time dimension (route duration constraint) ───────────────────────────
    routing.AddDimension(
        time_cb_idx,
        0,                  # no slack
        max_dur_int,        # max cumulative time per vehicle
        True,               # fix cumulative to zero at start
        "Time",
    )
    time_dimension = routing.GetDimensionOrDie("Time")

    # ── Capacity dimension ────────────────────────────────────────────────────
    def demand_callback(from_idx: int) -> int:
        node = manager.IndexToNode(from_idx)
        return inp.demands[node]

    demand_cb_idx = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_cb_idx,
        0,                                   # no slack
        [inp.vehicle_capacity] * inp.num_vehicles,
        True,
        "Capacity",
    )

    # ── Allow dropping nodes (unassigned) with a high penalty ─────────────────
    #   Penalty > max possible route distance → solver prefers visiting over dropping
    #   but will drop if constraints cannot be satisfied.
    max_dist = int(np.max(inp.distance_matrix) * _DIST_SCALE * n)
    penalty = max(max_dist * 10, 1_000_000)
    for node_idx in range(1, n):           # skip depot (0)
        routing.AddDisjunction([manager.NodeToIndex(node_idx)], penalty)

    # ── Search parameters ─────────────────────────────────────────────────────
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    params.time_limit.seconds = inp.solver_time_limit_seconds
    params.log_search = False

    # ── Solve ─────────────────────────────────────────────────────────────────
    solution = routing.SolveWithParameters(params)
    solver_time = time.perf_counter() - t0

    output = SolverOutput(solver_time_seconds=round(solver_time, 3))

    if not solution:
        logger.warning("vrp_no_solution_found", elapsed_s=round(solver_time, 2))
        # Return all as unassigned
        output.unassigned_internal = list(range(1, n))
        output.unassigned_ids = [inp.location_ids[i] for i in output.unassigned_internal]
        return output

    output.objective_value = solution.ObjectiveValue()
    logger.info(
        "vrp_solution_found",
        objective=output.objective_value,
        elapsed_s=round(solver_time, 2),
    )

    # ── Extract routes ────────────────────────────────────────────────────────
    visited_nodes: set[int] = set()

    for v in range(inp.num_vehicles):
        idx = routing.Start(v)
        internal_nodes: list[int] = []
        route_dist_m = 0
        route_dur_s = 0

        while not routing.IsEnd(idx):
            node = manager.IndexToNode(idx)
            internal_nodes.append(node)
            visited_nodes.add(node)
            next_idx = solution.Value(routing.NextVar(idx))
            next_node = manager.IndexToNode(next_idx)
            route_dist_m += dist_int[node][next_node]
            route_dur_s += dur_int[node][next_node]
            idx = next_idx

        # Append depot at end
        end_node = manager.IndexToNode(routing.End(v))
        internal_nodes.append(end_node)

        delivery_nodes = [nd for nd in internal_nodes if nd != 0]
        if not delivery_nodes:
            continue   # empty vehicle – skip

        result = RouteResult(
            vehicle_id=v + 1,
            internal_indices=internal_nodes,
            location_ids=[inp.location_ids[nd] for nd in internal_nodes],
            distance_km=round(route_dist_m / _DIST_SCALE, 3),
            time_seconds=round(route_dur_s, 1),
            packages_delivered=sum(inp.demands[nd] for nd in delivery_nodes),
        )
        output.routes.append(result)

    # ── Unassigned nodes ──────────────────────────────────────────────────────
    for node in range(1, n):
        if node not in visited_nodes:
            output.unassigned_internal.append(node)
            output.unassigned_ids.append(inp.location_ids[node])

    logger.info(
        "vrp_extraction_done",
        vehicles_used=len(output.routes),
        unassigned=len(output.unassigned_ids),
    )
    return output
