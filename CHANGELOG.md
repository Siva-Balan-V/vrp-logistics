# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows a phase-driven release cadence (tracked in
`docs/PHASE?_PLAN.md`) rather than strict semantic versions. Sections are grouped
by roadmap phase and dated by when the phase reached an integrated state on the
mainline. Internally the app advertises version `1.0.0`.

## [Unreleased]

### In progress — Phase 8 tail
- 8.7 Release hygiene & documentation: this `CHANGELOG.md`, `CONTRIBUTING.md`,
  a consolidated `docs/PRODUCTION_DEPLOYMENT.md` runbook, and a
  `docs/CONFIGURATION.md` env-var reference.
- 8.8 Accessibility pass (keyboard nav, ARIA, contrast, reduced-motion, jest-axe
  smoke tests).
- See `docs/PHASE8_PLAN.md` for the full scope and status.

---

## [Phase 8 — Live Dispatch & Delivery Execution] — 2026-09-07

### Added
- 8.1 Turn-by-turn directions engine: per-leg directions service with OSRM/ORS
  parsing and a Haversine fallback; per-leg directions caching in Redis plus a
  dedicated LRU; `DirectionStep` and `DirectionsResponse` schemas; new
  `GET /api/v1/routes/{route_id}/directions` endpoint.
- 8.2 RouteDetails panel with step-by-step instructions and vehicle tabs; a
  Directions tab in the results panel; driving polyline overlay for the selected
  route with map focus on each step.
- 8.3 Route export expansion: KML generator and direction-enriched CSV export
  (`csv`/`kml` formats), with KML and CSV download buttons in the results panel.
- 8.4 Live fleet dispatch: tenant-scoped WebSocket live channel
  (`/ws/fleet`), a throttled driver-location broadcast service, the
  live fleet map with driver markers and offline flags
  (`OFFLINE_AFTER_MS`), and the real-time `DispatchPage` with fleet roster and
  30s location ticker.
- 8.5 Stop lifecycle state machine with automated notification triggers;
  `StopStatusUpdate` schema; every route waypoint seeded with a pending status;
  new stop-status transition endpoint that drives lifecycle and emits trigger
  events; `NOTIFY_DELAY_THRESHOLD_MIN` config for delayed-stop notifications.
- 8.6 Ride-along re-optimization: `POST /api/v1/optimize-routes/replan`
  re-solves only remaining (non-delivered) stops, seeding each route start from
  the driver's live position; new `ReplanRequest`/`ReplanDriver` schemas;
  `previous_job_id` column on `optimization_jobs` (alembic
  `d4e5f6a7b8c9`) linking replan jobs to their source job; replan requests share
  the `optimize-routes` rate-limit budget.

### Fixed
- Directions cache entries kept as plain dicts to avoid mutating cache state on
  read.
- ORS integer maneuver codes accepted in direction parsing.
- Persistence flushes a job before inserting child rows, and depots are
  persisted from the job payload instead of a removed `depot` field.

### Changed
- `useWebSocket` hook made path-agnostic so the same hook serves optimization
  progress and live fleet channels.

## [Phase 7 — Advanced Features] — 2026-09-06

### Added
- Traffic-aware routing (requires the `ors` backend and `ORS_API_KEY`); enforced
  in backend schemas, frontend validation, and tests.
- PostgreSQL production hardening: `run_migrations()` applies alembic
  `upgrade head` at app startup; `schema.sql` demoted to `schema-legacy.sql`.
- Production deployment tooling: prod docker-compose pointed at real GHCR
  images; Kubernetes manifests under `k8s/` scoped to a `vrp-production`
  namespace with `vrp-env` Secret template; `.env.production.example`.
- Distributed tracing: `OTEL_EXPORTER_OTLP_ENDPOINT` / `OTEL_SERVICE_NAME`
  settings, lazy OpenTelemetry setup with OTLP gRPC exporter, spans tagged with
  request ids, absent endpoint keeps tracing fully disabled.
- Monitoring: Prometheus + Grafana stack (`docker-compose.monitoring.yml`),
  `REDIS_CONNECTED` gauge, Prometheus alert rules for backend health, VRP
  Overview Grafana dashboard provisioned from a file provider.
- Structured logging: `configure_logging()` extracted to `app.logging_config`;
  `LOG_LEVEL`, `LOG_FORMAT` (`console`|`json`), and rotated
  `LOG_FILE` support via structlog.
- Operations: PostgreSQL + Redis backup script (`scripts/backup.sh`) with a
  disaster-recovery runbook (`docs/DISASTER_RECOVERY.md`); concurrent load test
  for the `optimize-routes` endpoint.
- Razorpay billing with INR pricing, order creation/verification, and webhook
  handling alongside the legacy Stripe paths; Razorpay config fields on
  `Company`.
- API key management: `api_keys` table migration, management endpoints, and a
  management page.
- Responsive CSS breakpoints and utility classes; scrollable `ResultsPanel`
  tabs on mobile.

### Fixed
- Traffic mode rejected when `ORS_API_KEY` is not configured or the effective
  backend is not `ors`.
- Robust Jenkinsfile: pre-deploy container/port cleanup (8000, 5173, 5433,
  6379) using `ss`/`grep`.

### Changed
- ESLint pre-commit hook made non-blocking on warnings; k8s YAML allowed in
  multi-document pre-commit check.
- GitHub Actions deploy workflow added.

## [Phase 6 — Feature Expansion & SaaS] — 2026-07-30

### Added
- Real-time operations: WebSocket optimization progress, driver tracking,
  customer notifications, and live ETA computation.
- Analytics dashboard, history page, cost tracking, and territory heatmaps.
- SaaS billing: Stripe integration, usage metering, and an admin panel.
- Dark/light theme toggle with `ThemeContext` integrated into app header.
- Unassigned locations rendered as red `X` markers on the map.
- Client-side JSON upload validation and solver config (time limit, algorithm)
  in the request schema.
- Live progress tracking via polling on the optimize endpoint.
- Turn-by-turn stop details on route selection.
- API key management backend and page.

### Fixed
- Job result cache scoped per company; invalid job ids return 404 instead of
  500.
- Optimize quota limited to the submit endpoint; forwarded headers gated.
- WebSocket reconnect races, result reload, tooltip escaping, and payload
  validation.
- Eager-load user company to fix async tenant propagation; pass auth token on
  route export and only log out on 401.

### Changed
- bcrypt pinned to `4.0.1` for passlib compatibility; Postgres exposed on host
  port 5433 to avoid conflicts.

## [Phase 5 — VRPTW, Multi-Depot, Priority & Security] — 2026-07-26

### Added
- Per-delivery time windows (VRPTW) in the solver with a frontend toggle.
- Multi-depot support in optimization and the frontend form.
- Priority-based scheduling with frontend display.
- Security hardening: HSTS and `Permissions-Policy` headers, HTTPS config,
  tightened CORS with request body size limits, warning on missing JWT secret,
  Redis password support, rate-limit response headers with periodic cleanup,
  and validation of OSRM/ORS API responses before use.
- Unit tests for every API endpoint (57 backend endpoint tests).

## [Phase 4 — Database, Auth & Persistence] — 2026-07-25

### Added
- PostgreSQL service with SQLAlchemy ORM models and Alembic migrations.
- Optimization jobs persisted to PostgreSQL (`job_store`).
- JWT authentication: register, login, refresh, me.
- Tenant/company management endpoints.
- Frontend authentication flow with login, register, and protected routes.
- CSV and GPX route export endpoints and UI buttons.
- Database connectivity retry logic at startup; env passthrough to the backend
  docker service.

## [Phase 3 — Quality, Performance & Tests] — 2026-07-25

### Added
- `X-Request-ID` header for log tracing; request-id-scoped structured context.
- Vectorized Haversine matrix computation with NumPy (10-100x speedup).
- pytest and vitest testing infrastructure with unit and API integration tests.
- Redis status included in the health check response.
- Public `list_jobs()` replacing private cache access; `Literal` type for
  `routing_backend`; lifespan async context manager replacing deprecated
  `on_event`.

### Changed
- Removed dead code (colors, sample data, unused API functions) and unused
  dependencies.

## [Phase 2 — Security & Reliability Hotfix] — 2026-07-25

### Fixed
- Replaced pickle with JSON serialization in the Redis cache.
- Ran the VRP solver in a thread executor to unblock the event loop.
- Removed the CORS wildcard from default allowed origins.
- Stopped exposing exception details in API responses.
- Added a frontend error boundary to prevent blank screens.
- Validated external API responses before indexing.

### Added
- Rate-limiting middleware for API endpoints; nginx request body size limit;
  nginx security headers; documented Redis authentication in env config.

## [Phase 1 — Initial Structure] — 2026-03-17

### Added
- `Basic_Structure` scaffold of the full-stack VRP logistics app.
- Professional project README, `.gitignore`, and Docker healthchecks.
- Leaflet map integration fixes so the map loads correctly.
- Postgres/Redis wiring fixes for the docker-compose service names; relaxed
  dependency versions for Linux compatibility; pip install timeout for reliable
  dependency installation.
