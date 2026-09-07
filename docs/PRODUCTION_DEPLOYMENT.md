# Production Deployment Runbook

This runbook consolidates production deployment, CI/CD, SSL, monitoring, and
disaster recovery for the RouteForge/VRP logistics stack. It is the operational
home for material previously split across three documents:

| Original document | Content coverage here |
|-------------------|-----------------------|
| `docs/INFRASTRUCTURE_SETUP.md` | Blue-green deploy, SSL, monitoring (§2–§6) |
| `docs/JENKINS_SETUP.md` | CI/CD pipeline, plugins, credentials (§7) |
| `docs/DISASTER_RECOVERY.md` | Backups and restore (§6) |

The original files remain in `docs/` with their full detail; the sections below
link to them where a task has more depth. Refer to `docs/CONFIGURATION.md` for
the authoritative environment-variable reference.

---

## Table of contents

1. [Deployment architecture](#1-deployment-architecture)
2. [Blue-green deploy](#2-blue-green-deploy)
3. [SSL / HTTPS](#3-ssl--https)
4. [Monitoring](#4-monitoring)
5. [Kubernetes option](#5-kubernetes-option)
6. [Backups & disaster recovery](#6-backups--disaster-recovery)
7. [CI/CD with Jenkins](#7-cicd-with-jenkins)
8. [Manual deployment](#8-manual-deployment)

---

## 1. Deployment architecture

```
                    Internet
                       │
                       ▼
              ┌─────────────────┐
              │  Nginx Router   │
              │  (Port 80/443)  │
              └────────┬────────┘
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
    ┌───────────────┐    ┌───────────────┐
    │  vrp-blue     │    │  vrp-green    │
    │  (backend +   │    │  (backend +   │
    │   frontend)   │    │   frontend)   │
    └───────┬───────┘    └───────┬───────┘
            │                     │
            └──────────┬──────────┘
                       │ vrp-net
            ┌──────────┴──────────┐
            ▼                     ▼
    ┌───────────────┐    ┌───────────────┐
    │  PostgreSQL   │    │    Redis      │
    │  (shared)     │    │  (shared)     │
    └───────────────┘    └───────────────┘
```

The router runs Nginx as the single entry point. Two color stacks (`blue` /
`green`) run backend + frontend against shared Postgres and Redis, enabling
zero-downtime swaps.

## 2. Blue-green deploy

### 2.1 Initial server setup

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

### 2.2 Clone and prepare

```bash
cd /home/deploy
git clone https://github.com/siva-balan-v/vrp-logistics.git
cd vrp-logistics

mkdir -p /var/lib/vrp
echo "blue" > /var/lib/vrp/active-color

chmod +x scripts/deploy.sh scripts/backup.sh
```

### 2.3 Production environment file

```bash
cat > .env.production << 'ENVEOF'
# ── Routing ──────────────────────────────────────────────
ROUTING_BACKEND=haversine
ORS_API_KEY=
OSRM_BASE_URL=http://router.project-osrm.org

# ── Solver ───────────────────────────────────────────────
SOLVER_TIME_LIMIT_SECONDS=60

# ── JWT ──────────────────────────────────────────────────
JWT_SECRET_KEY=$(openssl rand -hex 32)
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ── Billing (fill in if using billing) ─────────────────
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_PRO=
STRIPE_PRICE_ENTERPRISE=

# ── SMS (fill in if using Twilio) ──────────────────────
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=

# ── Email (fill in if using SMTP) ──────────────────────
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=

# ── App ──────────────────────────────────────────────────
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json
ENVEOF
```

The full set of variables, including optional OpenTelemetry tracing
(`OTEL_EXPORTER_OTLP_ENDPOINT`) and Razorpay billing keys, is documented in
`docs/CONFIGURATION.md` and mirrored in `.env.production.example`.

### 2.4 Deploy

```bash
cd /home/deploy/vrp-logistics

# First deployment (pass your chosen passwords)
REDIS_PASSWORD=your-secure-redis-password \
POSTGRES_PASSWORD=your-secure-postgres-password \
bash scripts/deploy.sh latest
```

`scripts/deploy.sh` performs the following steps:

1. Start shared infrastructure (Redis + Postgres).
2. Pull/build Docker images for the **inactive** color.
3. Run Alembic migrations (the backend also runs `upgrade head` at startup).
4. Health-check the backend (30 attempts, 5s interval).
5. Flip the Nginx router to the new color.
6. Stop the old color stack.

Subsequent deployments (usually triggered by CI on push to `main`):

```bash
cd /home/deploy/vrp-logistics
git pull --ff-only
REDIS_PASSWORD=xxx POSTGRES_PASSWORD=xxx bash scripts/deploy.sh latest
```

### 2.5 Verify

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
curl http://localhost/health
curl -s http://localhost/docs | head -5
```

### 2.6 Blue-green rollback

```bash
cat /var/lib/vrp/active-color

ACTIVE=$(cat /var/lib/vrp/active-color)
case "$ACTIVE" in
  blue)  NEW="green" ;;
  green) NEW="blue" ;;
esac

sed "s/__FRONTEND_SERVICE__/vrp-frontend-${NEW}/" \
  deploy/router/router.conf.template > deploy/router/router.conf
docker compose -p vrp-router -f docker-compose.router.yml up -d --force-recreate

echo "$NEW" > /var/lib/vrp/active-color
```

## 3. SSL / HTTPS

```bash
apt install certbot

# Stop the router temporarily
docker compose -p vrp-router -f docker-compose.router.yml down

# Get certificate
certbot certonly --standalone -d yourdomain.com
# Certificates at:
# /etc/letsencrypt/live/yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/yourdomain.com/privkey.pem
```

Mount the certificates into the router and enable HTTPS in
`deploy/router/router.conf.template`.

Auto-renewal (crontab):

```bash
0 0 1 * * certbot renew --pre-hook "docker compose -p vrp-router -f /home/deploy/vrp-logistics/docker-compose.router.yml down" --post-hook "docker compose -p vrp-router -f /home/deploy/vrp-logistics/docker-compose.router.yml up -d"
```

## 4. Monitoring

### 4.1 Start the stack

```bash
cd /home/deploy/vrp-logistics
export GRAFANA_ADMIN_PASSWORD=your-secure-password
docker compose -f docker-compose.monitoring.yml up -d
```

### 4.2 Dashboards

| Service | URL | Credentials |
|---------|-----|-------------|
| Prometheus | `http://your-server:9090` | None |
| Grafana | `http://your-server:3000` | admin / (your password) |
| Node Exporter | `http://your-server:9100` | None |

A provisioned **VRP Overview** dashboard and Prometheus alert rules are loaded
from the monitoring compose file (see Phase 7). Key backend metrics at
`GET /metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `vrp_http_requests_total` | Counter | Total HTTP requests |
| `vrp_http_request_duration_seconds` | Histogram | Request latency |
| `vrp_http_requests_in_flight` | Gauge | Currently processing |
| `vrp_solver_duration_seconds` | Histogram | OR-Tools solver time |
| `vrp_solver_results_total` | Counter | Solver outcomes |
| `vrp_redis_connected` | Gauge | Cache availability |

### 4.3 Resource limits

| Service | CPU Limit | Memory Limit |
|---------|-----------|-------------|
| Prometheus | 0.5 CPU | 512 MB |
| Grafana | 0.5 CPU | 256 MB |
| Node Exporter | 0.1 CPU | 128 MB |

## 5. Kubernetes option

The stack can also be deployed to Kubernetes under the `vrp-production`
namespace (see `k8s/README.md` for the full guide). Summary:

```sh
# Create the vrp-env Secret (see secret.example.yaml) then apply in order
kubectl apply -f namespace.yaml
kubectl apply -f secret.yaml
kubectl apply -f infrastructure.yaml   # redis + postgres
kubectl apply -f backend.yaml          # backend + service + HPA
kubectl apply -f frontend.yaml         # frontend + service + ingress
```

Migrations run automatically at backend startup
(`alembic upgrade head`), so no separate migration job is required.

## 6. Backups & disaster recovery

This section condenses `docs/DISASTER_RECOVERY.md`; see that file for the full
runbook, including a complete restore-drill walkthrough.

| Component | Method | Frequency | Storage |
|-----------|--------|-----------|---------|
| PostgreSQL | Logical dump (`pg_dump` custom format, gzip) | Daily (cron) | `backups/vrp-db-*.sql.gz` |
| Redis | RDB snapshot via `BGSAVE` | Daily (cron) | `backups/vrp-redis-*.rdb.gz` |
| Redis (live) | AOF enabled (`--appendonly yes --appendfsync everysec`) | Continuous | container volume `redis_data` |

Redis holds ephemeral distance matrices only; Postgres holds the durable state
(users, companies, jobs, api keys).

**Backup script:**

```bash
./scripts/backup.sh                    # full backup
./scripts/backup.sh --db-only          # Postgres only
./scripts/backup.sh --redis-only       # Redis only
./scripts/backup.sh --retention 14     # keep 14 backups (default 7)
```

**Automated daily backups** — add to root crontab:

```cron
30 2 * * * cd /opt/vrp-logistics && ./scripts/backup.sh --retention 14 >> /var/log/vrp-backup.log 2>&1
```

**Restore PostgreSQL:**

```bash
docker compose stop backend
gunzip -c backups/vrp-db-<TIMESTAMP>.sql.gz \
  | docker exec -i vrp-postgres pg_restore -U postgres -d vrp --clean --if-exists
docker compose start backend
```

**Restore Redis:**

```bash
gunzip -c backups/vrp-redis-<TIMESTAMP>.rdb.gz > /tmp/dump.rdb
docker cp /tmp/dump.rdb vrp-redis:/data/dump.rdb
docker restart vrp-redis
```

**Verify a backup:**

```bash
ls -lh backups/
gunzip -c backups/vrp-db-<TIMESTAMP>.sql.gz \
  | docker exec -i vrp-postgres pg_restore -U postgres -l
```

> Backups are local-only by default. Copy `backups/` off-box (S3/object
> storage/another host) for real durability.

## 7. CI/CD with Jenkins

Full Jenkins installation steps are in `docs/JENKINS_SETUP.md`. Summary:

- **Server**: Ubuntu 22.04/24.04 or Debian 12 with Docker, Java 17
  (`openjdk-17-jre-headless`), Git, Python 3.11+, Node 20+.
- **Install**: add the Jenkins Debian repo, install the `jenkins` package,
  start via `systemctl`, and read the initial admin password from
  `/var/lib/jenkins/secrets/initialAdminPassword`.
- **Plugins**: `Pipeline`, `Docker Pipeline`, `Git`.
- **Registry credentials**: add a **Username with password** credential (id
  `docker-registry`) using your GitHub username + a Personal Access Token with
  `write:packages` / `read:packages` scopes.
- **Pipeline job**: repo `https://github.com/siva-balan-v/vrp-logistics.git`,
  branch `*/main` (or `*/develop`), script path `Jenkinsfile`.

Pipeline stages (from `Jenkinsfile`):

| Stage | What it does |
|-------|--------------|
| Checkout | Pulls code from GitHub |
| Backend Lint | Runs `ruff check .` on Python code |
| Backend Tests | Runs `pytest -v` |
| Frontend Lint | Runs `npm run lint` (ESLint) |
| Frontend Tests | Runs `npm test` |
| Frontend Build | Runs `npm run build` |
| Docker Build & Push | Builds images, pushes to GHCR |
| Deploy | Runs `docker compose pull && docker compose up -d` |

Environment variables for images:
- `DOCKER_REGISTRY` = `ghcr.io/siva-balan-v`
- `BACKEND_IMAGE` = `ghcr.io/siva-balan-v/vrp-backend`
- `FRONTEND_IMAGE` = `ghcr.io/siva-balan-v/vrp-frontend`

**Common Jenkins fixes:**

```bash
# Docker command not found
sudo usermod -aG docker jenkins && sudo systemctl restart jenkins

# Permission denied on build files
sudo chown -R jenkins:jenkins /var/lib/jenkins/workspace/

# Port 8080 busy — change HTTP_PORT in /etc/default/jenkins

# View logs
sudo journalctl -u jenkins -f
```

> A GitHub Actions deploy workflow also exists and triggers on push to `main`;
> it uses a dedicated deploy SSH key generated per `docs/INFRASTRUCTURE_SETUP.md`
> §12.3.

## 8. Manual deployment

Without CI, deploy manually:

```bash
cd /path/to/vrp-logistics

# Pull latest images
docker compose pull

# Restart with new images
docker compose up -d --force-recreate

# Check status / logs
docker compose ps
docker compose logs -f backend
```

---

## Troubleshooting quick reference

| Issue | Fix |
|-------|-----|
| Backend won't start | Check logs; `DATABASE_URL` port (5433 host / 5432 in Docker); `JWT_SECRET_KEY` empty; Redis password mismatch |
| DB connection refused | Confirm Postgres listening; test from host; check port mapping |
| Alembic migration errors | Check `alembic current`; if tables exist but version missing, stamp baseline then upgrade |
| Redis connection issues | Test `PING` with password; check Redis logs; test from Python |
| Deploy script failures | Check deploy logs; health endpoint; flip router to known-good color |

Service ports: backend `8000`, frontend `5173` (dev), Postgres `5433` (host) /
`5432` (container), Redis `6379`, Prometheus `9090`, Grafana `3000`, Nginx
`80`/`443`, Jenkins `8080`.

---

## Related documents

- `docs/INFRASTRUCTURE_SETUP.md` — full local + production setup walkthrough.
- `docs/JENKINS_SETUP.md` — step-by-step Jenkins installation.
- `docs/DISASTER_RECOVERY.md` — complete backup/restore runbook with drill.
- `docs/CONFIGURATION.md` — environment-variable reference.
- `k8s/README.md` — Kubernetes deployment guide.
