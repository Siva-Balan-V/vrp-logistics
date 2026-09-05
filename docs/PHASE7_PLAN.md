# Phase 7 — Advanced Features: Plan

> Status: in progress — items 1–5 done on `feat/traffic-aware-routing`.

## Goal

Deliver the long-term features from the Phase 7 roadmap item: windowed scheduling,
traffic-aware routing, multi-depot, full PostgreSQL wiring, production-grade
deployments, and observability.

## Current-state audit

Many Phase 7 items are already substantially implemented on `main`. The work below
closes the remaining gaps rather than building from scratch.

| # | Item | Status on `main` | Stub / gap |
|---|------|------------------|------------|
| 45 | Time windows per delivery (VRPTW) | ✅ Backend done | No frontend input for windows |
| 46 | Real-time traffic-aware routing | ⚠️ Partial | ORS `traffic=True` + `OptimizeRequest.traffic` exist; no UI toggle |
| 47 | Multi-depot optimization | ✅ Backend done | Frontend still single-depot (`depot`); no `depots[]` editor |
| 48 | PostgreSQL integration | ⚠️ Partial | Async SQLAlchemy + alembic (3 migrations); `database/schema.sql` possible drift; no migration step in compose/CI |
| 49 | Kubernetes support | ⚠️ Partial | Manifests + HPA + probes; placeholder `ghcr.io/your-org/*` images, no ingress/secret/namespace manifests |
| 50 | Production docker-compose | ⚠️ Partial | Resource limits/healthchecks/logging exist; placeholder images, no env template |
| 51 | Monitoring + distributed tracing | ⚠️ Partial | `/metrics` + Prometheus/Grafana compose exist; **no OpenTelemetry tracing**, no committed dashboards/alerts |
| 52 | Structured logging | ✅ Mostly done | structlog JSON + rotation + `X-Request-ID`; needs tests/docs |

## Suggested implementation order

Backend-tested increments first, then frontend, then deployment/infra polish.

### 1. Traffic-aware routing (46) ✅ done on `feat/traffic-aware-routing`
- Backend now rejects `traffic=true` with a clear 422 when `ORS_API_KEY` is not
  configured (`routes/optimization.py`).
- Backend rejects `traffic=true` when the effective routing backend is not `ors`.
- `validatePayload` errors client-side when `traffic=true` without `routing_backend: "ors"`.
- Toggle shows a "requires ORS_API_KEY on the server" hint.
- Tests: 3 `test_api.py` cases + 3 `uploadPanel.test.js` cases.

### 2. Time-window input (45) ✅ verified done on `main`
- `UploadPanel` "Enable time windows (VRPTW)" toggle assigns
  `time_window_start`/`time_window_end` to generated stops; paste/upload modes
  accept arbitrary windows. Backend solves via OR-Tools `AddTimeDimension`
  (`test_time_windows.py`). No code change needed.

### 3. Multi-depot frontend (47) ✅ verified done on `main`
- `UploadPanel` "Use 2 depots (multi-depot)" toggle generates `depots[]`;
  `MapView` renders depot A/B markers and the backend round-robins vehicle
  starts (`test_multi_depot.py`). Legacy `depot` field still accepted for
  backward compatibility. No code change needed.

### 4. PostgreSQL completion (48) ✅ done on `feat/traffic-aware-routing`
- `database/schema.sql` renamed to `database/schema-legacy.sql` with a note that
  alembic is the source of truth.
- New `app.database.run_migrations()` runs `alembic upgrade head` at startup from
  the lifespan (after `wait_for_db`), so prod compose/CI need no extra step.
- `run_migrations` covered by `tests/test_database.py`.

### 5. Production deployment hardening (50, 49) ✅ done on `feat/traffic-aware-routing`
- `docker-compose.prod.yml` and k8s manifests now reference the real registry
  `ghcr.io/siva-balan-v/*` (compose tag interpolates `${VERSION:-latest}`);
  k8s kept at `:latest` with `kubectl set image` documented for pinned deploys.
- Added `k8s/namespace.yaml` (`vrp-production`) and namespaced every manifest.
- Added `k8s/secret.example.yaml` (`vrp-env` — referenced by backend/redis/postgres).
- Added `.env.production.example` (parity with the k8s Secret).
- Added `k8s/README.md` with apply/rollout flow and an `emptyDir`→PVC note.
- YAML validated (pyyaml) and `docker compose config` passes.

### 6. Distributed tracing (51)
- Add OpenTelemetry FastAPI instrumentation, enabled via
  `OTEL_EXPORTER_OTLP_ENDPOINT` (opt-out by default).
- Correlate traces with the existing `X-Request-ID` / `request_id` contextvar.

### 7. Grafana dashboard + alerts (51)
- Commit dashboard JSON and Prometheus alert rules for: solver p95 latency,
  HTTP 5xx error rate, Redis unavailability.

### 8. Structured logging polish (52)
- Cover the structlog configuration with tests.
- Verify JSON output is always used in production path (LOG_FORMAT=json).
- Document `LOG_LEVEL` / `LOG_FORMAT` / `LOG_FILE` env vars.

## Verification

- Backend: `ruff check` + `ruff format` + `pytest` (with the documented env
  overrides `DATABASE_URL= REDIS_URL= ROUTING_BACKEND=haversine`).
- Frontend: `vitest run`, `eslint`, `prettier --check`, `vite build`.
- Infra: `docker compose -f docker-compose.{prod,monitoring}.yml config`
  and `kubectl apply --dry-run=client -f k8s/`.
- Per-item branches, committed in the repo's granular style.
