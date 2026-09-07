# 🚀 VRP Logistics — Improvement Roadmap

A prioritized plan for fixing critical issues, adding features, and preparing the application for production use.

---

## 🔴 Phase 1 — Critical Fixes

**Goal:** Eliminate security vulnerabilities and stability issues.

| # | Issue | File(s) | Severity |
|---|-------|---------|----------|
| 1 | **RCE via pickle.loads()** — Redis deserialization can execute arbitrary code | `backend/app/services/cache.py:10,57` | Critical |
| 2 | **Sync solver blocks event loop** — All requests hang for up to 60s | `backend/app/optimization/vrp_solver.py:101` | Critical |
| 3 | **CORS wildcard `*`** with credentials — any site can call the API | `backend/app/config.py:29` | Critical |
| 4 | **Exception text leaked to clients** — exposes paths, versions, internals | `backend/app/main.py:80`, `routes/optimization.py:40` | High |
| 5 | **No React error boundary** — component crash = white screen, no recovery | `frontend/src/App.jsx` | High |

---

## 🟠 Phase 2 — Security Hardening

**Goal:** Protect against abuse and prepare for production deployment.

| # | Issue |
|---|-------|
| 6 | No rate limiting on expensive VRP endpoint (DoS risk) |
| 7 | No authentication or authorization on any endpoint |
| 8 | No request body size limit — multi-GB payloads possible |
| 9 | Redis has no password configured |
| 10 | nginx missing security headers (CSP, HSTS, X-Frame-Options, etc.) |
| 11 | OSRM/ORS response structure not validated before indexing |
| 12 | No HTTPS/TLS — HTTP-only currently |

---

## 🟡 Phase 3 — Testing

**Goal:** Establish a safety net before making further changes.

### Backend Tests

| # | Test Type | What to Test |
|---|-----------|-------------|
| 13 | Unit tests | `haversine_km()`, `_scale_matrix()`, Pydantic validators, cache key generation |
| 14 | Solver tests | `solve_vrp()` with synthetic matrices (no API needed) |
| 15 | Integration tests | API endpoints with FastAPI `TestClient` |

### Frontend Tests

| # | Test Type | What to Test |
|---|-----------|-------------|
| 16 | Unit tests | `genSample()`, `vehicleColor()`, API functions |
| 17 | Component tests | React Testing Library for critical components |
| 18 | E2E tests | Playwright or Cypress for critical user flow |

---

## 🔵 Phase 4 — CI/CD & Tooling

**Goal:** Automate quality checks on every commit.

| # | Item | Details |
|---|------|---------|
| 19 | GitHub Actions CI | Lint, test, build, Docker image build |
| 20 | Python linter/formatter | ruff + black |
| 21 | Frontend linter | ESLint + Prettier |
| 22 | Pre-commit hooks | `.pre-commit-config.yaml` |

---

## 🟢 Phase 5 — High-Value Features

**Goal:** Add features that directly improve user experience.

| # | Feature | Description | Effort |
|---|---------|-------------|--------|
| 23 | ✅ Live progress tracking | WebSocket or polling with real solver status | Medium |
| 24 | ✅ Unassigned locations on map | Currently invisible — `MapView.jsx:127` | Low |
| 25 | ✅ Route turn-by-turn details | Stop names, arrival times, demand per stop | Medium |
| 26 | ✅ Route export (CSV, GPX) | Download optimized routes | Medium |
| 27 | ✅ JSON upload validation | Validate schema before sending to server | Low |
| 28 | ✅ Solver configuration UI | Time limit, algorithm choice, iterations | Low |
| 29 | ✅ URL state / shareable results | Bookmark or share result views | Medium |
| 30 | ✅ Dark/light theme toggle | CSS custom properties already support it | Low |

> **Phase 5 complete.** Turn-by-turn directions (item 25) shipped on `feat/turn-by-turn`:
> new `GET /api/v1/routes/{job_id}/directions` endpoint backed by OSRM/ORS leg fetching with
> Redis + LRU caching and fail-soft fallback, plus a Directions tab in the results panel.
> Progress polling fallback added when the WebSocket is unavailable.

---

## ⚪ Phase 6 — Code Quality

**Goal:** Improve maintainability and performance.

| # | Issue | File(s) |
|---|-------|---------|
| 31 | ✅ Dead code: `colors.js`, `SAMPLE_LONDON_MINI`, `isDelivery` | Multiple |
| 32 | ✅ Unused deps: `tenacity`, `scipy`, `python-multipart`, `react-dropzone`, `react-leaflet`, `lucide-react` | `requirements.txt`, `package.json` |
| 33 | ✅ Unused API functions: `getRoutes()`, `checkHealth()` | `frontend/src/api.js` |
| 34 | ✅ Haversine uses O(n²) Python loop instead of vectorized NumPy | `distance_matrix.py:57-62` |
| 35 | ✅ O(n) `list.index()` inside comprehension | `optimizer.py:74` |
| 36 | ✅ Deprecated `@app.on_event("startup")` — use `lifespan` | `main.py:84` |
| 37 | ✅ Zero accessibility: no ARIA, keyboard nav, focus indicators | All components |
| 38 | ✅ No responsive design — zero `@media` queries | All CSS |
| 39 | ✅ No `prefers-reduced-motion` support | `index.css` |
| 40 | ✅ No request/correlation ID for log tracing | `main.py` |
| 41 | ✅ Health check doesn't reflect Redis availability | `main.py:95-101` |
| 42 | ✅ `routing_backend` is free-form string, not enum | `schemas.py:46-48` |
| 43 | ✅ `list_routes` accesses private `_job_cache` directly | `routes/optimization.py:70-71` |
| 44 | ✅ Color contrast fails WCAG AA (`--text-3: #5a6070`) | `index.css:16-17` |

> **Phase 6 complete.** Most items were already resolved on `main`; audited and documented here,
> with the remaining gaps closed on `chore/code-quality-phase6`:
> `routing_backend` is now the shared `RoutingBackend = Literal["haversine", "osrm", "ors"]`
> across `OptimizeRequest`/`OptimizeResponse`/`HealthResponse`, `config.py` fails fast on unknown
> `ROUTING_BACKEND` values, unused `python-multipart` dep removed, and a11y gaps filled
> (skip-to-content link with visible focus, `aria-live` solver progress).

---

## 📋 Phase 7 — Advanced Features (Future)

**Goal:** Long-term enhancements from the README and beyond.

| # | Feature | Effort |
|---|---------|--------|
| 45 | Time windows per delivery (VRPTW) | High |
| 46 | Real-time traffic-aware routing | High |
| 47 | Multi-depot optimization | High |
| 48 | PostgreSQL integration — wire up `database/schema.sql` | High |
| 49 | Kubernetes deployment support | High |
| 50 | Production docker-compose (separate config, resource limits) | Medium |
| 51 | Monitoring — Prometheus metrics, distributed tracing | Medium |
| 52 | Structured logging — JSON format, log levels, rotation | Low |

---

## 📄 Documentation Gaps

| # | Item |
|---|------|
| 53 | `CHANGELOG.md` |
| 54 | `CONTRIBUTING.md` |
| 55 | `SECURITY.md` |
| 56 | Production deployment guide |
| 57 | Configuration reference |

---

## 📊 Summary

| Category | Items | Priority |
|----------|-------|----------|
| Critical Fixes | 5 | 🔴 Must do first |
| Security Hardening | 7 | 🟠 Before production |
| Testing | 6 | 🟡 Safety net |
| CI/CD & Tooling | 4 | 🔵 Automation |
| High-Value Features | 8 | 🟢 User impact |
| Code Quality | 14 | ⚪ Maintainability |
| Advanced Features | 8 | 📋 Future roadmap |
| Documentation | 5 | 📄 Polish |
| **Total** | **57** | |

---

## 🎯 Recommended Execution Order

1. **Phase 1** → Fix critical bugs (1-2 days)
2. **Phase 3** → Add tests before more changes (2-3 days)
3. **Phase 4** → CI/CD automation (1 day)
4. **Phase 2** → Security hardening (1-2 days)
5. **Phase 5** → High-value features (1-2 weeks)
6. **Phase 6** → Code quality cleanup (3-5 days)
7. **Phase 7** → Advanced features (ongoing)
