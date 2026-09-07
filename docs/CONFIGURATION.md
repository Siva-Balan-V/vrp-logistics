# Configuration Reference

Authoritative reference for every environment variable consumed by the
RouteForge/VRP stack.

Settings are read by the backend from `backend/app/config.py`
(pydantic-settings). Notes that apply to all backend variables:

- Variables are read from the environment and from the `.env` file
  (case-sensitive, uppercase only).
- `extra = "ignore"` — unexpected variables are silently ignored.
- `DATABASE_URL` and `REDIS_URL` are **optional**: the app runs without a
  database and without a cache (degraded modes). See each section below.
- Secrets are never logged. The Redis URL is scrubbed in logs.

> Backend vars in this doc map directly to fields on the pydantic `Settings`
> model; source of truth is `config.py` if the two ever disagree.

---

## Application

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `VRP Logistics Optimizer` | Display name used in API metadata |
| `APP_VERSION` | `1.0.0` | Version surfaced by `/health` |
| `DEBUG` | `false` | Enable debug behavior (e.g., stack traces) — keep `false` in prod |

## Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_FORMAT` | `console` | `console` (pretty structlog) or `json` (structured, for prod) |
| `LOG_FILE` | *(unset)* | Rotated file path, e.g. `/var/log/vrp/backend.log`. Unset = stdout only |

## Distributed tracing (OpenTelemetry)

Tracing is **completely disabled** unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set.

| Variable | Default | Description |
|----------|---------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | *(unset)* | OTLP gRPC collector, e.g. `http://localhost:4317`. Set to enable tracing |
| `OTEL_SERVICE_NAME` | `vrp-backend` | Service name reported to the collector |

## Routing

| Variable | Default | Description |
|----------|---------|-------------|
| `ROUTING_BACKEND` | `haversine` | `haversine` (built-in, offline) \| `osrm` \| `ors` |
| `OSRM_BASE_URL` | `http://router.project-osrm.org` | Base URL for the OSRM backend |
| `ORS_API_KEY` | *(empty)* | OpenRouteService API key. **Required** for `ors` backend and for traffic-aware routing |

## Redis (cache)

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | *(unset)* | e.g. `redis://:password@redis:6379/0`. Optional; unset = cache degraded (LRU-only fallback) |

> Docker compose sets `REDIS_PASSWORD` (service-level) and the backend builds
> `REDIS_URL` from it for the `vrp-redis` service.

## PostgreSQL (database)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | *(unset)* | e.g. `postgresql+asyncpg://postgres:pass@db:5432/vrp`. Optional; unset = jobs kept in-memory/Redis only and replan previous-job lookup uses the cache |

> Docker compose sets `POSTGRES_PASSWORD` (service-level) and the backend
> builds `DATABASE_URL` for the `vrp-postgres` service.

## JWT authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | *(empty)* | Signing secret. **Must be set and strong in production** — enforced with a startup warning otherwise |
| `JWT_ALGORITHM` | `HS256` | Signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access-token lifetime |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh-token lifetime |

## VRP solver

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_MAX_VEHICLES` | `18` | Default vehicle count cap |
| `DEFAULT_MAX_ROUTE_DURATION_SECONDS` | `9000` | 2.5-hour default route duration cap |
| `DEFAULT_VEHICLE_CAPACITY` | `50` | Default capacity per vehicle |
| `SOLVER_TIME_LIMIT_SECONDS` | `60` | OR-Tools solver time budget per request |

## Cost estimation

| Variable | Default | Description |
|----------|---------|-------------|
| `FUEL_COST_PER_KM` | `0.35` | $ per km (including maintenance) |
| `DRIVER_COST_PER_HOUR` | `25.0` | $ per hour |

## Billing

Stripe keys are legacy (replaced by Razorpay) but still read if present.

| Variable | Default | Description |
|----------|---------|-------------|
| `STRIPE_SECRET_KEY` | *(empty)* | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | *(empty)* | Stripe webhook signing secret |
| `STRIPE_PRICE_PRO` | *(empty)* | Pro plan price ID |
| `STRIPE_PRICE_ENTERPRISE` | *(empty)* | Enterprise plan price ID |
| `RAZORPAY_KEY_ID` | *(empty)* | Razorpay key id |
| `RAZORPAY_KEY_SECRET` | *(empty)* | Razorpay key secret |
| `RAZORPAY_WEBHOOK_SECRET` | *(empty)* | Razorpay webhook signing secret |

## Notifications

| Variable | Default | Description |
|----------|---------|-------------|
| `TWILIO_ACCOUNT_SID` | *(empty)* | Twilio account SID (SMS) |
| `TWILIO_AUTH_TOKEN` | *(empty)* | Twilio auth token |
| `TWILIO_FROM_NUMBER` | *(empty)* | Twilio sender number |
| `SMTP_HOST` | *(empty)* | SMTP server for email notifications |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | *(empty)* | SMTP username |
| `SMTP_PASSWORD` | *(empty)* | SMTP password |
| `SMTP_FROM_EMAIL` | *(empty)* | Sender address |

## Dispatch / stop lifecycle

| Variable | Default | Description |
|----------|---------|-------------|
| `NOTIFY_DELAY_THRESHOLD_MIN` | `15.0` | Live-ETA delay (minutes) that triggers a "delayed" notification |

## CORS & network

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOWED_ORIGINS` | `["http://localhost:5173", "http://localhost:3000"]` | Comma-delimited list of allowed origins (JSON list in the pydantic field) |
| `TRUST_PROXY_HEADERS` | `false` | Honor `X-Forwarded-For` only when behind a trusted proxy (affects rate limiting) |

## Batch processing

| Variable | Default | Description |
|----------|---------|-------------|
| `OSRM_BATCH_SIZE` | `100` | Max locations per OSRM batch request |
| `ORS_BATCH_SIZE` | `50` | Max locations per ORS batch request |

---

## Infrastructure / compose variables

These are consumed by docker-compose, deploy scripts, and the monitoring stack
rather than by the backend pydantic settings.

| Variable | Consumed by | Description |
|----------|-------------|-------------|
| `REDIS_PASSWORD` | docker-compose / deploy | Redis auth password (`vrp-redis` service) |
| `POSTGRES_PASSWORD` | docker-compose / deploy | Postgres superuser password (`vrp-postgres`) |
| `GRAFANA_ADMIN_PASSWORD` | `docker-compose.monitoring.yml` | Grafana admin password |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | backend | See tracing above |
| `DOCKER_REGISTRY` / `BACKEND_IMAGE` / `FRONTEND_IMAGE` | Jenkinsfile | GHCR image coordinates |

---

## Utility / reference files

| File | Purpose |
|------|---------|
| `.env.example` | Local development template |
| `.env.production.example` | Production template (mirrors the `vrp-env` k8s Secret) |
| `k8s/secret.example.yaml` | Template for the `vrp-env` Secret `stringData` (k8s only) |

See `docs/PRODUCTION_DEPLOYMENT.md` for wiring these into a real deployment.
