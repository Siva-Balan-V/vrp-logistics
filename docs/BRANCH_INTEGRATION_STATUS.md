# Branch Integration Status

> **Target Branch:** `develop` (acts as main/trunk)
> **Generated:** July 2026

---

## Summary

| Branch | Merged into `develop`? | Merge Commit | PR Description |
|--------|----------------------|--------------|----------------|
| `docs` | ✅ Yes | `36e236e` | Merge docs: add business launch roadmap |
| `feat(Quality)` | ✅ Yes | `d8a5735` | Merge feat(Quality): dead code cleanup, performance, and code quality improvements |
| `feat(multi-depot)` | ✅ Yes | `5533bb9` | Merge feat(multi-depot): multi-depot optimization support |
| `feat(priority)` | ✅ Yes | `b4be18f` | Merge feat(priority): priority-based scheduling |
| `feat(route-export)` | ✅ Yes | `ef85f39` | Merge feat(route-export): CSV and GPX route export |
| `feat(security)` | ✅ Yes | `d111704` | Merge feat(security): rate limiting, security headers, response validation |
| `feat(time-windows)` | ✅ Yes | `e1da3af` | Merge feat(time-windows): per-delivery time windows (VRPTW) |
| `feat/auth-backend` | ✅ Yes | `43785ae` | Merge feat/auth-backend: JWT authentication system |
| `feat/auth-frontend` | ✅ Yes | `6e0f477` | Merge feat/auth-frontend: authentication UI with login, register, protected routes |
| `feat/db-models` | ✅ Yes | `cda8f37` | Merge feat/db-models: SQLAlchemy ORM models |
| `feat/db-persist` | ✅ Yes | `7e84cc0` | Merge feat/db-persist: job persistence to PostgreSQL |
| `feat/db-setup` | ✅ Yes | `05f0cb4` | Merge feat/db-setup: PostgreSQL infrastructure and Alembic |
| `feat/tenant` | ✅ Yes | `da8a621` | Merge feat/tenant: company management endpoints |
| `hotfix` | ✅ Yes | `158e35f` | Merge hotfix: critical security and reliability fixes |
| `test` | ✅ Yes | `b56e1f5` | Merge test: add pytest and vitest testing infrastructure with unit and integration tests |
| **`main`** | **❌ No** | — | Stale — behind develop by ~15 feature merges |

---

## 1. `docs` → `develop`

**Status:** ✅ Merged via `36e236e`

**PR Description:**
Add business launch roadmap documenting 6 milestones for transforming the prototype into a production-ready SaaS product, covering persistence, VRP enhancements, real-time operations, analytics, billing, and production ops.

**Branch-specific commits:**
| Commit | Description |
|--------|-------------|
| `c29165a` | docs: add business launch roadmap with 6 milestones |

**Files changed:** `docs/BUSINESS_ROADMAP.md`

---

## 2. `feat(Quality)` → `develop`

**Status:** ✅ Merged via `d8a5735`

**PR Description:**
Code quality improvements across backend and frontend:
- Remove dead code (`colors.js`, `SAMPLE_LONDON_MINI`, `isDelivery`)
- Remove unused dependencies from both `requirements.txt` and `package.json`
- Remove unused API functions (`getRoutes`, `checkHealth`)
- Vectorize Haversine matrix with NumPy for 10-100x speedup
- Replace deprecated `@app.on_event` with lifespan context manager
- Use `Literal` type for `routing_backend` instead of free string
- Add `public list_jobs()` to replace private `_job_cache` access
- Add `X-Request-ID` header for log tracing
- Include Redis status in health check response
- Improve `text-3` color contrast to meet WCAG AA

**Branch-specific commits:**
| Commit | Description |
|--------|-------------|
| `48ef73c` | chore(frontend): remove dead code (colors.js, SAMPLE_LONDON_MINI, isDelivery) |
| `d719db5` | chore: remove unused dependencies from backend and frontend |
| `02e77dc` | chore(frontend): remove unused API functions (getRoutes, checkHealth) |
| `0fc0d93` | perf(backend): vectorize Haversine matrix with NumPy for 10-100x speedup |
| `d4625f3` | refactor(backend): replace deprecated on_event with lifespan context manager |
| `8f9368d` | refactor(backend): use Literal type for routing_backend instead of free string |
| `75e33a3` | refactor(backend): add public list_jobs() to replace private _job_cache access |
| `8bdb11c` | feat(backend): add X-Request-ID header for log tracing |
| `4dabfe5` | fix(backend): include Redis status in health check response |
| `79c04cf` | fix(frontend): improve text-3 color contrast to meet WCAG AA |

---

## 3. `feat(multi-depot)` → `develop`

**Status:** ✅ Merged via `5533bb9`

**PR Description:**
Add multi-depot optimization support allowing multiple depots in a single optimization request with each vehicle assigned to a specific depot, plus frontend UI for depot management.

**Branch-specific commits:**
| Commit | Description |
|--------|-------------|
| `60950ab` | feat(multi-depot): support multiple depots in optimization |
| `345c51a` | feat(multi-depot): add multi-depot UI to frontend |
| `f006a6d` | feat(multi-depot): support multiple depots in optimization |

---

## 4. `feat(priority)` → `develop`

**Status:** ✅ Merged via `b4be18f`

**PR Description:**
Add priority-based scheduling with a `priority` field (1-5) for deliveries. High-priority stops are visited first within constraints, with visual priority indicators on the map and comprehensive tests.

**Branch-specific commits:**
| Commit | Description |
|--------|-------------|
| `5b412ee` | feat(priority): add priority-based scheduling to solver |
| `71de1ea` | feat(priority): add priority display to frontend |
| `f291b50` | test(priority): add tests for priority-based scheduling |

---

## 5. `feat(route-export)` → `develop`

**Status:** ✅ Merged via `ef85f39`

**PR Description:**
Add route export functionality supporting CSV and GPX formats. Includes backend export endpoints, frontend download buttons in the results panel, and unit tests.

**Branch-specific commits:**
| Commit | Description |
|--------|-------------|
| `353ebdc` | feat(export): add CSV and GPX route export endpoints |
| `acacba6` | feat(export): add CSV/GPX export buttons to results panel |
| `026d49e` | test(export): add unit tests for CSV and GPX generation |

---

## 6. `feat(security)` → `develop`

**Status:** ✅ Merged via `d111704`

**PR Description:**
Security hardening including rate limiting on expensive VRP endpoints, security headers (CSP, HSTS, X-Frame-Options), OSRM/ORS response structure validation, and Redis authentication documentation.

**Branch-specific commits:**
| Commit | Description |
|--------|-------------|
| `53c4751` | docs(security): document Redis authentication in env config |

*(plus earlier commits merged in this feature branch)*

---

## 7. `feat(time-windows)` → `develop`

**Status:** ✅ Merged via `e1da3af`

**PR Description:**
Add per-delivery time windows (VRPTW) support. Extends the solver with a time window dimension, adds frontend time picker per delivery stop, and includes unit tests.

**Branch-specific commits:**
| Commit | Description |
|--------|-------------|
| `c4073cf` | feat(vrptw): add per-delivery time windows to solver |
| `ea7160a` | feat(vrptw): add time window toggle to frontend generate form |
| `d9a3e0b` | test(vrptw): add unit tests for time windows feature |

---

## 8. `feat/auth-backend` → `develop`

**Status:** ✅ Merged via `43785ae`

**PR Description:**
Implement JWT-based authentication system with register, login, token refresh, and current user endpoints. Includes password hashing, token generation, and protected route dependencies.

**Branch-specific commits:**
| Commit | Description |
|--------|-------------|
| `5723c5a` | feat(auth): add JWT authentication with register, login, refresh, me |

---

## 9. `feat/auth-frontend` → `develop`

**Status:** ✅ Merged via `6e0f477`

**PR Description:**
Add authentication UI with login and register pages, auth context with token storage, and protected route redirects for the React frontend.

**Branch-specific commits:**
| Commit | Description |
|--------|-------------|
| `5b89a31` | feat(frontend): add authentication flow with login, register, and protected routes |

---

## 10. `feat/db-models` → `develop`

**Status:** ✅ Merged via `cda8f37`

**PR Description:**
Add SQLAlchemy ORM models defining all database tables (users, companies, optimization_jobs, api_keys) with proper relationships and type-safe async support.

**Branch-specific commits:**
| Commit | Description |
|--------|-------------|
| `36b0e98` | feat(db): add SQLAlchemy ORM models for all tables |

---

## 11. `feat/db-persist` → `develop`

**Status:** ✅ Merged via `7e84cc0`

**PR Description:**
Wire optimization routes to persist job data to PostgreSQL, replacing the in-memory LRU job cache with database-backed persistence while keeping Redis for distance matrix caching.

**Branch-specific commits:**
| Commit | Description |
|--------|-------------|
| `445a840` | feat(db): wire optimization routes to persist jobs to PostgreSQL |

---

## 12. `feat/db-setup` → `develop`

**Status:** ✅ Merged via `05f0cb4`

**PR Description:**
Add PostgreSQL service configuration, SQLAlchemy async engine setup, and Alembic migration infrastructure for schema versioning.

**Branch-specific commits:**
| Commit | Description |
|--------|-------------|
| `4300c6f` | feat(db): add PostgreSQL service, SQLAlchemy, and Alembic infrastructure |

---

## 13. `feat/tenant` → `develop`

**Status:** ✅ Merged via `da8a621`

**PR Description:**
Add company management endpoints for multi-tenant support. Includes companies table, user-company relationships, and data scoped by company_id.

**Branch-specific commits:**
| Commit | Description |
|--------|-------------|
| `b199538` | feat(tenant): add company management endpoints |

---

## 14. `hotfix` → `develop`

**Status:** ✅ Merged via `158e35f`

**PR Description:**
Critical security and reliability fixes addressing top-priority issues from the improvement plan, including React error boundary to prevent blank screen crashes, fixes for critical vulnerabilities.

**Branch-specific commits:**
| Commit | Description |
|--------|-------------|
| `78aac2e` | fix(frontend): add error boundary to prevent blank screen on crash |

*(includes additional fixes from the hotfix branch)*

---

## 15. `test` → `develop`

**Status:** ✅ Merged via `b56e1f5`

**PR Description:**
Add comprehensive testing infrastructure with pytest (backend) and vitest (frontend). Includes unit tests for distance matrix, schemas, cache, and API integration tests using FastAPI TestClient, plus frontend tests for API utilities and vehicle colors.

**Branch-specific commits:**
| Commit | Description |
|--------|-------------|
| `5c63cf8` | test: add pytest and vitest testing infrastructure |
| `45d09ae` | test(backend): add unit tests for distance matrix, schemas, and cache |
| `2750974` | test(backend): add API integration tests using FastAPI TestClient |
| `3eb83ec` | test(frontend): add unit tests for API utilities and vehicle colors |

---

## 16. `main` → `develop` ❌ NOT MERGED

**Status:** ❌ Not merged into `develop`

**Details:**
- Contains 1 commit not in `develop`: `362cd4b` — `Merge pull request #2 from Siva-Balan-V/develop`
- This is an older merge commit that brought an earlier version of `develop` into `main`
- `main` is **~15 feature merges behind** `develop`
- Since `develop` is now the trunk, `main` is stale

**Recommendation:**
- **Delete** the local `main` branch (`git branch -d main`)
- **Delete** or archive the remote `main` branch (`git push origin --delete main`)
- All future work targets `develop`

---

## Branch → Target Mapping

| Source Branch | Target Branch | Merge Type | Status |
|---------------|---------------|------------|--------|
| `docs` | `develop` | Merge commit | ✅ Done |
| `feat(Quality)` | `develop` | Merge commit | ✅ Done |
| `feat(multi-depot)` | `develop` | Merge commit | ✅ Done |
| `feat(priority)` | `develop` | Merge commit | ✅ Done |
| `feat(route-export)` | `develop` | Merge commit | ✅ Done |
| `feat(security)` | `develop` | Merge commit | ✅ Done |
| `feat(time-windows)` | `develop` | Merge commit | ✅ Done |
| `feat/auth-backend` | `develop` | Merge commit | ✅ Done |
| `feat/auth-frontend` | `develop` | Merge commit | ✅ Done |
| `feat/db-models` | `develop` | Merge commit | ✅ Done |
| `feat/db-persist` | `develop` | Merge commit | ✅ Done |
| `feat/db-setup` | `develop` | Merge commit | ✅ Done |
| `feat/tenant` | `develop` | Merge commit | ✅ Done |
| `hotfix` | `develop` | Merge commit | ✅ Done |
| `test` | `develop` | Merge commit | ✅ Done |
| `main` | `develop` | — | ❌ Pending (stale) |

---

## Git DAG (Simplified)

```
main  ──o──o──o──o──o──o──o──o──o──o──o──o──o──o──o──o──362cd4b (PR #2 from develop)
       │
develop└──docs──db-setup──db-models──db-persist──auth-backend──tenant──auth-frontend──route-export──time-windows──multi-depot──priority──hotfix──test──security──Quality
       │     │         │           │            │            │       │            │              │            │           │        │      │        │          │
       │    36e236e   05f0cb4     cda8f37     7e84cc0      43785ae da8a621     6e0f477       ef85f39      e1da3af     5533bb9  b4be18f 158e35f  b56e1f5   d111704   d8a5735
       ▼
  All feature branches merged into develop ✓
```

---

## Notes

- All future feature branches should be created from `develop`
- PRs must target `develop` for integration
- After PR merge, delete the source branch to keep the repo clean
- `main` is stale and can be archived/deleted
