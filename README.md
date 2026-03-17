# 🚚 RouteForge — Last-Mile VRP Optimizer

> **Production-grade Vehicle Routing Problem solver** for last-mile logistics.  
> Handles **600+ delivery locations** across **18+ vehicles** with a strict **2.5-hour route limit**,  
> powered by **Google OR-Tools** and real road-network distances.

---

## ✨ Features

| Feature | Detail |
|---|---|
| 🔢 Scale | Up to 600 delivery locations per planning cycle |
| 🚐 Fleet | 18+ vehicles with configurable capacity |
| ⏱ Time Limit | Strict 2.5 h (9 000 s) per-vehicle constraint |
| 🗺 Road Distances | OSRM / OpenRouteService / Haversine fallback |
| 🧠 Solver | OR-Tools CVRP + GUIDED_LOCAL_SEARCH metaheuristic |
| 📦 Capacity | Per-vehicle package capacity enforced |
| ❌ Unassigned | Infeasible stops cleanly reported, never silently violated |
| 🗃 Caching | SHA-256 matrix cache (Redis + in-process LRU) |
| 📊 Dashboard | React SPA — interactive Leaflet map + Recharts |
| 🐳 Docker | One-command deployment via Docker Compose |

---

## 🏗 Architecture

```
React SPA (Vite + Leaflet + Recharts)
          │  REST/JSON
FastAPI (Python 3.11)
    ├── Distance Matrix Service  →  OSRM / ORS / Haversine
    ├── Cache Service            →  Redis + LRU
    └── VRP Solver               →  Google OR-Tools 9.x
```

Full diagram + data flow: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## 🚀 Quick Start

### Local (no Docker)

```bash
git clone https://github.com/yourname/routeforge-vrp.git
cd routeforge-vrp

# Backend
cd backend
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp ../.env.example .env
python -m uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
# macOS/Linux or Windows cmd: npm install && npm run dev
# Windows PowerShell (execution policy restricted): npm.cmd install; npm.cmd run dev
npm.cmd install
npm.cmd run dev
```

Open **http://localhost:5173**

### Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

- **Frontend** → http://localhost:5173  
- **API Docs** → http://localhost:8000/docs

---

## ⚙️ Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `ROUTING_BACKEND` | `haversine` | `haversine` \| `osrm` \| `ors` |
| `ORS_API_KEY` | *(empty)* | [Free key](https://openrouteservice.org/) |
| `OSRM_BASE_URL` | public demo | Self-hosted OSRM for production |
| `SOLVER_TIME_LIMIT_SECONDS` | `60` | OR-Tools wall-clock limit |
| `REDIS_URL` | *(empty)* | Optional Redis for shared cache |

---

## 📡 API

### `POST /api/v1/optimize-routes`

```json
{
  "depot":      { "id": 0, "lat": 51.5074, "lon": -0.1278 },
  "deliveries": [ { "id": 1, "lat": 51.515, "lon": -0.072, "demand": 2 } ],
  "vehicles":   { "count": 18, "capacity": 50, "max_route_duration_seconds": 9000 }
}
```

```json
{
  "job_id": "uuid", "status": "success", "solver_time_seconds": 4.2,
  "vehicles": [ { "vehicle_id": 1, "route": [0,23,45,0], "distance_km": 35.4, "time_minutes": 130 } ],
  "unassigned": [101, 203]
}
```

### `GET /api/v1/routes/{job_id}` — retrieve cached result  
### `GET /health` — health check

---

## 📁 Structure

```
vrp-logistics/
├── backend/app/
│   ├── main.py              FastAPI app + middleware
│   ├── config.py            Settings
│   ├── models/schemas.py    Pydantic I/O models
│   ├── routes/              API endpoints
│   ├── services/            Matrix, cache, orchestrator
│   └── optimization/        OR-Tools VRP solver
├── frontend/src/
│   ├── App.jsx              State machine
│   ├── api.js               HTTP client
│   └── components/          Header, UploadPanel, Map, Results, Charts
├── scripts/
│   ├── generate_sample_data.py   600-location generator
│   └── test_api.py               Integration tests
├── database/schema.sql      PostgreSQL schema
├── docs/ARCHITECTURE.md
├── docker-compose.yml
└── .env.example
```

---

## 🧪 Tests & Sample Data

```bash
# Integration tests (backend must be running)
python scripts/test_api.py --url http://localhost:8000

# Generate 600-location dataset
python scripts/generate_sample_data.py --n 600 --city london --out sample_600.json
```

---

## 📈 Performance Benchmarks

| Locations | Vehicles | Haversine matrix | Solve time |
|---|---|---|---|
| 30 | 5 | 0.01 s | <1 s |
| 100 | 10 | 0.1 s | 2–5 s |
| 300 | 18 | 0.8 s | 10–30 s |
| 600 | 18 | 3.2 s | 30–60 s |

*Matrix cached — repeated calls with identical location sets: ~0 ms.*

---

## 🔮 Roadmap

- Time windows per delivery (VRPTW)  
- Real-time traffic (HERE / Google Maps Platform)  
- Multi-depot routing  
- WebSocket progress streaming  
- Route export (GPX, CSV)  
- Kubernetes Helm chart  

---

*Built with FastAPI · Google OR-Tools · React · Leaflet · Docker*
