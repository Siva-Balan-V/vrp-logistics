# RouteForge – Architecture & API Documentation

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                 │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  React + Vite SPA  (Leaflet map, Recharts, DM Mono / Syne)    │  │
│  │  • Upload/Generate delivery JSON                               │  │
│  │  • Configure vehicles & routing backend                        │  │
│  │  • Animated route map with per-vehicle selection               │  │
│  │  • Charts: distance & time per vehicle                         │  │
│  └─────────────────────────┬─────────────────────────────────────┘  │
└────────────────────────────│────────────────────────────────────────┘
                             │  HTTP / REST (JSON)
┌────────────────────────────▼────────────────────────────────────────┐
│                        API LAYER  (FastAPI)                          │
│                                                                      │
│  POST /api/v1/optimize-routes   ←── OptimizeRequest                 │
│  GET  /api/v1/routes/{job_id}   ←── cached result lookup            │
│  GET  /api/v1/routes            ←── recent jobs list                │
│  GET  /health                   ←── health check                    │
│                                                                      │
│  Middleware:  CORS · request timing · structured logging             │
└────────────────────────────┬────────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
┌─────────────────┐ ┌──────────────┐  ┌────────────────────┐
│  MATRIX SERVICE │ │ CACHE SERVICE│  │   VRP SOLVER       │
│                 │ │              │  │                    │
│  ① Haversine    │ │  LRU (in-    │  │  OR-Tools          │
│  ② OSRM table   │ │  process)    │  │  RoutingModel      │
│  ③ ORS matrix   │ │  + Redis     │  │  CVRP + time dim   │
│                 │ │  (optional)  │  │  GLS metaheuristic │
│  n×n matrices:  │ │              │  │                    │
│  distance (km)  │ │  SHA-256 key │  │  60 s time limit   │
│  duration (s)   │ │  1 h TTL     │  │  penalty unassign  │
└────────┬────────┘ └──────────────┘  └────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL ROUTING APIs                             │
│                                                                      │
│  router.project-osrm.org/table/v1/driving/{coords}                  │
│  api.openrouteservice.org/v2/matrix/driving-car                      │
│  (fallback: great-circle × 1.35 road-network factor)                │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
Input JSON
    │
    ├─► Pydantic validation (schemas.py)
    │       • unique IDs, lat/lon bounds, demand ≥ 0
    │
    ├─► Build coordinate list  [depot, d1, d2, …, dn]
    │
    ├─► Cache lookup (SHA-256 of coords + backend)
    │       HIT  → skip matrix call
    │       MISS → call distance_matrix.build_matrix()
    │                   ├─ OSRM:  batched /table requests
    │                   ├─ ORS:   batched /v2/matrix requests
    │                   └─ Haversine: O(n²) in-process
    │
    ├─► VRPInput construction
    │       • integer-scaled matrices (×1000 for OR-Tools)
    │       • max_route_duration_seconds enforced via Time dimension
    │       • demand-per-stop fed into Capacity dimension
    │
    ├─► OR-Tools solve
    │       • PATH_CHEAPEST_ARC first solution
    │       • GUIDED_LOCAL_SEARCH improvement
    │       • Penalty-based node dropping (unassigned)
    │       • 60 s wall-clock limit
    │
    ├─► Extract routes from solution object
    │       • per-vehicle: ordered stop list, distance, time, packages
    │       • unvisited nodes → unassigned list
    │
    └─► OptimizeResponse JSON
            • job_id, status, solver_time_seconds
            • vehicles[]: route, distance_km, time_minutes, waypoints
            • unassigned[], matrix_source
```

## API Reference

### POST /api/v1/optimize-routes

**Request body:**
```json
{
  "depot": {
    "id": 0,
    "lat": 51.5074,
    "lon": -0.1278,
    "demand": 0,
    "label": "London Depot"
  },
  "deliveries": [
    { "id": 1, "lat": 51.515, "lon": -0.072, "demand": 2, "label": "Stop A" }
  ],
  "vehicles": {
    "count": 18,
    "capacity": 50,
    "max_route_duration_seconds": 9000,
    "speed_kmh": 30.0
  },
  "routing_backend": "haversine"
}
```

**Response:**
```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "success",
  "solver_time_seconds": 4.21,
  "total_locations": 600,
  "assigned_count": 587,
  "unassigned_count": 13,
  "vehicles_used": 18,
  "total_distance_km": 842.3,
  "total_time_minutes": 1680.5,
  "matrix_source": "haversine",
  "vehicles": [
    {
      "vehicle_id": 1,
      "route": [0, 23, 45, 12, 0],
      "route_labels": ["London Depot", "Stop A", "Stop B", "Stop C", "London Depot"],
      "distance_km": 35.4,
      "time_minutes": 130.2,
      "packages_delivered": 8,
      "waypoints": [{"id": 0, "lat": 51.5074, "lon": -0.1278}, ...]
    }
  ],
  "unassigned": [101, 203],
  "unassigned_labels": ["Stop X", "Stop Y"]
}
```

### GET /api/v1/routes/{job_id}
Returns a cached OptimizeResponse by job ID. Results cached 2 hours.

### GET /api/v1/routes?limit=10
Lists up to `limit` recent job summaries from the in-process cache.

### GET /health
```json
{ "status": "ok", "version": "1.0.0", "routing_backend": "haversine" }
```

## Mathematical Model

**Problem class:** CVRPTW (Capacitated VRP with Time Windows simplified to a global route duration limit)

**Objective:**
```
Minimize Σ_k Σ_{i,j} dist_{ij} · x_{ijk}
```

**Constraints:**
1. Each delivery visited by at most one vehicle: `Σ_k Σ_j x_{ijk} ≤ 1`
2. Flow conservation: `Σ_j x_{ijk} = Σ_j x_{jik}` for all i, k
3. Route duration: `Σ_{i,j on route k} time_{ij} ≤ 9000 s`
4. Capacity: `Σ_{i on route k} demand_i ≤ vehicle_capacity`
5. Unassigned penalty: nodes may be dropped at cost `max_dist × 10`

**Algorithm:**
- First solution: PATH_CHEAPEST_ARC (greedy nearest-neighbour arc insertion)
- Improvement: GUIDED_LOCAL_SEARCH (penalizes frequently-used arcs to escape local optima)
- Time limit: 60 s (configurable via `SOLVER_TIME_LIMIT_SECONDS`)

## Scalability Notes

| Scale        | Nodes | Recommended backend | Expected solve time |
|-------------|-------|---------------------|---------------------|
| Small       | ≤50   | haversine           | <1 s               |
| Medium      | ≤200  | osrm                | 2–10 s             |
| Large       | ≤600  | osrm (batched)      | 15–60 s            |
| Very large  | >600  | Split into zones    | Run parallel jobs  |

**Caching:** The distance matrix is the most expensive computation.
The SHA-256 cache key means identical location sets reuse the matrix instantly.

**Horizontal scaling:** Run multiple backend workers behind a load balancer.
Redis cache ensures workers share matrix results.
