# Technical Status & Roadmap

Consolidated view of **defects to fix**, **what stands between this codebase and
production**, **pending tasks**, and **features still to build**.

It supersedes the "future work" sections of `IMPROVEMENT_PLAN.md` and
`BUSINESS_ROADMAP.md`, both of which are now stale — they still list PostgreSQL,
Kubernetes, Prometheus and the CHANGELOG as future work, and all of those shipped.
See [§5 Roadmap reconciliation](#5-roadmap-reconciliation) for what changed.

Baseline: `main` at `97cfe56`. Backend **258/258** tests, frontend **51/51**,
eslint 0 errors / 175 warnings, coverage backend ~60% / frontend ~23%.

## How to read this

Every claim carries a confidence marker. This matters, because the difference
between "I ran it" and "an audit read the code" is the difference between a bug
report and a rumour.

| Marker | Meaning |
|---|---|
| ✅ **Verified** | Reproduced or confirmed by direct inspection while writing this document. Evidence given. |
| ⚠️ **Cited** | Read directly from the source at the given `file:line` and the mechanism is sound, but not executed. |
| 🔍 **Needs proof** | Plausible from the code, but the claim is strong enough that it should be reproduced before you act on it. |

---

## 1. Executive summary

The honest headline: **this codebase is well built and tested in the parts it
covers, and the parts it does not cover are where the severe defects live.**

That is not a coincidence. Three of the five critical findings sit in modules
with **zero test coverage**, and the single largest test file is excluded from
the coverage job. The coverage number is real, but it is measuring the wrong
half of the application.

```
Critical   5    authentication/authorization bypass, unbounded memory, event-loop stalls
High      11    billing fraud, tenant data leaks, broken CORS, unauthenticated WebSocket
Medium    26    unbounded queries, missing validation, sync-in-async, N+1, dead code
Low       20    PII in logs, silent exception swallowing, user enumeration

Test coverage        backend ~60%   frontend ~23%
Untested backend     auth, admin, billing, webhooks, notifications, analytics, drivers routes
Blocked deps         numpy 2.5, bcrypt 5, eslint 10, jsdom 30  (all floor/peer blocked)
Admin-gated          branch protection, GHCR_TOKEN, deploy secrets
```

Nothing here is an argument against shipping. It is an argument about **order**:
the five critical items are days of work and they are what stand between "demo"
and "production".

---

## 2. Bugs to fix

### 2.1 Critical

#### C1 — Empty default JWT secret allows universal token forgery ✅ **Verified**
`backend/app/config.py:39` — `JWT_SECRET_KEY: str = ""`

There is no validation. Startup only **logs a warning** (`app/main.py:56-57`).
`python-jose` signs and verifies HMAC-SHA256 happily with an empty key, so
anyone who can reach the app can mint a token for any `sub` and claim any role.

The guard is also **broken**: `app/main.py:58` checks for the literal
`"CHANGE-ME-IN-PRODUCTION"` (uppercase), but the shipped placeholder in
`.env.example:2` is `change-me-in-production` (**lowercase**). A deployment that
copies the example sails past the check. `k8s/secret.example.yaml:11` and
`.env.production.example:7` ship the same class of unchecked placeholder.

**Fix:** make the field required, or add a `model_validator` that raises when the
value is empty, under 32 bytes, or in a placeholder denylist — and refuse to
start rather than warn. Fix the case mismatch either way.

#### C2 — `depots` is unbounded → quadratic memory blowup ✅ **Verified**
`backend/app/models/schemas.py:58`

```python
depots: list[Location] = Field(default=[], description="Depot locations ...")   # no max_length
deliveries: list[Location] = Field(..., min_length=1, max_length=1000, ...)      # bounded
```

`deliveries` is correctly bounded. `depots` is not, and the matrix builder
allocates `n × n × 2` arrays. With `n` depots that grows quadratically. ⚠️ The
audit measured ~200k depots as accepted, implying a ~0.6 TB allocation — 🔍 that
figure is arithmetic, not something I executed.

Note the plan check uses `len(deliveries) + len(depots)` but is **only applied
when the DB is enabled** (`app/routes/optimization.py:65` vs `:79`), so the
DB-less path has no limit at all, and the matrix LRU retains up to 20 such
entries.

**Fix:** `max_length=50` on `depots`, assert `len(depots) + len(deliveries) <= 1100`
in the existing model validator, and run the plan check unconditionally.

#### C3 — `smtplib.SMTP` with no timeout inside `async def` ⚠️ **Cited**
`backend/app/services/notifications.py:72-75`

`SMTPEmailProvider.send` is `async def` but performs blocking socket I/O, and
`smtplib.SMTP()` defaults to `timeout=None`. A black-holed SMTP host blocks
**forever** — not an exception, so the `except` at `:78` never fires. Reachable
from `POST /api/v1/notifications/trigger` by any authenticated user.

**Fix:** `asyncio.to_thread(...)` plus an explicit `timeout=10`. Prefer
`aiosmtplib`.

#### C4 — Twilio sync HTTP inside `async def` ⚠️ **Cited**
`backend/app/services/notifications.py:41-42` — `twilio.rest.Client` is
synchronous. Same failure mode as C3, on the same request paths.

**Fix:** `asyncio.to_thread(...)`.

#### C5 — Any tenant admin can read and rewrite every tenant ✅ **Verified**
`backend/app/dependencies.py:61-65` + `backend/app/routes/admin.py`

`require_admin` checks only `user.role != "admin"`. But `role` is a **per-user,
within-company** column (`app/models/db.py:50`, default `"member"`), and
`register_user` grants `role="admin"` to **anyone who supplies a `company_name`**
(`app/services/auth.py:77`).

So every self-serve signup is a company admin, and none of the admin endpoints
authorize against the caller's own company:

```python
# app/routes/admin.py:54 — no check that this company is the caller's
result = await db.execute(select(Company).where(Company.id == company_id))
```

The 11 `company_id` references in `admin.py` are all **counting** users/jobs for
the *target* company, never *authorizing* the caller against it.

Reachable by any authenticated user:
- `GET /api/v1/admin/companies` — enumerate every tenant (plan, Stripe customer id, counts)
- `GET /api/v1/admin/companies/{company_id}` — read any tenant's users and emails
- `PUT /api/v1/admin/companies/{company_id}/plan` — rewrite any tenant's billing plan

**Fix:** this is the one item where the correct answer is architectural. Add a
platform-level role (`is_superuser`, or `role == "platform_admin"`) that is
distinct from the per-company admin. Cross-tenant operations belong behind it.
Do **not** simply scope the queries by `company_id` without deciding which
company legitimately administers the platform.

There is no test file for `admin.py` at all, which is why this survived.

### 2.2 High

| # | Finding | Loc | Confidence |
|---|---|---|---|
| H1 | **Billing fraud.** The Razorpay HMAC covers only `order_id\|payment_id`, not the plan. `plan` is an unconstrained query parameter (`billing.py:117`) written straight to `company.plan` (`:138`). A ₹49 `pro` payer can replay the same triple with `plan=enterprise`. No consumption record, so it is replayable forever. The webhook path gets this right — `webhooks.py:49` derives plan from amount. | `routes/billing.py:112-141` | ✅ |
| H2 | Any `member` can cancel the company subscription. All three billing mutations use `Depends(require_user)`, while `api_keys.py` correctly uses `require_admin`. | `routes/billing.py:82,112,158` | ✅ |
| H3 | **CORS omits `PATCH`/`PUT`/`DELETE`** — `allow_methods=["GET","POST","OPTIONS"]` — yet the app exposes PATCH/PUT/DELETE routes and the deployed topology is cross-origin. Those endpoints fail preflight. Secondary: `expose_headers` omits the rate-limit headers, so JS cannot read them. | `app/main.py:89,91` | ✅ |
| H4 | Rate limiter keyed on the **raw path** (`rate_limit.py:60`), so every distinct path is a fresh bucket — `GET /routes/<random-uuid>` grants a full 120-request allowance each time. `_hits` is a `defaultdict(list)` pruned only every 30s, so it grows unbounded within that window. | `middleware/rate_limit.py:33,60,83` | ⚠️ |
| H5 | Rate limiting collapses to **one global bucket** in production. `TRUST_PROXY_HEADERS` defaults `False` and is not set in `docker-compose.prod.yml`, `k8s/secret.example.yaml` or `.env.production.example`, so every user shares the proxy IP's bucket. Worse, nginx sets `X-Real-IP` but **not** `X-Forwarded-For`, and the backend reads only the latter. Compounded by `--workers 2` and HPA `maxReplicas: 10` — the limiter is in-process, so the real global limit is 10-20× configured. | `config.py:79`, `middleware/rate_limit.py:36-41`, `frontend/nginx.conf:63-67` | ✅ |
| H6 | **WebSocket progress accepts unauthenticated connections** — `main.py:149-161` only validates the token `if token:`, so omitting `?token=` skips all checks. No check that the token's company owns the `run_id` either. `ws_drivers_fleet` (`:184`) does this correctly, so the fix pattern already exists in the file. | `app/main.py:149-161` | ⚠️ |
| H7 | `_progress_store` is unbounded and keyed on **client-supplied** `run_id` (`cache.py:225`, `optimization.py:48,85`). Entries are removed only on success (`optimizer.py:108`), so every solver failure leaks one forever. | `services/cache.py:225` | ⚠️ |
| H8 | `optimization_jobs.company_id` was added `nullable=True` with **no `server_default` and no backfill** (`alembic/versions/a1b2c3d4e5f6:42`), while the ORM declares `nullable=False` (`models/db.py:80`). Pre-existing rows keep `NULL`, are invisible to every tenant query, and cannot be reassigned. | `alembic/…a1b2c3d4e5f6:42` | ⚠️ |
| H9 | **2-10 replicas race on `alembic upgrade head`** — every worker/pod migrates in its own lifespan (`database.py:73-82`), with no advisory lock, and the failure is swallowed to a log line (`:77-78`). A worker can then serve traffic against a half-migrated schema. | `Dockerfile:24`, `app/database.py:73-82` | ⚠️ |
| H10 | Export issues **N sequential external HTTP calls** with no deadline (`export.py:166-167`), each opening a fresh `AsyncClient` with `timeout=30`. A 100-stop route is ~99 round-trips ≈ up to 50 minutes for one request. `get_directions_for_route` already does this correctly with `asyncio.gather` + semaphore (`directions.py:217-227`). | `services/export.py:166-167` | ⚠️ |
| H11 | **Prometheus label cardinality is unbounded** — `path = request.url.path` (`:51`) is used verbatim as a label on `REQUEST_COUNT` and `REQUEST_LATENCY` (`:62-63`), so every job UUID and attacker-chosen `run_id` creates a new series. | `middleware/metrics.py:51,62-63` | ⚠️ |

### 2.3 The live-progress feature is silently dead ✅ **Verified**

This one is called out separately because it is a **shipped feature that does
nothing**, discovered by direct test rather than code reading.

`app/services/cache.py:244-260` broadcasts progress via `anyio.from_thread.run`,
wrapped in a `try/except` that downgrades the failure to `debug`. I ran it:

```
from asyncio run_in_executor thread -> NoEventLoopError: Not running inside an AnyIO worker thread…
from event loop thread             -> NoEventLoopError: Not running inside an AnyIO worker thread…
from anyio to_thread               -> ok
```

`anyio.from_thread.run` only works inside a thread spawned by
`anyio.to_thread.run_sync`. The real call site is `run_in_executor(None, ...)`
(`optimization.py:89`, `replan.py:216`) — asyncio's **default** executor, which
provides no AnyIO token. So the call raises, and the exception is swallowed.

**WebSocket progress updates never reach the client.** Phase 8.4 / roadmap 3.1
is non-functional, and reports no error. `useWebSocket.js` reconnects every 2s
forever, waiting for messages that never come.

**Fix:** capture the main event loop at startup and use
`asyncio.run_coroutine_threadsafe(...)`, or inject an async broadcaster.
Verify by asserting a message actually arrives — the current test surface
cannot detect this failure.

### 2.4 Medium (selected — full list in the audit)

| # | Finding | Loc |
|---|---|---|
| M1 | `authenticate_api_key` **commits on every authenticated request**, including read-only GETs — one DB write per GET, and it defeats the request-scoped rollback | `services/api_keys.py:62-69` |
| M2 | Tenant leak: `select(VehicleRoute).where(job_id, vehicle_id)` has **no `company_id` filter** — a user can attach another tenant's vehicle route to their driver | `routes/drivers.py:167-173` |
| M3 | Same gap: driver lookup by id with no company filter, leaking another tenant's driver **name** into an SMS/email body | `services/notifications.py:121` |
| M5 | `limit: int = 50` with **no bounds** — `?limit=1000000000` dumps the whole notification log (customer phone/email/message) | `routes/notifications.py:77` |
| M6 | `/refresh` mints new tokens **without checking the user still exists or is active**, and there is no `jti`/denylist — a deactivated user keeps access for the 7-day window | `routes/auth.py:52-62` |
| M7 | OSRM failure silently falls back to haversine but still **labels `source = "osrm"`**, and the mislabelled matrix is written into the cache, poisoning future hits | `services/distance_matrix.py:202-204` |
| M8 | `label` has no `max_length` but the column is `String(200)` → a long label yields **500 instead of 422** | `models/schemas.py:20` |
| M10 | No-solution fallback hardcodes `list(range(1, n))`; with multiple depots, depot nodes are reported as **unassigned deliveries** | `optimization/vrp_solver.py:206` |
| M11 | No `pool_pre_ping`/`pool_recycle` → `SSL connection has been closed` behind pgbouncer after idle | `app/database.py:28` |
| M12 | `wait_for_db()` result is **discarded**; migrations run anyway and the app starts serving 500s | `app/main.py:53-55` |
| M14 | `/metrics` is served with **no authentication** — request rates, latency, error rates exposed to anyone | `middleware/metrics.py:47-48` |
| M17 | **Synchronous `redis` client** used from async paths throughout (`cache.py:73,116,145,178,221`) — every round-trip blocks | `services/cache.py:32+` |
| M18 | `minidom` GPX/KML serialisation on multi-MB documents runs **synchronously inside `async def`** — seconds of CPU on the event loop | `services/export.py:141-143,289-292` |
| M19 | `POST /notifications/trigger` returns **HTTP 200** whether nothing was configured, the trigger was disabled, or the provider failed — indistinguishable | `routes/notifications.py:77` |
| M20 | `uuid.UUID(body.job_id)` with no `try/except` → malformed id yields **500, not 422** | `routes/drivers.py:169` |
| M22 | Analytics loads **every job row for up to 365 days** into Python and aggregates there — up to ~120k ORM objects per request | `routes/analytics.py:33-41` |
| M26 | `lifespan` has **no shutdown branch** — engine and Redis client never disposed | `app/main.py:48-68` |
| — | **Plan entitlements are declared but never enforced**: `export_enabled` and `max_users` appear only in definitions and the billing response, never in a check | `services/plans.py:17,19` |
| — | `PUT /notifications/config` lets any **member** overwrite company-wide `twilio_auth_token` / `smtp_password` | `routes/notifications.py:35-53` |
| — | Two competing transaction owners: `get_db` commits in teardown *and* the api-key routes commit explicitly | `app/database.py:85-95` |
| — | `%` in a DB password raises `ValueError: invalid interpolation syntax` — alembic forwards the URL to `configparser` without escaping | `app/database.py:70`, `alembic/env.py:20` |
| — | Dead code: `app/services/stripe_service.py` (123 lines) is **imported by nothing**; Razorpay is the live path | `services/stripe_service.py` |
| — | Dead DDL: `matrix_cache` table has no ORM model and no reader/writer | `alembic/…2f4a6c8e0b1d:101-116` |
| — | OR-Tools drop penalty scales with `n` (~2e16 at n=1000), uncomfortably close to int64 accumulation | `optimization/vrp_solver.py:180-187` |

### 2.5 Low

- **PII in logs**: customer phone numbers, emails and message bodies are written
  to structured logs (`services/notifications.py:36,43,65,76,85`); user emails
  are logged on every registration (`services/auth.py:81`).
- **User enumeration** by timing: `/login` verifies a password only when the user
  exists (`services/auth.py:85-90`).
- `User.email` is **case-sensitive** and globally unique, so `A@x.com` and
  `a@x.com` are different accounts (`models/schemas.py:229`, `models/db.py:47`).
- `password: max_length=128` but bcrypt silently truncates at **72 bytes**.
- `verify_password` can raise `UnknownHashError` on a corrupt hash → 500 instead
  of 401.
- Razorpay redirect is derived from `ALLOWED_ORIGINS[0]` (`routes/billing.py:98`).
- Silent `except Exception: pass` at `services/replan.py:144-145` — a corrupt
  previous job silently produces a materially different replan with no log line.
- `db-migrations.yml`'s single-head assertion `test "$(alembic heads --resolve-dependencies)" != ""`
  passes for *any* number of heads, so it does not actually verify one head.

---

## 3. Frontend: defects

### 3.1 High

| # | Finding | Loc | Confidence |
|---|---|---|---|
| F1 | **`refresh_token` is stored and never used.** It is written to `localStorage` on login and register and removed on logout, but **no code ever reads it**. Combined with the absence of a 401 interceptor, an expired access token means an abrupt logout with no silent renewal — despite the backend exposing `/refresh` and issuing 7-day refresh tokens. | `context/AuthContext.jsx:22,32,38` | ✅ |
| F2 | **No 401 handling in the API layer.** `api.js` has no fetch wrapper or interceptor; the only 401 handling is the one-shot `/me` check, which logs out on failure. Every other call surfaces a raw error. No timeouts and no `AbortController` anywhere, so a hung request hangs the UI indefinitely. | `api.js:3-14` | ✅ |
| F3 | **Tokens in `localStorage`** — readable by any script, so one XSS exfiltrates a 7-day session. | `context/AuthContext.jsx:8,21-23` | ✅ |
| F4 | **No role guard.** `ProtectedRoute` checks only that a user exists, and `/admin` is wrapped in `ProtectedRoute` alone, so any authenticated user reaches the admin UI client-side. | `components/ProtectedRoute.jsx:4-34`, `App.jsx:90-96` | ✅ |
| F5 | **Post-login redirect discards the intended destination.** `<Navigate to="/login" replace />` passes no location state, so a user deep-linking to `/dispatch` lands on `/dashboard` after login instead. | `components/ProtectedRoute.jsx:32` | ✅ |

Note F4 is cosmetic relative to C5: the backend lets those requests succeed
anyway. Fixing the client guard alone would be security theatre.

### 3.2 Medium / Low

- **10 blocking `alert()` calls** for errors and success messages — poor UX and
  they leak internal error text (`ApiKeysPage.jsx:63,71`,
  `BillingPage.jsx:54,72,77`, `NotificationSettingsPage.jsx:112,120`,
  `AdminPage.jsx:44`). No toast/notification system exists.
- **146 `react/prop-types` warnings**, now the *only* prop validation since
  React 19 removed the runtime check. Worst: `ResultsPanel.jsx` (37),
  `MapView.jsx` (27), `RouteDetails.jsx` (24), `MetricsBar.jsx` (23),
  `UploadPanel.jsx` (15). The project is **JavaScript, not TypeScript** — so
  the real fix is a TS migration, not 146 `PropTypes` blocks.
- **No focus management on route change** — after navigation, focus stays where
  it was, so keyboard and screen-reader users are stranded. A skip link exists
  (`App.jsx:209-211`), which is good.
- **jest-axe covers only `Header` and `UploadPanel`** (`__tests__/a11y.test.jsx`) —
  not one of the ten pages. No `<img>` without `alt`, and no `onClick` on
  non-interactive elements, which is genuinely good.
- `useWebSocket.js` reconnects **every 2s forever** with no cap, no backoff and
  no heartbeat; and `onMessage` is invoked without a mounted check.
- Two `console.error` left in production source (`ErrorBoundary.jsx:14`,
  `ResultsPanel.jsx:63`).

### 3.3 Checked and *not* bugs ✅

Three things that look wrong but are fine — recorded so nobody "fixes" them:

- **`VITE_API_URL` is never set, and that is correct.** `api.js:1` falls back to
  `''`, giving same-origin relative requests, and `frontend/nginx.conf:63`
  proxies `/api/` to the backend. The agent audit flagged this CRITICAL after
  reading a *commented-out* nginx block at `:23-27`. The topology is fine.
  *Worth noting:* a separately-deployed frontend would need the variable, so
  document it rather than assume.
- **An `ErrorBoundary` exists** (`src/ErrorBoundary.jsx`, wired at `App.jsx:29`),
  so a render throw shows a fallback, not a white screen.
- **Security headers are active.** CSP, HSTS, `X-Frame-Options: DENY` and
  `Permissions-Policy` are all set in the `server` block — the identical block
  at `:18-30` is commented out, which is confusing but harmless.
- The frontend `Dockerfile` **is** multi-stage and does not ship devDependencies.

---

## 4. Production readiness

### 4.1 Must fix before real traffic

1. **C1** — empty JWT secret. One env var away from full compromise.
2. **C5** — cross-tenant authorization. Any signup can read every customer.
3. **C2** — unbounded `depots`. One request can exhaust a node.
4. **C3 / C4** — event-loop stalls. One slow SMTP host takes down the app.
5. **H1 / H2** — billing fraud and subscription tampering.
6. **§2.3** — live progress is dead; either fix it or stop advertising it.

### 4.2 Must fix before horizontal scaling

- **H9** — migrations race across replicas and failures are swallowed.
- **H5** — the rate limiter is per-process *and* mis-keyed behind the proxy, so
  it provides neither fairness nor a real ceiling.
- **M17** — the synchronous Redis client blocks on every call.
- **H11** — unbounded Prometheus label cardinality will OOM the process.

### 4.3 Must fix before relying on the billing/plan tier

Plan limits are **declared but never enforced** (`export_enabled`, `max_users`
have zero enforcement). Customers can be sold tiers that do nothing.

### 4.4 Operational gaps

| Gap | Detail |
|---|---|
| No coverage gate | `backend-coverage` is `continue-on-error: true` (`ci.yml:58`) — a gate that cannot fail. Frontend's is real. |
| Coverage excludes the biggest test file | `ci.yml:63` passes `--ignore=tests/test_api.py` (831 lines, 90 tests). |
| Coverage excludes the app entrypoint | `backend/pyproject.toml:24` omits `app/main.py`, so the lifespan and both WebSocket endpoints are never measured. |
| No load testing | Zero performance or stress tests in either suite. Roadmap 6.2 is unmet. |
| Test/env mismatch | `pyproject.toml` and CI target `py311`; the local venv is **3.14**. Local runs are not CI-equivalent. |
| No health gating | `/health` calls **synchronous** Redis `ping()` on the event loop every probe (`main.py:141`); `wait_for_db()`'s result is discarded (`M12`). |
| Engine floors undocumented | No `.nvmrc`, no `engines` field, no Python floor. Node requirements exist (`vitest` 5 needs `^22.12.0`, `jsdom` 29 needs `^22.13.0`) and are recorded nowhere — this is exactly why `jsdom` 30 and `numpy` 2.5 fail late instead of at resolution. |

### 4.5 Security posture summary

**Good** — and worth preserving: no SQL injection anywhere (all queries are
parameterised; the only raw SQL is a literal `SELECT 1` and `CREATE EXTENSION`);
JWT verification *is* enforced with an explicit algorithm list and no
verify-bypass; no hardcoded secrets in `app/`; `.env` is gitignored; bcrypt
config is currently correct (`bcrypt==4.0.1` + `passlib`, avoiding the known
`bcrypt>=4.1` breakage); security headers and a CSP are active; notification
config responses correctly omit secrets.

**Poor** — the authentication and multi-tenancy boundary (C1, C5, H1, H2), and
the fact that none of it is tested.

---

## 5. Roadmap reconciliation

`IMPROVEMENT_PLAN.md` and `BUSINESS_ROADMAP.md` are both stale. Corrected status:

| Item | Roadmap said | Reality |
|---|---|---|
| PostgreSQL integration | future (High) | ✅ shipped — SQLAlchemy async, asyncpg, alembic |
| Kubernetes | future (High) | ✅ shipped — `k8s/`, HPA 2-10 |
| Production docker-compose | future (Medium) | ✅ shipped — `docker-compose.prod.yml` |
| Prometheus + tracing | future (Medium) | ✅ shipped — `middleware/metrics.py`, `app/tracing.py` |
| Structured logging | future (Low) | ✅ shipped — structlog |
| CHANGELOG / deploy guide / config reference | future | ✅ shipped |
| `SECURITY.md` | future | ✅ exists |
| Time windows (VRPTW) | future (High) | ✅ shipped and tested — `test_time_windows.py` |
| Multi-depot | future (High) | ✅ shipped — `test_multi_depot.py` (but see C2) |
| Route export | quick win | ✅ shipped — CSV/GPX/KML |
| Dark/light theme | quick win | ✅ shipped — `context/ThemeContext.jsx` |
| Job history, analytics dashboard | quick win | ✅ shipped |
| **WebSocket progress** | M3.1 | ⚠️ **code exists but is dead** — see §2.3 |
| Traffic-aware routing | future (High) | ⚠️ partially — referenced in schemas/`replan.py` |
| Territory/density maps | M4.4 | ⚠️ partial — `analytics.py`, needs verification |
| Stripe integration | M5.2 | ⚠️ **dead code** — Razorpay is the live provider |
| **Load testing** | M6.2 | ❌ **not started** — no perf tests at all |
| **Security audit** | M6.5 | ❌ **not started** — this document is the first pass |

---

## 6. Pending tasks

### 6.1 Blocked on repo admin

| Task | Detail |
|---|---|
| Branch protection | Required checks + `CODEOWNERS` review + `main` protection. Without it, none of the 12 CI checks is actually enforced on merge. |
| `GHCR_TOKEN` | Code landed in PR #7; the secret is still absent, so images are not published. |
| Blue-green deploy secrets | `DEPLOY_HOST/_USER/_SSH_KEY/_PATH`, `REDIS_PASSWORD`, `POSTGRES_PASSWORD`. |
| Dependabot security updates | The toggle in **Settings → Code security** may still be on. `dependabot.yml` is deleted, so no PRs are proposed, but alerts may still fire. |

### 6.2 Dependency floors — a single decision unlocks four bumps

| Bump | Blocked on |
|---|---|
| `numpy>=2.5` | Python floor → 3.12. 2.5.0 ships **no cp311 wheels**; both CI and `backend/Dockerfile:1` are 3.11. |
| `jsdom@30` | Node floor → ≥22.22.2, recorded in `engines` + `.nvmrc`. |
| `bcrypt==5.0.0` | The passlib migration — needs tests first. |
| `eslint@10` | Upstream: `eslint-plugin-react@7.37.5` is the newest release and peers `^9.7`. |

**Raise the floors and record them** (`engines`, `.nvmrc`, Dockerfiles). That
converts every one of these from a late, confusing CI failure into a resolution
error at the moment of the bump.

### 6.3 Test debt

| Gap | Detail |
|---|---|
| Zero-coverage modules | `routes/auth.py` (login/register/refresh **entirely untested**), `routes/admin.py`, `routes/billing.py`, `routes/webhooks.py`, `routes/analytics.py`, `routes/drivers.py`, `routes/notifications.py` |
| Zero-coverage services | `services/plans.py`, `services/razorpay_service.py` (HMAC verification!), `services/eta.py`, `services/optimizer.py`, `services/notifications.py` |
| Untested functions | `hash_password` / `verify_password` have **no tests at all** — which is why the passlib migration is stuck |
| No endpoint coverage | Zero requests to `/auth/login`, `/auth/register`, `/auth/refresh`, `/admin/*`, `/billing/*`, `/webhooks/*`, `/notifications/*` |
| Frontend | 23% coverage; no tests for 10 of 11 pages. `api.js` recovered to 43% by PR #24 |
| Migration drift | No `alembic check` in CI, and the head-count assertion passes for any number of heads |
| Fix `pytest --cov` deadlock | The documented reason `test_api.py` is excluded (`CI_PIPELINE_PLAN.md` Known deviations) — untriaged |

### 6.4 Code quality

- **175 eslint warnings** → `--max-warnings 0`. The plan's step 8.
- **22 React Compiler findings** across 12 files, deferred in
  `CI_PIPELINE_PLAN.md`. Mostly `set-state-in-effect` in data-fetching code.
  Sequence is coverage → fix → enable.
- **`ruff` pin parity**: `requirements.txt` and `.pre-commit-config.yaml` must
  move together. Dependabot proposed loosening `==0.16.6` to `>=`, which would
  have restored the non-determinism the pin exists to prevent.
- **ESLint config needs migrating**: it is flat-config style but declares
  `parserOptions` (pre-flat key) and `plugins` as an object rather than a flat
  array. It works by accident.
- 6 separate `httpx.AsyncClient()` constructions inside request-path functions —
  no connection reuse.
- **TypeScript migration** — the only real fix for the 146 `prop-types`
  warnings.

### 6.5 Dead and stale code

- `app/services/stripe_service.py` — imported by nothing (123 lines).
- `matrix_cache` table — DDL with no model and no reader/writer.
- `matrix_source = "osrm"` mislabelling (M7).
- `CHANGELOG.md:36` still labels Phase 8.7/8.8 "In progress" while
  `docs/PHASE8_PLAN.md:91,99` mark them done.
- `Jenkinsfile` — legacy, superseded by the GH Actions pipelines. Retire or
  document.
- `docs/BUSINESS_ROADMAP.md`, `docs/IMPROVEMENT_PLAN.md` — stale, see §5.

---

## 7. Features still to build

Ordered by what unblocks the most work.

### 7.1 Not features — repair work disguised as features

| Item | Why it reads as a feature |
|---|---|
| **Working live progress** | §2.3. The UI exists and the WebSocket reconnects forever; nothing is ever sent. |
| **Silent token refresh** | F1/F2. `refresh_token` is already issued and stored. Wiring an interceptor is a day of work and removes a class of "why did I get logged out" support tickets. |
| **Real role-based access control** | F4 + C5 together. Until the platform role exists, "admin" means two unrelated things. |
| **Enforced plan entitlements** | §4.3. The tiers are sold; `export_enabled` and `max_users` do nothing. |
| **Typed API client** | The TS migration kills 146 warnings, the missing-timeout class of bug, and gives the interceptor somewhere to live. |

### 7.2 Genuinely new capabilities

| Feature | Notes | Effort |
|---|---|---|
| **Load / performance testing** | Never started. The 2-CPU / 2 GiB container limit plus a 600s solver time limit means concurrency behaviour is unknown. This should precede any scaling claim. | Medium |
| **Formal security audit** | This document is a code-reading pass, not an audit. | High |
| **Deep-link-safe auth flow** | F5 — preserve the requested route across login. | Low |
| **Toast / notification system** | Replaces 10 `alert()` calls; needed for any async UX. | Low |
| **Silent observability** | `structlog` JSON is shipped but PII leaks into it (phone numbers, emails, message bodies). Redaction is a prerequisite for shipping logs anywhere. | Medium |
| **Distributed rate limiting** | Redis is already a dependency. | Low |
| **Move Redis to `redis.asyncio`** | Removes blocking I/O from every request path (M17). | Low |
| **Migrate startup DDL to a pre-deploy job** | Fixes H9 properly. | Medium |
| **Multi-region / DR rehearsal** | `docs/DISASTER_RECOVERY.md` exists; has it been tested? | Medium |
| **Customer-facing notifications UI** | Drivers get SMS/email; customers do not appear to. | Medium |
| **Territory & density maps** | Roadmap 4.4, partial in `analytics.py`. | Medium |
| **Cost tracking** | Only a `MetricsBar` reference today; roadmap 4.3 is effectively unbuilt. | Medium |

### 7.3 Explicitly not recommended yet

- **More VRP feature work.** Time windows, multi-depot, priority and export are
  all shipped. The marginal feature is worth far less than fixing C1 and C5.
- **Scaling out.** H5, H9, H11 and M17 each independently break horizontal
  scaling. Fix those before adding replicas.
- **Anything touching auth, billing or multi-tenancy** before C1/C5/H1 and the
  corresponding tests land.

---

## 8. Suggested order of work

```
Week 1   C1 empty JWT secret ......... half a day, closes a total-compromise hole
         C5 cross-tenant authz ....... architectural, but the decision is the work
         H1/H2 billing ................ fraud + privilege, small diffs
         cap depots (C2) ............. one-line + validator, closes a DoS

Week 2   §2.3 live progress ........... either fix or stop shipping it
         C3/C4 async notifications .... event-loop stalls
         tests for auth/admin/billing . so the fixes above cannot regress
         hash_password tests .......... unblocks passlib + bcrypt 5

Week 3   H9 migrations, H5 rate limit . required before >1 replica
         M17 redis.asyncio, H11 metrics  correctness under load
         record Node + Python floors ... makes the next bump fail at resolution

Then     load testing .................. before any scaling claim
         TS migration ................. kills the 146 prop-types warnings
         coverage to a real gate ...... makes all of the above hold
```

---

## 9. Appendix: reproducing the verified findings

```bash
# C1 — empty JWT secret + broken placeholder guard
grep -n "JWT_SECRET_KEY" backend/app/config.py backend/app/main.py .env.example

# C2 — depots unbounded, deliveries bounded
grep -n "depots\|deliveries" backend/app/models/schemas.py | head -3

# C5 — role is per-user; admin routes never check the caller's company
grep -n "role" backend/app/models/db.py | head -2
grep -n 'role="admin"' backend/app/services/auth.py
sed -n '48,60p' backend/app/routes/admin.py

# H1/H2 — plan from a query param; billing uses require_user not require_admin
sed -n '112,120p' backend/app/routes/billing.py

# H3 — CORS methods
sed -n '85,93p' backend/app/main.py

# H5 — nginx sets X-Real-IP but not X-Forwarded-For
sed -n '63,67p' frontend/nginx.conf

# §2.3 — anyio.from_thread.run raises from both real call sites
cd backend && .venv/bin/python -c "
import anyio, asyncio
async def m():
    def w():
        try: anyio.from_thread.run(lambda: None)
        except Exception as e: print(type(e).__name__, e)
    await asyncio.get_running_loop().run_in_executor(None, w)
asyncio.run(m())"

# F1 — refresh_token stored, never read
grep -rn "refresh_token" frontend/src/
```

**Not reproducible locally:** the 3.11 install matrix (local venv is 3.14) and
container image builds (no Docker daemon) — those need CI.
