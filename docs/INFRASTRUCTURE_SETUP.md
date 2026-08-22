# Infrastructure Setup Guide

Complete step-by-step guide for provisioning all external services, configuring
the development environment, and deploying RouteForge to production.

---

## Table of Contents

1. [Overview & Service Map](#1-overview--service-map)
2. [Prerequisites](#2-prerequisites)
3. [Local Development Environment](#3-local-development-environment)
4. [PostgreSQL Database](#4-postgresql-database)
5. [Redis Cache](#5-redis-cache)
6. [Database Migrations (Alembic)](#6-database-migrations-alembic)
7. [JWT Authentication](#7-jwt-authentication)
8. [Routing APIs](#8-routing-apis)
9. [Stripe Billing (Optional)](#9-stripe-billing-optional)
10. [Twilio SMS Notifications](#10-twilio-sms-notifications)
11. [SMTP Email Notifications](#11-smtp-email-notifications)
12. [CI/CD with GitHub Actions](#12-cicd-with-github-actions)
13. [Production Deployment](#13-production-deployment)
14. [SSL / HTTPS](#14-ssl--https)
15. [Monitoring (Prometheus + Grafana)](#15-monitoring-prometheus--grafana)
16. [Backups](#16-backups)
17. [Environment Variable Reference](#17-environment-variable-reference)
18. [Troubleshooting](#18-troubleshooting)

---

## 1. Overview & Service Map

```
┌──────────────────────────────────────────────────────────────────┐
│                     EXTERNAL SERVICES MAP                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────────┐  │
│  │ PostgreSQL  │  │   Redis    │  │   Routing APIs           │  │
│  │ Port 5432   │  │ Port 6379  │  │  • OSRM (free public)   │  │
│  │ (5433 host) │  │            │  │  • ORS (API key)        │  │
│  │             │  │  Cache +   │  │  • Haversine (local)    │  │
│  │  Users,     │  │  Sessions  │  │                          │  │
│  │  Companies, │  │  + LRU     │  └──────────────────────────┘  │
│  │  Jobs, etc  │  │  fallback  │                                  │
│  └────────────┘  └────────────┘                                  │
│                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────────┐  │
│  │   Stripe   │  │   Twilio   │  │   SMTP Email             │  │
│  │  Billing   │  │  SMS       │  │  Gmail / SendGrid        │  │
│  │  (optional)│  │  (optional)│  │  (optional)              │  │
│  └────────────┘  └────────────┘  └──────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  GitHub Actions CI/CD  →  SSH Deploy  →  Docker Compose   │  │
│  │  Blue-Green Deployment with Nginx Router                   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Prometheus + Grafana + Node Exporter (monitoring)         │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Service Status Matrix

| Service | Required? | Code Implemented | Infra Setup |
|---------|-----------|-----------------|-------------|
| PostgreSQL | Recommended | ✅ | ✅ (Docker) |
| Redis | Optional (LRU fallback) | ✅ | ✅ (Docker) |
| JWT Auth | Yes (for user features) | ✅ | ✅ (config only) |
| Routing (haversine) | Yes (default) | ✅ | ✅ (no external dep) |
| Routing (OSRM) | Optional | ✅ | ✅ (public endpoint) |
| Routing (ORS) | Recommended | ✅ | ⚠️ (needs API key) |
| Stripe | Optional (SaaS billing) | ✅ | ❌ (needs account) |
| Twilio SMS | Optional | ✅ | ❌ (needs account) |
| SMTP Email | Optional | ✅ | ❌ (needs credentials) |
| CI/CD | Recommended | ✅ | ❌ (needs GitHub secrets) |
| Monitoring | Optional | ✅ | ❌ (needs Docker start) |

---

## 2. Prerequisites

### Local Development

- **Docker** ≥ 24.0 + **Docker Compose** ≥ 2.20
- **Python** 3.11+ (3.14 tested)
- **Node.js** 20+ (22 tested)
- **Git**

Verify your setup:

```bash
docker --version          # Docker version 24+
docker compose version    # Docker Compose version 2.20+
python3 --version         # Python 3.11+
node --version            # Node 20+
```

### Production Server

- **OS:** Ubuntu 22.04+ / Debian 12+ (or any Docker-compatible Linux)
- **RAM:** ≥ 2 GB (4 GB recommended)
- **Disk:** ≥ 20 GB free
- **Docker** installed (install script provided below)
- **SSH access** with key-based auth
- **Domain name** (optional, for SSL)

---

## 3. Local Development Environment

### Step 3.1 — Clone the Repository

```bash
git clone https://github.com/siva-balan-v/vrp-logistics.git
cd vrp-logistics
```

### Step 3.2 — Configure Environment Variables

Copy the example and customize:

```bash
cp .env.example .env
```

Open `.env` and configure the values. The full file with all sections:

```env
# ── App ──────────────────────────────────────────────────────────
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=console

# ── Routing ──────────────────────────────────────────────────────
ROUTING_BACKEND=haversine       # "haversine" | "osrm" | "ors"
ORS_API_KEY=                    # Get key at https://openrouteservice.org
OSRM_BASE_URL=http://router.project-osrm.org
SOLVER_TIME_LIMIT_SECONDS=60

# ── Redis ────────────────────────────────────────────────────────
REDIS_PASSWORD=vrp-dev-redis-2024
REDIS_URL=redis://:vrp-dev-redis-2024@localhost:6379/0

# ── PostgreSQL ───────────────────────────────────────────────────
POSTGRES_PASSWORD=vrp-dev-postgres-2024
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/vrp

# ── JWT ──────────────────────────────────────────────────────────
JWT_SECRET_KEY=<generate with: openssl rand -hex 32>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ── Cost Defaults ────────────────────────────────────────────────
FUEL_COST_PER_KM=0.35
DRIVER_COST_PER_HOUR=25.0

# ── Stripe (optional) ───────────────────────────────────────────
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_PRO=
STRIPE_PRICE_ENTERPRISE=

# ── Twilio SMS (optional) ───────────────────────────────────────
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_FROM_NUMBER=+1234567890

# ── SMTP Email (optional) ───────────────────────────────────────
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
```

Generate a secure JWT secret:

```bash
openssl rand -hex 32
```

### Step 3.3 — Create Backend Symlink for Alembic

Alembic runs from the `backend/` directory and reads `.env` from CWD. Create a symlink:

```bash
ln -sf ../.env backend/.env
```

### Step 3.4 — Start Infrastructure Services

```bash
docker compose up -d redis postgres
```

Verify both are healthy:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expected output:
```
NAMES          STATUS                    PORTS
vrp-redis      Up (healthy)              0.0.0.0:6379->6379/tcp
vrp-postgres   Up (healthy)              0.0.0.0:5433->5432/tcp
```

### Step 3.5 — Install Python Dependencies

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3.6 — Run Database Migrations

```bash
cd backend
alembic stamp 50e7a5c47b13    # Mark existing tables as baseline
alembic upgrade head           # Apply new migrations
```

### Step 3.7 — Start the Application

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

- **API docs:** http://localhost:8000/docs
- **Health check:** http://localhost:8000/health
- **Metrics:** http://localhost:8000/metrics

### Step 3.8 — Start Frontend (Development)

```bash
cd frontend
npm install
npm run dev
```

- **Frontend:** http://localhost:5173

### Step 3.9 — Full Stack via Docker Compose

To run everything in containers:

```bash
docker compose up -d --build
```

This starts:
- Backend on port 8000
- Frontend on port 5173
- Redis on port 6379
- Postgres on port 5433

---

## 4. PostgreSQL Database

### What It Stores

| Table | Purpose |
|-------|---------|
| `companies` | Tenant organizations, plan, Stripe customer ID |
| `users` | User accounts with bcrypt password hashes |
| `api_keys` | B2B API keys (SHA-256 hashed, with permissions) |
| `optimization_jobs` | VRP solve requests and results (JSONB) |
| `drivers` | Driver profiles with GPS tracking |
| `vehicle_routes` | Route details per vehicle per job |
| `locations` | Delivery locations per job |
| `notification_config` | Per-company SMS/email settings |
| `notification_log` | Notification delivery audit trail |

### Connection Details

| Setting | Dev Value |
|---------|-----------|
| Host | `localhost` (or `postgres` in Docker) |
| Port | `5433` (host) / `5432` (container) |
| Database | `vrp` |
| User | `postgres` |
| Password | Set in `.env` as `POSTGRES_PASSWORD` |

### Docker Service (from `docker-compose.yml`)

```yaml
postgres:
  image: postgres:16-alpine
  ports:
    - "5433:5432"
  environment:
    POSTGRES_DB: vrp
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  volumes:
    - postgres_data:/var/lib/postgresql/data
```

### Verify Connection

```bash
# From host
docker exec vrp-postgres psql -U postgres -d vrp -c "\dt"

# From Python
source backend/.venv/bin/activate
python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
async def test():
    engine = create_async_engine('postgresql+asyncpg://postgres:postgres@localhost:5433/vrp')
    async with engine.connect() as conn:
        result = await conn.execute(__import__('sqlalchemy').text('SELECT 1'))
        print('Connected:', result.scalar())
    await engine.dispose()
asyncio.run(test())
"
```

### Raw Schema

The initial schema is defined in `database/schema.sql`. It is applied manually
or by the Docker entrypoint on first run. Alembic manages subsequent migrations.

---

## 5. Redis Cache

### What It Caches

| Key Pattern | TTL | Purpose |
|-------------|-----|---------|
| `matrix:{sha256}` | 1 hour | Distance/duration matrices |
| `job:{job_id}` | 2 hours | Optimization job results |

### Fallback Behavior

When Redis is unavailable, the app falls back to an **in-process LRU cache**
(max 20 matrices, 200 jobs). Set `REDIS_URL=` (blank) to disable Redis entirely.

### Connection Details

| Setting | Dev Value |
|---------|-----------|
| Host | `localhost` (or `redis` in Docker) |
| Port | `6379` |
| Password | Set in `.env` as `REDIS_PASSWORD` |
| Database | `0` |
| URL | `redis://:password@localhost:6379/0` |

### Docker Service (from `docker-compose.yml`)

```yaml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  command: >
    redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    ${REDIS_PASSWORD:+--requirepass ${REDIS_PASSWORD}}
  volumes:
    - redis_data:/data
```

### Verify Connection

```bash
docker exec vrp-redis redis-cli -a vrp-dev-redis-2024 ping
# Expected: PONG
```

---

## 6. Database Migrations (Alembic)

### Migration History

| Revision | Description |
|----------|-------------|
| `50e7a5c47b13` | Initial — creates `api_keys` table |
| `a1b2c3d4e5f6` | Adds `drivers`, `notification_config`, `notification_log` tables; adds `company_id` to `optimization_jobs` and `driver_id` to `vehicle_routes` |

### Running Migrations

```bash
cd backend
source .venv/bin/activate

# If tables already exist from schema.sql, stamp baseline first:
alembic stamp 50e7a5c47b13

# Apply all pending migrations:
alembic upgrade head

# Check current version:
alembic current

# Rollback one step:
alembic downgrade -1
```

### Creating New Migrations

After modifying ORM models in `backend/app/models/db.py`:

```bash
cd backend
alembic revision --autogenerate -m "description_of_change"
alembic upgrade head
```

---

## 7. JWT Authentication

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `JWT_SECRET_KEY` | (must set) | HMAC signing key — **generate with `openssl rand -hex 32`** |
| `JWT_ALGORITHM` | `HS256` | Signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/auth/register` | Register new user + company |
| `POST` | `/api/v1/auth/login` | Login, returns access + refresh tokens |
| `POST` | `/api/v1/auth/refresh` | Refresh access token |
| `GET` | `/api/v1/auth/me` | Get current user profile |

### API Key Authentication

API keys provide B2B access with scoped permissions:

| Header | Format | Example |
|--------|--------|---------|
| `X-API-Key` | `rf_` prefix + random | `rf_AbCdEfGhIjKlMnOpQrStUvWxYz1234` |

Permissions: `optimize`, `read`

### Security Notes

- Passwords are hashed with **bcrypt** (cost factor 12)
- Access tokens are short-lived (30 min default)
- Refresh tokens allow silent re-authentication
- API keys are stored as **SHA-256 hashes** — only the prefix is stored in plaintext

---

## 8. Routing APIs

### Available Backends

| Backend | Accuracy | Speed | Cost | API Key Required |
|---------|----------|-------|------|-----------------|
| `haversine` | Good (1.35x correction) | Fastest | Free | No |
| `osrm` | Excellent | Medium | Free (rate-limited) | No |
| `ors` | Excellent | Medium | Free tier: 2000 req/day | Yes |

### Option A: Haversine (Default — No Setup)

Uses great-circle distance with a 1.35x road-network correction factor.
Works entirely locally with no external API calls.

```env
ROUTING_BACKEND=haversine
```

### Option B: OSRM (Free Public Server)

Uses the public OSRM demo server. Rate-limited for large jobs.

```env
ROUTING_BACKEND=osrm
OSRM_BASE_URL=http://router.project-osrm.org
```

For production, consider self-hosting OSRM (see below).

### Option C: OpenRouteService (Recommended for Production)

1. Sign up at https://openrouteservice.org/dev/#/signup
2. Copy your API key from the dashboard
3. Configure:

```env
ROUTING_BACKEND=ors
ORS_API_KEY=your_api_key_here
```

Free tier: 2000 requests/day, 40 requests/minute.

### Self-Hosted OSRM (Production)

```bash
docker run -d --name osrm -p 5000:5000 \
  -v /path/to/osrm-data:/data \
  ghcr.io/project-osrm/osrm-backend \
  osrm-routed --algorithm mld /data/india-latest.osrm
```

Update `.env`:
```env
ROUTING_BACKEND=osrm
OSRM_BASE_URL=http://localhost:5000
```

---

## 9. Stripe Billing (Optional)

> Only needed if you want subscription billing (Free / Pro / Enterprise tiers).

### Step 9.1 — Create Stripe Account

1. Go to https://dashboard.stripe.com/register
2. Complete account setup
3. Switch to **Test mode** for development

### Step 9.2 — Get API Keys

From the Stripe Dashboard → **Developers → API Keys**:

| Key | Where to Find |
|-----|---------------|
| Secret Key (`sk_test_...`) | API Keys page |
| Publishable Key (`pk_test_...`) | API Keys page (frontend) |

### Step 9.3 — Create Products & Prices

In Stripe Dashboard → **Products**:

1. Create product **"RouteForge Pro"**
   - Add price: **$49/month** (recurring)
   - Copy the **Price ID** (`price_...`)

2. Create product **"RouteForge Enterprise"**
   - Add price: **$199/month** (recurring)
   - Copy the **Price ID** (`price_...`)

### Step 9.4 — Configure Webhook

1. Go to **Developers → Webhooks → Add endpoint**
2. URL: `https://yourdomain.com/api/v1/webhooks/stripe`
3. Select events:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. Copy the **Webhook Signing Secret** (`whsec_...`)

### Step 9.5 — Update `.env`

```env
STRIPE_SECRET_KEY=sk_test_xxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx
STRIPE_PRICE_PRO=price_xxxxxxxxxxxxx
STRIPE_PRICE_ENTERPRISE=price_xxxxxxxxxxxxx
```

### Billing Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/billing/plans` | List available plans |
| `GET` | `/api/v1/billing/usage` | Current usage |
| `POST` | `/api/v1/billing/create-checkout` | Create Stripe checkout session |
| `POST` | `/api/v1/billing/portal` | Customer portal for subscription management |
| `POST` | `/api/v1/webhooks/stripe` | Stripe webhook handler |

---

## 10. Twilio SMS Notifications

> Enables SMS delivery notifications to drivers (out_for_delivery, arrived, delayed).

### Step 10.1 — Create Twilio Account

1. Go to https://www.twilio.com/try-twilio
2. Sign up for a free trial (~$15 credit)
3. Verify your email and phone number

### Step 10.2 — Get Credentials

From the **Twilio Console** (https://console.twilio.com):

| Credential | Value |
|------------|-------|
| Account SID | Starts with `AC...` |
| Auth Token | Click "Show" to reveal |

### Step 10.3 — Buy a Phone Number

1. Go to **Phone Numbers → Buy a Number**
2. Search for a number in your region
3. Ensure it supports **SMS**
4. Click **Buy**
5. Copy the number (e.g., `+15551234567`)

### Step 10.4 — Update `.env`

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_FROM_NUMBER=+15551234567
```

### Step 10.5 — Per-Company Override

Companies can configure their own Twilio credentials via the API:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/notifications/config` | Set per-company SMS/email config |
| `GET` | `/api/v1/notifications/config` | Get current config |
| `POST` | `/api/v1/notifications/trigger` | Manually trigger a notification |

When `TWILIO_ACCOUNT_SID` is blank in `.env`, notifications are logged to
console instead of sent (useful for development).

---

## 11. SMTP Email Notifications

> Enables email delivery notifications (out_for_delivery, arrived, delayed).

### Option A: Gmail SMTP (Development)

1. Enable **2-Step Verification** on your Google Account
2. Go to https://myaccount.google.com/apppasswords
3. Generate a new app password:
   - App: **Mail**
   - Device: **Other (Custom name)** → "RouteForge"
4. Copy the 16-character password

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx
SMTP_FROM_EMAIL=your_email@gmail.com
```

### Option B: SendGrid (Production)

1. Sign up at https://sendgrid.com (free: 100 emails/day)
2. Go to **Settings → API Keys → Create API Key**
3. Verify a **Single Sender** email address
4. Configure:

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your_sendgrid_api_key
SMTP_FROM_EMAIL=verified@yourdomain.com
```

### Option C: AWS SES

```env
SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=your_ses_smtp_username
SMTP_PASSWORD=your_ses_smtp_password
SMTP_FROM_EMAIL=noreply@yourdomain.com
```

### Fallback Behavior

When SMTP settings are blank, the app uses `LogOnlyEmailProvider` which logs
email content to the console — no actual emails are sent.

---

## 12. CI/CD with GitHub Actions

### Pipeline Overview

```
  Push/PR to develop/main
         │
         ▼
  ┌──────────────────────────────────────────────┐
  │              CI Pipeline (ci.yml)             │
  │                                              │
  │  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
  │  │ Backend  │  │ Backend  │  │  Docker   │  │
  │  │ Lint     │  │ Tests    │  │  Build    │  │
  │  │ (Ruff)   │  │ (pytest) │  │  Check    │  │
  │  └──────────┘  └──────────┘  └───────────┘  │
  │  ┌──────────┐  ┌──────────┐                 │
  │  │ Frontend │  │ Frontend │                 │
  │  │ Lint     │  │ Test +   │                 │
  │  │ (ESLint) │  │ Build    │                 │
  │  └──────────┘  └──────────┘                 │
  └──────────────────────────────────────────────┘

  Push to main / tag v* / manual trigger
         │
         ▼
  ┌──────────────────────────────────────────────┐
  │           Deploy Pipeline (deploy.yml)        │
  │                                              │
  │  1. Build Docker images                      │
  │  2. Push to GitHub Container Registry (GHCR) │
  │  3. SSH into server                          │
  │  4. Run blue-green deploy script             │
  └──────────────────────────────────────────────┘
```

### Step 12.1 — CI Pipeline (Automatic)

The CI pipeline requires **no secrets** — it runs linting and tests on every push.

Triggers:
- Push to `develop` or `main`
- Pull requests to `develop` or `main`

### Step 12.2 — Deploy Pipeline (Needs Secrets)

Go to your GitHub repo → **Settings → Secrets and variables → Actions**:

| Secret Name | Required | Description |
|-------------|----------|-------------|
| `DEPLOY_HOST` | Yes | Server IP or hostname |
| `DEPLOY_USER` | Yes | SSH username (e.g., `deploy`) |
| `DEPLOY_SSH_KEY` | Yes | Full SSH private key content |
| `DEPLOY_PORT` | No | SSH port (default: `22`) |
| `DEPLOY_PATH` | Yes | Repo path on server (e.g., `/home/deploy/vrp-logistics`) |
| `REDIS_PASSWORD` | Yes | Production Redis password |
| `POSTGRES_PASSWORD` | Yes | Production Postgres password |

### Step 12.3 — Generate Deployment SSH Key

On your local machine:

```bash
# Generate a dedicated deploy key
ssh-keygen -t ed25519 -C "vrp-deploy" -f ~/.ssh/vrp-deploy -N ""

# Copy public key to server
ssh-copy-id -i ~/.ssh/vrp-deploy deploy@your.server.ip
```

Copy the **private key** content (`cat ~/.ssh/vrp-deploy`) into the
`DEPLOY_SSH_KEY` GitHub secret.

### Step 12.4 — GitHub Container Registry

The deploy workflow pushes images to GHCR. Ensure the repo has package
publish permissions:

1. Go to repo **Settings → Actions → General**
2. Under **Workflow permissions**, select **"Read and write permissions"**
3. Save

Images are pushed as:
- `ghcr.io/siva-balan-v/vrp-backend:latest`
- `ghcr.io/siva-balan-v/vrp-frontend:latest`

---

## 13. Production Deployment

### Architecture

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

### Step 13.1 — Server Setup

SSH into your production server:

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

### Step 13.2 — Deploy Application Code

```bash
# Clone the repo
cd /home/deploy
git clone https://github.com/siva-balan-v/vrp-logistics.git
cd vrp-logistics

# Create required directories
mkdir -p /var/lib/vrp
echo "blue" > /var/lib/vrp/active-color

# Make scripts executable
chmod +x scripts/deploy.sh scripts/backup.sh
```

### Step 13.3 — Create Production Environment File

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

# ── Stripe (fill in if using billing) ───────────────────
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_PRO=
STRIPE_PRICE_ENTERPRISE=

# ── Twilio (fill in if using SMS) ───────────────────────
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=

# ── SMTP (fill in if using email) ───────────────────────
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

### Step 13.4 — First Deployment

```bash
cd /home/deploy/vrp-logistics

# Deploy with your chosen passwords
REDIS_PASSWORD=your-secure-redis-password \
POSTGRES_PASSWORD=your-secure-postgres-password \
bash scripts/deploy.sh latest
```

The deploy script will:
1. Start shared infrastructure (Redis + Postgres)
2. Pull/build Docker images for the inactive color
3. Run Alembic migrations
4. Health-check the backend (30 attempts, 5s interval)
5. Flip the Nginx router to the new color
6. Stop the old color stack

### Step 13.5 — Verify Deployment

```bash
# Check all containers
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Test health endpoint
curl http://localhost/health

# Check API docs
curl -s http://localhost/docs | head -5
```

### Step 13.6 — Subsequent Deployments

Push to `main` triggers the deploy workflow automatically. For manual deploys:

```bash
cd /home/deploy/vrp-logistics
git pull --ff-only
REDIS_PASSWORD=xxx POSTGRES_PASSWORD=xxx bash scripts/deploy.sh latest
```

### Blue-Green Rollback

If the new version has issues, flip back to the old color:

```bash
# Check which color is active
cat /var/lib/vrp/active-color

# Swap the color
ACTIVE=$(cat /var/lib/vrp/active-color)
case "$ACTIVE" in
  blue)  NEW="green" ;;
  green) NEW="blue" ;;
esac

# Flip the router
sed "s/__FRONTEND_SERVICE__/vrp-frontend-${NEW}/" \
  deploy/router/router.conf.template > deploy/router/router.conf
docker compose -p vrp-router -f docker-compose.router.yml up -d --force-recreate

echo "$NEW" > /var/lib/vrp/active-color
```

---

## 14. SSL / HTTPS

### Using Let's Encrypt (Recommended)

```bash
# Install certbot
apt install certbot

# Stop the router temporarily
docker compose -p vrp-router -f docker-compose.router.yml down

# Get certificate
certbot certonly --standalone -d yourdomain.com

# Certificates are at:
# /etc/letsencrypt/live/yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/yourdomain.com/privkey.pem
```

Mount certificates into the Nginx router. Edit `docker-compose.router.yml`:

```yaml
services:
  router:
    volumes:
      - ./deploy/router/router.conf:/etc/nginx/conf.d/router.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
```

Update `deploy/router/router.conf.template` to uncomment the HTTPS server block
and update the SSL certificate paths.

### Auto-Renewal

```bash
# Add to crontab
0 0 1 * * certbot renew --pre-hook "docker compose -p vrp-router -f /home/deploy/vrp-logistics/docker-compose.router.yml down" --post-hook "docker compose -p vrp-router -f /home/deploy/vrp-logistics/docker-compose.router.yml up -d"
```

---

## 15. Monitoring (Prometheus + Grafana)

### Start the Monitoring Stack

```bash
cd /home/deploy/vrp-logistics

# Set Grafana admin password
export GRAFANA_ADMIN_PASSWORD=your-secure-password

docker compose -f docker-compose.monitoring.yml up -d
```

### Access Dashboards

| Service | URL | Credentials |
|---------|-----|-------------|
| Prometheus | `http://your-server:9090` | None |
| Grafana | `http://your-server:3000` | admin / (your password) |
| Node Exporter | `http://your-server:9100` | None |

### Available Metrics

The backend exposes these at `GET /metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `vrp_http_requests_total` | Counter | Total HTTP requests |
| `vrp_http_request_duration_seconds` | Histogram | Request latency |
| `vrp_http_requests_in_flight` | Gauge | Currently processing |
| `vrp_solver_duration_seconds` | Histogram | OR-Tools solver time |
| `vrp_solver_results_total` | Counter | Solver outcomes |

### Create Grafana Dashboard

1. Login to Grafana → **Dashboards → New**
2. Add a new **Prometheus** datasource (URL: `http://prometheus:9090`)
3. Create panels using the metrics above

Sample PromQL queries:

```promql
# Request rate (per second)
rate(vrp_http_requests_total[5m])

# P95 latency
histogram_quantile(0.95, rate(vrp_http_request_duration_seconds_bucket[5m]))

# Solver duration P99
histogram_quantile(0.99, rate(vrp_solver_duration_seconds_bucket[5m]))

# Active requests
vrp_http_requests_in_flight
```

### Resource Limits (Production)

From `docker-compose.monitoring.yml`:

| Service | CPU Limit | Memory Limit |
|---------|-----------|-------------|
| Prometheus | 0.5 CPU | 512 MB |
| Grafana | 0.5 CPU | 256 MB |
| Node Exporter | 0.1 CPU | 128 MB |

---

## 16. Backups

### Manual Backup

```bash
cd /home/deploy/vrp-logistics
./scripts/backup.sh

# Options:
#   --db-only        PostgreSQL only
#   --redis-only     Redis only
#   --retention 14   Keep 14 days (default: 7)
```

### Backup Output

```
backups/
├── vrp-db-20260818-023000.sql.gz      # PostgreSQL logical dump
└── vrp-redis-20260818-023000.rdb.gz   # Redis RDB snapshot
```

### Automated Daily Backups

```bash
# Edit crontab
crontab -e

# Add (runs daily at 2:30 AM, keeps 14 days):
30 2 * * * cd /home/deploy/vrp-logistics && \
  REDIS_PASSWORD=xxx POSTGRES_PASSWORD=xxx \
  ./scripts/backup.sh --retention 14 \
  >> /var/log/vrp-backup.log 2>&1
```

### Restore PostgreSQL

```bash
# Decompress and restore
gunzip -c backups/vrp-db-*.sql.gz | \
  docker exec -i vrp-postgres pg_restore -U postgres -d vrp --clean --if-exists
```

See `docs/DISASTER_RECOVERY.md` for full restore procedures.

---

## 17. Environment Variable Reference

### Application Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_NAME` | No | `VRP Logistics Optimizer` | Application name |
| `APP_VERSION` | No | `1.0.0` | Version string |
| `DEBUG` | No | `false` | Debug mode |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `LOG_FORMAT` | No | `console` | `console` or `json` |
| `LOG_FILE` | No | (none) | Log file path (rotated) |

### Routing Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ROUTING_BACKEND` | Yes | `haversine` | `haversine`, `osrm`, or `ors` |
| `ORS_API_KEY` | Conditional | (empty) | OpenRouteService API key |
| `OSRM_BASE_URL` | No | `http://router.project-osrm.org` | OSRM server URL |
| `OSRM_BATCH_SIZE` | No | `100` | Max locations per OSRM request |
| `ORS_BATCH_SIZE` | No | `50` | Max locations per ORS request |

### Infrastructure Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | No | (none) | Redis connection URL |
| `REDIS_PASSWORD` | No | (empty) | Redis password (Docker only) |
| `DATABASE_URL` | No | (none) | PostgreSQL connection URL |
| `POSTGRES_PASSWORD` | No | (empty) | PostgreSQL password (Docker only) |

### Authentication Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET_KEY` | Yes | (empty) | HMAC signing key |
| `JWT_ALGORITHM` | No | `HS256` | JWT algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | Access token lifetime |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | Refresh token lifetime |

### Stripe Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `STRIPE_SECRET_KEY` | No | (empty) | Stripe API secret key |
| `STRIPE_WEBHOOK_SECRET` | No | (empty) | Stripe webhook signing secret |
| `STRIPE_PRICE_PRO` | No | (empty) | Price ID for Pro plan |
| `STRIPE_PRICE_ENTERPRISE` | No | (empty) | Price ID for Enterprise plan |

### Notification Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TWILIO_ACCOUNT_SID` | No | (empty) | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | No | (empty) | Twilio auth token |
| `TWILIO_FROM_NUMBER` | No | (empty) | Twilio phone number |
| `SMTP_HOST` | No | (empty) | SMTP server hostname |
| `SMTP_PORT` | No | `587` | SMTP server port |
| `SMTP_USER` | No | (empty) | SMTP username |
| `SMTP_PASSWORD` | No | (empty) | SMTP password |
| `SMTP_FROM_EMAIL` | No | (empty) | Sender email address |

### Solver Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SOLVER_TIME_LIMIT_SECONDS` | No | `60` | OR-Tools time limit |
| `DEFAULT_MAX_VEHICLES` | No | `18` | Max vehicles per job |
| `DEFAULT_MAX_ROUTE_DURATION_SECONDS` | No | `9000` | Max route duration (2.5h) |
| `DEFAULT_VEHICLE_CAPACITY` | No | `50` | Vehicle capacity |
| `FUEL_COST_PER_KM` | No | `0.35` | Cost per km for estimates |
| `DRIVER_COST_PER_HOUR` | No | `25.0` | Driver hourly cost |

### CORS Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ALLOWED_ORIGINS` | No | `["http://localhost:5173", "http://localhost:3000"]` | Allowed CORS origins |

### Docker Compose Variables

| Variable | Used By | Description |
|----------|---------|-------------|
| `IMAGE_TAG` | `docker-compose.prod.yml` | Docker image tag to deploy |
| `COLOR` | `docker-compose.prod.yml` | Blue or green stack |
| `PROMETHEUS_RETENTION` | `docker-compose.monitoring.yml` | Data retention (default: 30d) |
| `GRAFANA_ADMIN_USER` | `docker-compose.monitoring.yml` | Grafana admin username |
| `GRAFANA_ADMIN_PASSWORD` | `docker-compose.monitoring.yml` | Grafana admin password |

### GitHub Actions Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `GITHUB_TOKEN` | Auto | GHCR login (automatic) |
| `DEPLOY_HOST` | Yes | Server IP/hostname |
| `DEPLOY_USER` | Yes | SSH username |
| `DEPLOY_SSH_KEY` | Yes | SSH private key |
| `DEPLOY_PORT` | No | SSH port (default: 22) |
| `DEPLOY_PATH` | Yes | Repo path on server |
| `REDIS_PASSWORD` | Yes | Production Redis password |
| `POSTGRES_PASSWORD` | Yes | Production Postgres password |

---

## 18. Troubleshooting

### Containers Won't Start

```bash
# Check logs
docker logs vrp-postgres --tail 50
docker logs vrp-redis --tail 50

# Check if ports are in use
ss -tlnp | grep -E ':(5433|6379|8000|5173)'

# Recreate containers
docker compose down
docker compose up -d redis postgres
```

### Database Connection Refused

```bash
# Verify Postgres is listening
docker exec vrp-postgres pg_isready -U postgres

# Test connection from host
docker exec vrp-postgres psql -U postgres -d vrp -c "SELECT 1"

# Check port mapping
docker port vrp-postgres
```

### Alembic Migration Errors

```bash
# Check current version
cd backend && source .venv/bin/activate
alembic current

# If tables exist but Alembic version is missing:
alembic stamp 50e7a5c47b13

# Then apply pending migrations:
alembic upgrade head

# Check migration history
alembic history
```

### Redis Connection Issues

```bash
# Test with password
docker exec vrp-redis redis-cli -a your-password ping

# Check Redis logs
docker logs vrp-redis --tail 20

# Test from Python
python -c "
import redis
r = redis.Redis(host='localhost', port=6379, password='your-password')
print(r.ping())
"
```

### Backend Startup Failures

```bash
# Check backend logs
docker logs vrp-backend --tail 50

# Common issues:
# 1. DATABASE_URL pointing to wrong port (5433 on host, 5432 in Docker)
# 2. JWT_SECRET_KEY is empty
# 3. Redis password mismatch
```

### Deploy Script Failures

```bash
# Check deploy logs
cat /var/log/vrp-backup.log

# Manual health check
docker compose -p vrp-blue -f docker-compose.prod.yml exec -T backend \
  python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Check active color
cat /var/lib/vrp/active-color

# Force flip to a specific color
echo "blue" > /var/lib/vrp/active-color
sed "s/__FRONTEND_SERVICE__/vrp-frontend-blue/" \
  deploy/router/router.conf.template > deploy/router/router.conf
docker compose -p vrp-router -f docker-compose.router.yml up -d --force-recreate
```

### Notification Fallback Behavior

When Twilio or SMTP credentials are not configured, the app falls back to
log-only providers:

| Channel | Fallback | Output |
|---------|----------|--------|
| SMS | `LogOnlySMSProvider` | Logs message content to console |
| Email | `LogOnlyEmailProvider` | Logs email content to console |

No errors are thrown — the app functions normally without external notification
services.

---

## Quick Reference: Service Ports

| Service | Host Port | Container Port | Protocol |
|---------|-----------|---------------|----------|
| Backend API | 8000 | 8000 | HTTP |
| Frontend | 5173 | 80 | HTTP |
| PostgreSQL | 5433 | 5432 | TCP |
| Redis | 6379 | 6379 | TCP |
| Prometheus | 9090 | 9090 | HTTP |
| Grafana | 3000 | 3000 | HTTP |
| Node Exporter | 9100 | 9100 | HTTP |
| Nginx Router (prod) | 80/443 | 80/443 | HTTP/HTTPS |
