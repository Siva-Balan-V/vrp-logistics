# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows a phase-driven release cadence (tracked in
`docs/PHASE?_PLAN.md`) rather than strict semantic versions. Sections are grouped
by roadmap phase and dated by when the phase reached an integrated state on the
mainline. Internally the app advertises version `1.0.0`.

## [Unreleased]

### Added
- CI pipeline overhaul (PRs #7 and #8, tracked in `docs/CI_PIPELINE_PLAN.md`):
  permissions and concurrency guards plus a deploy gate; `pytest-cov` and vitest
  coverage gates; `security.yml` (pip-audit, npm audit, gitleaks); container
  scanning via Trivy; `db-migrations.yml` (alembic upgrade head against a real
  Postgres); `e2e.yml` compose smoke; PR template and CODEOWNERS. Trivy,
  pip-audit and npm audit are report-only pending baseline review.

### Removed
- **Dependabot** (`.github/dependabot.yml`). It churned through four frontend PRs
  (`#20` → `#26` → `#28`) and two backend ones, re-created after every merge, all
  blocked on the same two version floors — and it proposed `ruff>=0.16.6`, which
  would have undone the exact pin added in PR #7. Dependency updates are now
  manual; the procedure is in `docs/CI_PIPELINE_PLAN.md` §6. Security scanning is
  unaffected — `security.yml` (pip-audit, npm audit, Trivy, gitleaks) is unchanged,
  but nothing opens patch PRs automatically any more.

### Fixed
- Alembic could not bootstrap a fresh database: no migration created the base
  tables, and the root migration added an `api_keys` foreign key to a
  `companies` table that nothing created. Added initial-schema migration
  `2f4a6c8e0b1d` and re-parented the chain onto it.
- Backend image shipped without the alembic runtime (`alembic.ini` and
  `alembic/` were not copied), so container startup silently skipped migrations.
- Startup migrations never ran in the container: `alembic upgrade` was called
  synchronously inside the FastAPI lifespan, and alembic's async environment
  calls `asyncio.run()`, which raises inside a live event loop. The exception
  was swallowed, leaving containers on an empty schema while `/health` stayed
  green. Migrations now run in a dedicated thread.

### Changed
- Backend runtime dependencies (dependabot #12, reworked): 21 packages bumped —
  `fastapi` 0.111.0 → 0.141.1, `uvicorn` 0.30.1 → 0.52.4, `httpx` 0.27.0 →
  0.28.1, `pydantic` 2.7.4 → 2.13.5, `sqlalchemy` 2.0.31 → 2.0.52, `redis`
  5.0.6 → 8.1.0, `cachetools` 5.3.3 → 7.1.8, `alembic` 1.13.1 → 1.19.2,
  `structlog` 24.2.0 → 26.1.0, `stripe` 10.0.0 → 15.6.1, `twilio` 9.0.0 →
  9.11.0, `websockets` 17.0 → 17.1, and others. Two bumps deliberately held
  back — see the note below.
- `ruff` 0.16.0 → 0.16.6, moved in lockstep with `.pre-commit-config.yaml` so the
  pin parity established in PR #7 holds. Dependabot proposed loosening the pin to
  `ruff>=0.16.6`, which would have restored the non-determinism the exact pin
  exists to prevent (`docs/CI_PIPELINE_PLAN.md:127`).
- `react-router-dom` 6.23.0 → 7.18.4 (PR #19). No source changes required: the
  app uses only the declarative APIs (`BrowserRouter`, `Routes`, `Route`, `Link`,
  `useNavigate`, `useParams`, `useSearchParams`, `Navigate`), which v7 keeps.
  The v6→v7 data-router codemod does not apply. Verified locally — 36/36
  frontend tests, eslint 0 errors, prettier and `vite build` clean.

### Dependencies held back
- **`numpy` capped at `>=2.4.2,<2.5`.** `numpy` 2.5.0 dropped cp311 wheels
  entirely and declares `requires_python >=3.12`. Both CI
  (`.github/workflows/ci.yml:10`) and the shipped image
  (`backend/Dockerfile:1`, `python:3.11-slim`) are Python 3.11, so the
  dependabot-proposed `numpy>=2.5.3` breaks the install in *both*, not just CI.
  2.4.2 is the last release with cp311 wheels. Unblocking `numpy` 2.5+ requires
  raising the Python floor to 3.12, which also clears the frontend's undocumented
  Node floor (jsdom 30 needs ≥22.22.2).
- **`bcrypt` held at `==4.0.1`.** `bcrypt` 5.0.0 breaks `passlib` 1.7.4, which
  `app/services/auth.py:21` uses for `CryptContext`. `hash_password` and
  `verify_password` have **no test coverage**, so the migration off the
  unmaintained `passlib` (last release 2020) needs tests first. It is a small,
  well-bounded change — only `auth.py:25,29` touch the context.
- Frontend: React 19.3.0 (PR #21); vite 8.3.2, `@vitejs/plugin-react` 6.1.1,
  vitest 5.0.3, `@vitest/coverage-v8` 5.0.3 (PR #22); jsdom 29.1.1 and the
  testing-library set (PR #25); `eslint-plugin-react` 7.37.5,
  `eslint-plugin-react-hooks` 7.1.1, `globals` 17.13.0 (PR #27). `eslint` stays
  on 9 — `eslint-plugin-react@7.37.5`, the newest release, peers `^9.7` and no
  combination reaches eslint 10 until it ships support.
- `starlette` 1.7.0 now deprecates `httpx` in `starlette.testclient` and asks for
  `httpx2`; the warning is benign today and tracked as future frontend work.

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
