# Phase 8 — Live Dispatch & Delivery Execution: Plan

> Status: in progress — 8.1–8.6 completed and committed (8.1–8.3, 8.5 earlier; 8.4
> live-dispatch branch; 8.6 replan); 8.7 docs and 8.8 a11y remaining.

## Goal

Phase 7 delivered batch optimization at production quality (traffic, PostgreSQL,
k8s, monitoring, tracing). Phase 8 closes the loop between **planning** and
**execution**: turn optimized routes into drive-able directions, track drivers
live, automate customer notifications from stop status, and handle mid-route
disruption. It ends the last open item from `BUSINESS_ROADMAP.md` (turn-by-turn,
milestone 2.6) and adds release hygiene.

## Current-state audit (what already exists on `main`)

| Capability | Status on `main` |
|------------|------------------|
| Optimization: CVRP + time windows + multi-depot + priority + traffic | ✅ Complete (Phases 2/7) |
| Auth, multi-tenancy, API keys, billing (Stripe + Razorpay), quotas | ✅ Complete |
| Jobs persisted to PostgreSQL; job history + re-run UI | ✅ Complete |
| WebSocket progress for solver; status polling fallback | ✅ Complete |
| Export: CSV + GPX | ✅ CSV/GPX (`app/services/export.py`) |
| Driver records + GPS ping endpoint (`DriverLocationUpdate`) | ✅ Backend + Driver pages |
| Live ETA recalculation from driver position | ✅ `app/services/eta.py` |
| Notification providers + triggers (out_for_delivery/arrived/delayed) | ✅ `app/services/notifications.py` |
| Analytics dashboard + territory endpoint | ✅ |
| Monitoring: Prometheus/Grafana/alerts, OTel tracing | ✅ (Phase 7) |
| **Turn-by-turn directions** | ❌ **No directions service, no endpoint, no UI** |
| **Real-time dispatch / live fleet map** | ❌ **GPS pings are REST-only; no WS broadcast, no dispatch view** |
| **Delivery/stop status lifecycle** | ❌ **No stop status field, nothing auto-emits arrived/delayed events** |
| **Mid-route re-optimization (ride-along re-plan)** | ❌ **None** |
| Docs: SECURITY.md, PRIVACY.md, DR, Jenkins, infra-setup | ✅ |
| Docs: `CHANGELOG.md`, `CONTRIBUTING.md`, production runbook, config reference | ❌ |

## Scope — 8 items

### 8.1 Turn-by-turn directions engine (roadmap 2.6) — High ✅ Done
Real instruction-level route legs so drivers can actually follow the plan.
- `app/services/directions.py`: fetch route geometry + maneuvers from OSRM
  (or ORS when `routing_backend=ors`), with haversine fallback producing a
  single "go to next stop" leg when no router is configured.
- Schema additions: per-route `directions: list[DirectionStep]` with
  `{instruction, distance_m, duration_s, maneuver, lon, lat}`.
- Endpoint `GET /api/v1/routes/{job_id}/directions/route/{route_index}` so the
  map can render legs lazily per vehicle.
- Cache legs by `(backend, origin, dest)` in Redis/LRU like distance matrices.
- Tests: mocked OSRM geometry parsing, ORS variant, haversine fallback,
  cache hit.

### 8.2 RouteDetails panel with step-by-step instructions — Medium ✅ Done
- New `RouteDetails` component: active-vehicle tabs, maneuver list (turn
  icons/arrows, distance, ETA deltas), tap a step to focus map.
- Render leg polyline on `MapView` for the selected route (multi-stop path
  already drawn; add driving polyline per leg).
- "Start navigation" in-app progress: highlight the upcoming step as the driver
  checks in stops (feeds 8.5).
- Tests: component test with a fixture route; vitest.

### 8.3 Route export: KML + directions in CSV — Medium ✅ Done
- Add KML generator (`_generate_kml`) with per-leg waypoints + step names.
- Extend CSV export with direction columns (maneuver + step instruction).
- Extend `routes/export.py` to serve `kml` format.
- Tests: `test_export.py` additions assert well-formed XML/doc structure.

### 8.4 Live fleet dispatch view — High ✅ Done
- WebSocket `WS /api/v1/ws/drivers/{company_id}` broadcasting driver position
  updates (subscribe on driver GPS ping; throttle to 1/s per driver).
- Frontend `DispatchPage`: fleet map with a live marker per driver (pulsing
  when moving), current ETA vs original, latest ping time, offline flag.
- Guard with auth dependency; scope strictly to `company_id` (tenant-safe).
- Tests: WS broadcast test, unauthorized cross-tenant access rejected.

### 8.5 Stop lifecycle + automated notifications — High ✅ Done
- Add `status` to stops in job store / optimize response
  (`pending → en_route → arrived → delivered`), persisted per job.
- `POST /api/v1/drivers/{driver_id}/stops/{stop_id}/status` transitions a stop
  and, on `arrived`, emits the existing `arrived` notification trigger (and
  `delayed` when live-ETA delta exceeds threshold from `eta.py`).
- Respect per-company notification settings (already modeled).
- Tests: transition guards (out-of-order), notification provider mocked,
  delayed trigger fires on stale drivers.

### 8.6 Ride-along re-optimization (disruption handling) — Medium ✅ Done
- `POST /api/v1/optimize-routes/replan`: takes the previous `job_id` + live
  driver positions; re-solves only the remaining (non-delivered) stops with the
  current position as the start point, keeps depot/vehicle constraints.
- Returns updated route + ETAs; persists as a new job linked to the old one.
- Tests: remaining-stops subset solves; delivered stops excluded.

### 8.7 Release hygiene & documentation — Low
- `CHANGELOG.md` (keep-a-changelog format; backfill from Phases 1–8).
- `CONTRIBUTING.md` (toolchain, test/lint commands, pre-commit, branching).
- Consolidate `INFRASTRUCTURE_SETUP.md` + `JENKINS_SETUP.md` +
  `DISASTER_RECOVERY.md` into a `docs/PRODUCTION_DEPLOYMENT.md` runbook with
  links, plus a `docs/CONFIGURATION.md` env-var reference (auto vs manual):
  `LOG_*`, `OTEL_*`, `REDIS_*`, `DATABASE_URL`, `ROUTING_BACKEND`, billing keys.

### 8.8 Accessibility pass (improvement item 37) — Medium
- Keyboard navigation for `ResultsPanel` tabs, `UploadPanel` toggles, header
  menu; proper ARIA roles/labels; visible focus indicators.
- Ensure WCAG AA contrast for `--text-*` tokens (verify with automated check).
- Respect existing `prefers-reduced-motion`.
- Add a smoke a11y test (jest-axe) on Header + UploadPanel.

## Suggested implementation order

Dependencies drive the order; each item is independently shippable.

```
8.1 Directions engine         ← 8.2, 8.3 depend on it
  → 8.2 RouteDetails UI           (needs 8.1)
  → 8.3 Export formats            (needs 8.1)
8.5 Stop lifecycle             ← enables late 8.2 "start navigation" and 8.6
  → 8.4 Live dispatch WS          (uses the same status/position events)
  → 8.6 Ride-along re-plan        (needs 8.5 stop statuses)
8.7 Docs hygiene                ← independent, do anytime
8.8 Accessibility               ← independent, do anytime
```

## Verification

- Backend: `ruff check` + `ruff format` +
  `DATABASE_URL= REDIS_URL= ROUTING_BACKEND=haversine .venv/bin/python -m pytest`
  (networking tests still mocked; no external router required).
- Frontend: `vitest run`, `eslint`, `prettier --check`, `vite build`.
- Infra: `docker compose -f docker-compose.monitoring.yml config`; no k8s/kubectl
  available locally (manifests validated with pyyaml only).
- E2E scenario for Phase 8: optimize a route → view step-by-step directions →
  mark stops delivered → driver positions appear on DispatchPage → customer
  receives an "arrived" notification → simulate a delay and re-plan remaining
  stops.
- New endpoints covered by unit tests; WS and cross-tenant cases included.

## Commit strategy

Follow the Phase 7 pattern: granular, single-concern commits so pre-commit hooks
stay green and history reads as a stack of reviewable steps (e.g. directions
service → schema → endpoint → cache → tests → UI panel).
