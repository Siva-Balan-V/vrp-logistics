# Bugfix Plan

Sequenced remediation plan for the findings in
[TECHNICAL_ROADMAP.md](TECHNICAL_ROADMAP.md). That document is the **what**;
this one is the **in what order, with what proof, and at what risk**.

Baseline: `main` at `b5232ae`. Backend **258/258** tests, frontend **51/51**,
eslint 0 errors / 175 warnings, coverage backend ~60% / frontend ~23%.

## Scope

**In:** the 5 critical findings, the 11 high findings, the dead live-progress
feature, the frontend auth findings (F1-F5), and the tests that prove each fix.

**Out:** all medium and low findings, the production-readiness gaps, the
TypeScript migration, and the passlib → bcrypt migration. Listed in
[§9 Out of scope](#9-out-of-scope) rather than dropped.

Every PR in this plan is independently revertable. That is a design constraint,
not a nicety: it means a bad merge is a `git revert`, not an incident.

---

## 1. Locked decisions

Four decisions were open when this plan was written. They are resolved, and the
rest of the document assumes them.

| # | Decision | Choice | Consequence |
|---|---|---|---|
| D1 | Cross-tenant admin (C5) | Add `users.is_platform_admin` + `require_platform_admin` | Keeps the admin panel's cross-tenant capability, makes the boundary explicit. Needs one migration and a bootstrap decision (§8, risk 2) |
| D2 | JWT secret (C1) | Add `ENVIRONMENT`; hard-fail unless dev/test | `config.py` has no environment concept today, so this is a new setting, not a tweak. Fixes the stale uppercase guard |
| D3 | Token storage (F3) | httpOnly cookies + CSRF protection | Largest PR in the plan. Simplifiable because production is same-origin (§1.1) |
| D4 | Plan scope | Critical + High + tests | Keeps the plan reviewable. Medium/low become follow-up |

### 1.1 Why the cookie change is smaller than it looks

`docker-compose.prod.yml` binds backend to `127.0.0.1:8000` and frontend to
`127.0.0.1:8080`, and `frontend/nginx.conf` serves the SPA at `/` **and** proxies
`/api/` to the backend. From the browser's perspective there is one origin. The
Vite dev server also proxies `/api`, so development matches production.

Two consequences:

- `SameSite=Lax` cookies are viable. Combined with the fact that every
  state-changing route is `POST`/`PUT`/`PATCH`/`DELETE`, this is a strong CSRF
  mitigation on its own. The double-submit token stays in scope as
  defence-in-depth, not as the primary control.
- **F1 is subsumed by F3.** With an httpOnly refresh cookie the client retries a
  401 and the server refreshes transparently. Do not build the refresh
  interceptor as its own PR and then rewrite it in the cookie PR.

---

## 2. Wave 0 — Foundations

Blocks everything. Both 1.3 and 1.4 change behaviour in ways that cannot be
proven correct without tests that do not currently exist.

There is no `backend/tests/conftest.py`. `JWT_SECRET` and `create_access_token`
appear only in `tests/test_auth_dependencies.py`. Every other test either
avoids auth or hand-rolls it.

### PR 0.1 — Test fixtures

Add `backend/tests/conftest.py`:

- `settings` fixture overriding `JWT_SECRET_KEY` so tests never inherit a
  default or depend on developer `.env`
- `client` fixture using `TestClient`
- `auth_headers` factory for a signed token per user/role
- `db_session` helper for the tests that need persistence

**The `.env` leak is not hypothetical.** Measured on this checkout: with
`backend/.env` present, `pytest` hangs past 900s and never finishes. Remove the
`DATABASE_URL` line and the same 258 tests pass in 129s. `config.py:96` loads
`.env` at import time, so a developer with `DATABASE_URL` pointing at a Postgres
that is not running gets a suite that stalls instead of failing. CI has no `.env`,
which is why this was never noticed.

A fixture that clears the environment before settings are constructed fixes the
symptom. The durable fix is to stop loading `.env` implicitly during tests.

No behaviour change in production code. This exists so that 0.2 and everything
after it are cheap.

### PR 0.2 — Auth and billing endpoint tests

Cover `login`, `register`, `refresh`, `/me`, and the billing routes.

This is the proof that makes 1.3 and 1.4 safe to attempt. H1 changes where
`plan` comes from; H2 changes who may call the route at all. Both are
security-relevant and neither is verifiable without a test that asserts the
*rejection*, not just the success path.

### PR 0.3 — Record dependency floors *(optional)*

Neither exists today: `backend/pyproject.toml` declares no `requires-python`,
and there is no `.nvmrc`.

- `requires-python = ">=3.11,<3.14"` in `backend/pyproject.toml`
- `.nvmrc` pinned to the current Node 22.22.1

Cheap insurance. Four blocked bumps — `numpy` 2.5 (needs Python ≥3.12), `jsdom`
30 (needs Node ≥22.22.2), `eslint` 10 (upstream), bcrypt 5 (needs the passlib
migration) — currently fail silently at build time instead of at resolve time.
Optional because it is not a bug; do it if convenient.

**Gate:** 258+ green, pure additions, no production code touched.

---

## 3. Wave 1 — Criticals

Small, independent, high impact. Four of five are under 30 lines each.

### PR 1.1 — C1: require a real JWT secret

- Add `ENVIRONMENT` to `app/config.py`
- Refuse to boot when `JWT_SECRET_KEY` is empty, short, or the bundled
  placeholder, unless `ENVIRONMENT` is explicitly development or test
- Replace the warning-only guard at `app/main.py:56-60`, which compares against
  an **uppercase** placeholder while `config.py:39` ships a lowercase example —
  so it does not match its own target

Test: importing settings with the default secret in a production-like
environment raises.

### PR 1.2 — C2: bound request payloads

- `max_length` on `depots` in `app/models/schemas.py:58`, which is unbounded
  while `deliveries` at `:59` is capped at 1000
- Bound `label` at `:20`, currently unbounded
- Add a request body size guard

Test: a 10,000-depot payload returns 422.

### PR 1.3 — H1 + H2: billing authorization

**H1 — the HMAC does not cover the plan.** `plan` arrives as an unconstrained
body/query parameter on `create-order` (`billing.py:82`), `verify-payment`
(`:119`) and `cancel-subscription` (`:161`), and `verify-payment` writes it
straight to `company.plan` (`:120`). The Razorpay signature covers only
`order_id|payment_id`, so a ₹49 `pro` payer can replay a verified payment with
`plan=enterprise`, and nothing records the consumption, so it stays replayable.

The fix already exists elsewhere in the codebase: `webhooks.py:49` calls
`get_plan_from_razorpay_amount(amount)`. Reuse that helper so plan is derived
from the paid amount, never accepted from the client.

**H2 — `require_user` where `require_admin` belongs.** All four billing routes
use `Depends(require_user)` (`:50`, `:86`, `:119`, `:161`), so any `member`
can cancel the company subscription. `api_keys.py` gets this right — it uses
`require_admin` at `:35`, `:49`, `:63`. Follow that pattern.

Tests: cross-tenant access returns 403; a `member` cannot cancel; a
client-supplied `enterprise` plan is ignored and the server-derived tier wins;
replaying a captured signature cannot change the plan.

### PR 1.4 — C5: platform admin boundary

- Migration adding `users.is_platform_admin`
- `require_platform_admin` dependency in `app/dependencies.py`, alongside the
  existing `require_admin` at `:61-65` which is role-only
- Gate `/api/v1/admin/*`
- Company-scoped authorization on `/companies/{company_id}`
  (`app/routes/admin.py:48-60`), which currently reads any tenant

Tests: a tenant admin cannot list companies and cannot read another company; a
platform admin can.

Also note, from the same review: `register_user` grants `role="admin"` to any
signup that supplies a `company_name` (`app/services/auth.py:77`). That is how
the cross-tenant surface became reachable. Fold the fix into this PR or file it
as a follow-up; do not leave it unremarked.

### PR 1.5 — C3 + C4: take blocking I/O off the event loop

- `notifications.py:41-42` calls Twilio synchronously
- `notifications.py:72-75` constructs `smtplib.SMTP` with no timeout
- `notifications.py:121` performs an unscoped driver lookup

Move both to a threadpool, add SMTP timeouts, scope the lookup.

Tests: mock the clients, assert the endpoint returns without waiting on them.

**Gate:** full backend suite green, each PR independently revertable, +1
migration with a tested downgrade path.

---

## 4. Wave 2 — Transport and access control

### PR 2.1 — H6 + the unauthenticated status endpoint

One PR, because both fix the same surface.

- Copy the correct pattern from `ws_drivers_fleet` (`app/main.py:184-200`) onto
  the progress WebSocket at `app/main.py:149-162`. That handler treats the
  token as optional (`if token:`), never checks `expected_type="access"`, and
  never checks company ownership of `run_id`
- `GET /optimize-routes/{run_id}/status` (`app/routes/optimization.py:150`) has
  **no `Depends(...)` at all** — unauthenticated run progress polling

> The roadmap files the status endpoint as low severity because it only exposes
> progress. It is an unauthenticated endpoint that accepts attacker-chosen
> `run_id` values, which makes it an enumeration oracle for run existence.
> Treating it as low is a severity misjudgement, not a style preference.

Tests: missing token, refresh token used as an access token, cross-tenant
`run_id`, and unauthenticated status polling are all rejected.

### PR 2.2 — H4: fix rate-limit keying

`app/middleware/rate_limit.py:54-58` selects the limit by **exact path match**.
A trailing slash falls through to `default_limit=120`, so
`/optimize-routes/` gets 4× the intended limit on the most expensive endpoint in
the app. The middleware runs before routing, so nothing later catches it.

- Match on the normalized/route-template path, not the raw string
- Bound the `client_ip:path` keyspace

Test: `/optimize-routes/` and `/optimize-routes` hit the same 30/min bucket.

### PR 2.3 — H5: trust the proxy for client IPs

- Set `X-Forwarded-For` and `X-Forwarded-Proto` on the **active** `/api/` block
  in `frontend/nginx.conf:63-67`. It sets `X-Real-IP` only, and only that
- Move limits into environment variables

Note the duplicate server block at `nginx.conf:18-30` is commented out. Edit
the active one; several audit findings in other documents came from reading the
dead copy.

**Gate:** unauthenticated and wrong-type WebSocket tokens rejected; status
endpoint requires auth; rate-limit tests green.

---

## 5. Wave 3 — The dead feature and its leak

### PR 3.1 — Live progress, rebuilt and bounded

Fixes the live-progress gap (roadmap §2.3: progress is emitted and never
received) and H7 (the store leaks on
every failure) together, because both live in `cache.py` and share the `run_id`
lifecycle. Splitting them means reviewing the same function twice.

- `_progress_store` (`app/services/cache.py:225`) is an unbounded module-level
  dict with no eviction
- `clear_progress` exists only on the success path
  (`app/services/optimizer.py:108`), so **every failed solve leaks an entry
  permanently**
- Generate `run_id` server-side, or bind a client-supplied one to the
  authenticated user
- Bound the store: TTL plus a maximum entry count
- Call `clear_progress` on failure as well as success

**The test that matters:** subscribe to the WebSocket, trigger a solve, assert a
message arrives. That test fails today and is the only genuine proof the
feature works. Everything else in this PR is bookkeeping by comparison.

**Gate:** the message-arrival test passes; a churn test shows the store stays
within bounds.

---

## 6. Wave 4 — High, non-security backend

### PR 4.1 — H9: migrate once, not per replica

`app/database.py:81-82` calls `runner.start()` and then `runner.join()`
immediately. The migration thread is joined synchronously inside the lifespan,
so **every** replica runs `alembic upgrade head` concurrently at startup.

- Remove the join and the startup migration
- Move `alembic upgrade head` to a pre-deploy job or a single-replica init
  service

Test: two app instances against one database converge on head.

> This changes deploy semantics. Anyone relying on "push and it migrates" will
> break. It needs a compose job and a note in
> [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md), not just a code change.

### PR 4.2 — H10: parallelize export legs

`app/services/export.py:167` awaits each leg in a sequential loop, so an
N-vehicle export makes N serial round trips. `app/services/directions.py:217`
already has the correct `asyncio.gather` pattern — mirror it, then add a
semaphore and a deadline so concurrency stays bounded.

Test: leg count preserved, wall-clock bounded.

### PR 4.3 — H11: bound Prometheus label cardinality

`app/middleware/metrics.py:51,62-63` labels on the raw request path, so every
`run_id` becomes a distinct time series. The series count grows with traffic
and will eventually take down the scrape target.

- Resolve the route template before the span is created. This needs pure-ASGI
  middleware or equivalent, because the route is not yet matched when the
  middleware opens the span

Test: two different `run_id` values produce one series, not two.

**Gate:** suite green; migrations no longer run in the lifespan.

---

## 7. Wave 5 — Frontend auth

Must follow Wave 1, because 5.3 needs the shape C5 introduces.

### PR 5.1 — F2: one request wrapper

Extract a single `apiFetch` used by `frontend/src/api.js`: timeout via
`AbortController`, normalized error shape, and a single place for
`credentials`. Pure refactor, no behaviour change. It exists so 5.2 is a
mechanical change rather than a redesign, and it is the only reason to keep the
current per-module fetch helpers out of the way.

### PR 5.2 — F1 + F3: httpOnly cookies and CSRF

The largest PR in the plan. Backend sets cookies; the client stops touching
token storage; `localStorage` keeps nothing.

See §1.1 for why this is smaller than it looks. F1 arrives for free: the client
retries a 401 and the server refreshes transparently.

A side effect: the cookie change keeps every request same-origin, so CSP
`connect-src 'self'` (`nginx.conf:59`) stays sufficient. Setting `VITE_API_URL`
to an absolute cross-origin URL later would require widening `connect-src` at
the same time.

Land backend and frontend as separate commits if review is easier; keep one PR
so the intermediate state is never deployed.

### PR 5.3 — F4 + F5: route guards

- Role guard in `ProtectedRoute`
  (`frontend/src/components/ProtectedRoute.jsx:4-34`).
  Depends on C5 for the platform-admin shape
- Deep-link 401 handling. `ProtectedRoute.jsx:32` redirects to `/login` with no
  `from`, so a page reload on a deep link loses the destination

**Gate:** frontend suite grows to cover refresh, 401 retry, and guard
redirects; no token in `localStorage`.

---

## 8. Risks

Named up front, because each one has a plausible way to go wrong.

1. **F3 is the highest-risk PR.** It changes auth transport and adds CSRF. 5.1
   exists to keep it mechanical. Do not combine it with 5.3.
2. **C5 needs a bootstrap answer.** If the platform-admin flag is driven by an
   env var that is unset, nobody can administer anything and the fix is an
   outage. Decide the mechanism — seed from `PLATFORM_ADMIN_EMAILS`, or a
   one-shot script — before starting 1.4.
3. **H9 breaks deploy assumptions.** Removing startup migrations means a deploy
   without the migration step fails at runtime instead of at boot. The compose
   job and the documentation update are part of the PR, not follow-ups.
4. **Wave 0 is genuinely blocking.** 1.3 and 1.4 without 0.1 and 0.2 are
   unverifiable security changes. Do not reorder to save a day.
5. **H3 is insurance, not an outage.** Revisit below.

### 8.1 Correction: H3 is latent, not live

`app/main.py:89` sets `allow_methods=["GET","POST","OPTIONS"]` while the app
exposes PATCH, PUT and DELETE routes.

The roadmap states the deployed topology is cross-origin, and concludes those
endpoints fail preflight. **That conclusion is wrong.** Both shipped topologies
are same-origin from the browser's perspective:

- Compose: `nginx.conf` serves the SPA at `/` and proxies `/api/` to the
  backend. Compose binds both services to `127.0.0.1` only
- Kubernetes: the ingress (`k8s/frontend.yaml:50-91`) is a **single host**,
  `vrp.example.com`, routing `/api/` and `/` to different services on the same
  hostname
- Vite dev server proxies `/api`, so development matches production

No cross-origin preflight occurs, so PATCH/PUT/DELETE work today.

The configuration is still wrong and should be fixed: it breaks the moment
anyone splits the origins, e.g. `api.example.com`. The related smell is
`.env.production.example` shipping localhost origins.

Fix the three words. Do not schedule it as an emergency, and do not describe it
as a current outage.

---

## 9. Out of scope

Recorded here so these are visibly deferred, not forgotten.

- **All medium and low findings** — PII in logs, dead code, sync-in-async,
  unbounded queries, plan-entitlement enforcement (`export_enabled` and
  `max_users` are declared in `app/services/plans.py:17,19` and never
  enforced), silent exception swallowing, user enumeration
- **Production readiness** — Redis-backed rate limiting (Wave 2 fixes keying
  and leaves the limiter in-process), GHCR publishing, blue-green deploy,
  branch protection, re-enabling the backend coverage gate
- **TypeScript migration**
- **passlib → bcrypt migration** — blocked on `hash_password` and
  `verify_password` (`app/services/auth.py:25,29`) having zero test coverage.
  PR 0.2 partially unblocks this by giving them their first tests
- **Backend coverage gate** — `--ignore=tests/test_api.py`
  (`.github/workflows/ci.yml:72`) excludes the largest test file. That
  `--cov` interaction is itself unresolved and is worth a dedicated
  investigation

---

## 10. Verification

Run per PR. Full suite at each wave gate.

```bash
# Backend  (258 tests, ~129s on this checkout)
cd backend && python -m pytest -q

# Frontend  (matches .github/workflows/ci.yml)
cd frontend && npm run lint
cd frontend && npm run format:check
cd frontend && npm run test:ci     # vitest run --coverage
cd frontend && npm run build
```

Use `npm run test:ci`, not `npm test`, so coverage is actually collected.

If the backend run stalls, check whether `backend/.env` exists. See PR 0.1 —
`config.py:96` loads it at import time, so a `DATABASE_URL` pointing at an
unreachable Postgres makes the suite hang rather than fail. CI has no `.env`,
which is why the baseline is 258/258 there and unbounded locally.

| Wave | Gate |
|---|---|
| 0 | 258+ backend green; pure additions |
| 1 | Full backend green; migration downgrades cleanly |
| 2 | Unauth / wrong-type WebSocket rejected; status endpoint requires auth |
| 3 | Progress message actually arrives; store stays bounded |
| 4 | Suite green; no migration in the lifespan |
| 5 | No token in `localStorage`; refresh and guard tests green |

Coverage floors only move **up**. New code ships with tests in the same PR; the
gate stays disabled until the `--ignore` question in §9 is resolved.

---

## 11. Open items carried forward

Not part of this plan, but they change what the plan can achieve and should not
be rediscovered later.

| Item | Effect |
|---|---|
| The `--cov` / `--ignore=tests/test_api.py` interaction | Unresolved. Until it is understood, the backend coverage gate stays off and the ~60% figure understates real coverage |
| Roadmap H3 severity | The roadmap concludes CORS breaks PATCH/PUT/DELETE today. Both shipped topologies are same-origin (§8.1). The config is still wrong; the outage is not real |
| `hash_password` / `verify_password` have no tests | Blocks the passlib → bcrypt migration. PR 0.2 is the first step |
| Admin-gated settings | Branch protection, `GHCR_TOKEN`, blue-green secrets, and the Dependabot **security updates** toggle live in Settings → Code security. Removing `dependabot.yml` did not disable that toggle |
| Stale documents | `IMPROVEMENT_PLAN.md` and `BUSINESS_ROADMAP.md` are superseded by `TECHNICAL_ROADMAP.md` §5. Worth archiving so they stop being cited as current |
