# RouteForge — Business Launch Roadmap

This roadmap transforms RouteForge from a demo/prototype into a production-ready SaaS product. Organized into 6 milestones, each delivering standalone value.

**Current state:** Working VRP solver with React frontend, FastAPI backend, Docker deployment. No auth, no persistence, no multi-tenancy.

---

## Milestone 1: Data Persistence & User Accounts (2-3 weeks)

Foundation for everything else. Without this, nothing is production-viable.

### 1.1 PostgreSQL Integration
- Wire up existing `database/schema.sql` (4 tables already defined)
- Add SQLAlchemy + Alembic for ORM and migrations
- Replace in-memory LRU job cache with PostgreSQL reads
- Keep Redis for distance matrix caching (high-throughput, ephemeral)
- **Files:** New `backend/app/models/db.py`, `backend/app/models/alembic/`, update `backend/app/services/cache.py`

### 1.2 User Authentication
- Add `users` table: id, email, password_hash, company_id, role, created_at
- JWT-based auth with refresh tokens
- Register/login endpoints: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`
- Protected routes via `Depends(get_current_user)` dependency
- **Files:** New `backend/app/models/user.py`, `backend/app/routes/auth.py`, `backend/app/services/auth.py`

### 1.3 Company/Tenant Model
- Add `companies` table: id, name, plan, created_at
- Link users to companies (multi-tenancy)
- Add `company_id` to `optimization_jobs` table
- All data queries scoped by company_id
- **Files:** New `backend/app/models/company.py`, update `database/schema.sql`

### 1.4 API Key Management
- Add `api_keys` table: id, key_hash, company_id, name, permissions, expires_at
- API key authentication for B2B integrations (alternative to JWT)
- **Files:** New `backend/app/routes/api_keys.py`

### 1.5 Frontend Auth Flow
- Login/Register pages
- Auth context + token storage
- Protected route redirects
- **Files:** New `frontend/src/pages/Login.jsx`, `frontend/src/pages/Register.jsx`, `frontend/src/context/AuthContext.jsx`

**Verification:** Register user, login, create optimization job, verify data persists in PostgreSQL after restart.

---

## Milestone 2: Enhanced VRP Features (2-3 weeks)

Make the solver actually useful for real logistics operations.

### 2.1 Time Windows (VRPTW)
- Add `time_window_start` and `time_window_end` fields to Location schema
- Add time window dimension to OR-Tools solver
- Frontend: time picker per delivery stop
- **Files:** `backend/app/models/schemas.py`, `backend/app/optimization/vrp_solver.py`, `frontend/src/components/UploadPanel.jsx`

### 2.2 Multi-Depot Support
- Allow multiple depots in a single optimization request
- Each vehicle assigned to a specific depot
- Frontend: depot management UI
- **Files:** `backend/app/models/schemas.py`, `backend/app/optimization/vrp_solver.py`, `frontend/src/components/UploadPanel.jsx`

### 2.3 Priority & Priority-Based Scheduling
- Add `priority` field (1-5) to deliveries
- High-priority stops visited first within constraints
- Visual priority indicators on map
- **Files:** `backend/app/models/schemas.py`, `frontend/src/components/MapView.jsx`

### 2.4 Vehicle Types & Skills
- Define vehicle types (van, truck, bike) with different capacities/speeds
- Skill-based assignment (e.g., fragile items need specific vehicles)
- **Files:** New `backend/app/models/vehicle.py`, update solver

### 2.5 Route Export (CSV, GPX, KML)
- Generate downloadable route files for GPS devices
- CSV: stop order, address, ETA, packages
- GPX/KML: waypoints with timestamps for Garmin/Google Earth
- **Files:** New `backend/app/services/export.py`, `backend/app/routes/export.py`

### 2.6 Turn-by-Turn Directions
- Integrate Google Maps Directions API or OSRM instructions
- Display step-by-step directions per vehicle route
- **Files:** New `backend/app/services/directions.py`, `frontend/src/components/RouteDetails.jsx`

**Verification:** Create optimization with time windows, export as GPX, verify waypoints in GPS device/app.

---

## Milestone 3: Real-Time Operations (2-3 weeks)

Transform from batch optimization to live operations platform.

### 3.1 WebSocket Progress Tracking
- Replace static "Solving..." spinner with real-time solver status
- WebSocket endpoint: `WS /api/v1/ws/optimization/{job_id}`
- Status updates: matrix building, solving, extraction
- **Files:** New `backend/app/websocket.py`, `frontend/src/hooks/useWebSocket.js`

### 3.2 Driver Assignment & Tracking
- Assign optimized routes to specific drivers
- Driver dashboard showing today's route
- Basic GPS ping tracking (periodic location updates)
- **Files:** New `backend/app/models/driver.py`, `backend/app/routes/drivers.py`, new frontend pages

### 3.3 Customer Notifications
- SMS/email notifications with delivery ETA
- Integration with Twilio (SMS) or SendGrid (email)
- Configurable notification triggers (out for delivery, arrived, delayed)
- **Files:** New `backend/app/services/notifications.py`

### 3.4 Live ETA Updates
- Recalculate ETAs based on actual driver progress
- Push updated ETAs to customers
- **Files:** `backend/app/services/optimizer.py`, notification service

**Verification:** Submit optimization, see real-time progress in UI, receive test notification.

---

## Milestone 4: Business Intelligence (1-2 weeks)

Make data actionable for fleet managers.

### 4.1 Job History & Search
- List all past optimizations with filters (date, status, driver)
- Search by job_id, date range, location
- Re-run previous optimizations with one click
- **Files:** `frontend/src/pages/History.jsx`, `backend/app/routes/jobs.py`

### 4.2 Analytics Dashboard
- Key metrics: avg cost/delivery, on-time rate, vehicle utilization
- Charts: daily volume, distance trends, solver performance
- Compare periods (this week vs last week)
- **Files:** New `frontend/src/pages/Dashboard.jsx`, `backend/app/routes/analytics.py`

### 4.3 Cost Tracking
- Fuel cost estimation (distance * cost_per_km)
- Driver time cost (hours * hourly_rate)
- Total cost per job and aggregate
- **Files:** `backend/app/services/optimizer.py`, `frontend/src/components/CostBreakdown.jsx`

### 4.4 Territory & Density Maps
- Heatmap of delivery density over time
- Optimal depot placement analysis
- Zone-based fleet assignment
- **Files:** `frontend/src/components/Heatmap.jsx`, `backend/app/routes/analytics.py`

**Verification:** Run 10+ optimizations, view analytics dashboard, verify cost calculations.

---

## Milestone 5: SaaS & Billing (1-2 weeks)

Monetize the platform.

### 5.1 Subscription Tiers
- **Free**: 5 optimizations/month, 50 locations max, haversine only
- **Pro** ($49/mo): Unlimited optimizations, 500 locations, OSRM/ORS, export, priority support
- **Enterprise** ($199/mo): Custom limits, API access, SSO, dedicated support
- **Files:** New `backend/app/models/plan.py`, `backend/app/routes/billing.py`

### 5.2 Stripe Integration
- Checkout sessions for subscription signup
- Webhook handling for payment events
- Invoice generation
- **Files:** New `backend/app/services/stripe.py`, `backend/app/routes/webhooks.py`

### 5.3 Usage Metering
- Track optimizations per company per month
- Enforce limits based on plan tier
- Overage notifications
- **Files:** `backend/app/middleware/usage_limit.py`

### 5.4 Admin Panel
- User management (view, suspend, impersonate)
- Company management
- Usage dashboards
- **Files:** New `frontend/src/pages/Admin.jsx`

**Verification:** Create free account, hit usage limit, upgrade to Pro via Stripe test mode.

---

## Milestone 6: Production Operations (1-2 weeks)

Run reliably at scale.

### 6.1 Monitoring & Alerting
- Prometheus metrics endpoint (`/metrics`)
- Grafana dashboards for: request latency, solver performance, cache hit rate, error rate
- PagerDuty/Slack alerts for anomalies
- **Files:** New `backend/app/middleware/metrics.py`, `docker-compose.monitoring.yml`

### 6.2 Load Testing
- k6 or Locust scripts for concurrent optimization load
- Target: 100 concurrent 500-location optimizations
- Identify bottlenecks and optimize
- **Files:** New `scripts/load_test.py`

### 6.3 CI/CD Pipeline
- GitHub Actions: lint, test, build, deploy
- Staging environment for PRs
- Blue-green deployment for zero downtime
- **Files:** `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`

### 6.4 Backup & Recovery
- Automated PostgreSQL backups (daily + WAL archiving)
- Redis persistence with AOF
- Disaster recovery runbook
- **Files:** `scripts/backup.sh`, `docker-compose.prod.yml`

### 6.5 Security Audit
- OWASP Top 10 review
- Penetration testing
- GDPR compliance (data deletion, export)
- **Files:** `SECURITY.md`, `PRIVACY.md`

**Verification:** Run load test with 100 concurrent users, verify Grafana dashboards show metrics, test backup restore.

---

## Implementation Priority

```
Milestone 1 (Persistence + Auth)     ← Start here, everything depends on this
  ↓
Milestone 2 (VRP Features)          ← Core product value
  ↓
Milestone 3 (Real-Time)             ← Operational capability
  ↓
Milestone 4 (Analytics)             ← Data-driven decisions
  ↓
Milestone 5 (SaaS/Billing)          ← Revenue generation
  ↓
Milestone 6 (Production Ops)        ← Scale and reliability
```

**Total estimated timeline:** 10-14 weeks for full business launch.

---

## Quick Wins (Can Do Now, Before Milestone 1)

| Item | Effort | Value |
|------|--------|-------|
| Route export (CSV/GPX) | 2-3 days | Immediate user value |
| Time windows (VRPTW) | 3-5 days | Core feature gap |
| Job history page | 1-2 days | Basic data persistence |
| Analytics dashboard | 3-5 days | Business value |
| Dark/light theme toggle | 1 day | UX improvement |

---

## Tech Stack Additions

| Component | Technology | Why |
|-----------|-----------|-----|
| ORM | SQLAlchemy 2.0 | Type-safe, async support |
| Migrations | Alembic | Schema versioning |
| Auth | FastAPI Users or custom JWT | Battle-tested auth patterns |
| SMS | Twilio | Industry standard |
| Email | SendGrid | Reliable delivery |
| Payments | Stripe | De facto SaaS billing |
| Monitoring | Prometheus + Grafana | Open source, proven |
| Load Testing | k6 | Modern, scriptable |
| CI/CD | GitHub Actions | Native to the repo |

---

## Verification Strategy

After each milestone:
1. **Unit tests**: pytest (backend) + vitest (frontend) — all passing
2. **Integration tests**: API endpoint tests with TestClient
3. **Manual QA**: Full user flow in browser
4. **Docker**: `docker compose up --build` — all services healthy
5. **Demo**: End-to-end demo scenario for stakeholders
