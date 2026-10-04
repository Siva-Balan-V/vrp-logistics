# Pull Request Descriptions

Ready-to-paste PR descriptions for branches that still carry commits not merged
into `main`. Branch push state, merge base, and change size are noted for each.

**Remote:** `https://github.com/Siva-Balan-V/vrp-logistics.git`
**Base:** `main` at `5a1711f` (PR #9, dependabot actions bump)

## Status

Every product and CI branch is merged. All 24 local branches and all remote
branches except the five open dependabot branches are ancestors of `main`, so
**no feature-branch PRs are outstanding.** The open work is dependency
upgrades, listed below.

| Branch | Commits ahead | Files | Diff | Risk |
|--------|--------------:|------:|------|------|
| `dependabot/pip/backend/runtime-deps-9fd38ec251` | 1 | 1 | +23 / −23 | **blocked** — bcrypt 5.0.0 breaks passlib (see PR 1) |
| `dependabot/npm_and_yarn/frontend/multi-7f19880bf6` | 1 | 2 | +10 / −21 | **high** — react 18 → 19 (major) |
| `dependabot/npm_and_yarn/frontend/multi-de36fa8f59` | 1 | 2 | +17 / −21 | **high** — react-dom 18 → 19 (major) |
| `dependabot/npm_and_yarn/frontend/react-router-dom-7.18.4` | 1 | 2 | +43 / −24 | **high** — react-router-dom 6 → 7 (major) |
| `dependabot/npm_and_yarn/frontend/dev-deps-f586ce92d0` | 1 | 2 | +1,596 / −2,275 | **high** — eslint 9→10, vite 5→8, vitest 2→5 |

Branches already fully contained in `main` (no PR needed, 24 local + 3
remote-only `copilot/*`): `chore/code-quality-phase6`, `develop`, `docs`,
`feat(auth-backend)`, `feat(auth-frontend)`, `feat(ci-pipelines)`,
`feat(db-models)`, `feat(db-persist)`, `feat(db-setup)`, `feat(live-dispatch)`,
`feat(multi-depot)`, `feat(priority)`, `feat(Quality)`, `feat(route-export)`,
`feat(security)`, `feat/security`, `feat(tenant)`, `feat(time-windows)`,
`feat(traffic-aware-routing)`, `feat(turn-by-turn)`, `fix/ci-green`, `hotfix`,
`test`, `copilot/add-professional-readme`,
`copilot/list-tech-stacks-and-descriptions`,
`copilot/research-technology-stack`.

## Baseline on `main`

Both suites green at `5a1711f`, so any failure after a bump is attributable to
the bump:

- Backend: `env -i PATH="$PATH" HOME="$HOME" python -m pytest` → 258 passed.
- Frontend: `npm test` (vitest 2.1.9) → 36/36 passed across 7 files.

---

## 1. `dependabot/pip/backend/runtime-deps-9fd38ec251` → `main`

> Base: `main` · 1 commit · +23 / −23 across 1 file

```markdown
## Summary
Bumps 23 backend runtime dependency floors in `backend/requirements.txt`. Every
change is a lower bound (`>=`), not an exact pin, so nothing is held back except
`bcrypt` — and the local `.venv` already resolves higher than every one of these
floors, which is why the suite is green today against the post-bump set.

**1 commit · +23 / −23 across 1 file**

## Bumps
- Framework/API: `fastapi` 0.111.0 → 0.141.1, `uvicorn[standard]` 0.30.1 →
  0.52.4, `httpx` 0.27.0 → 0.28.1, `pydantic` 2.7.4 → 2.13.5,
  `pydantic-settings` 2.3.4 → 2.15.0.
- Data: `sqlalchemy[asyncio]` 2.0.31 → 2.0.52, `asyncpg` 0.29.0 → 0.31.0,
  `alembic` 1.13.1 → 1.19.2, `numpy` 2.3.0 → 2.5.3.
- Redis/caching: `redis` 5.0.6 → 8.1.0, `cachetools` 5.3.3 → 7.1.8.
- Observability: `structlog` 24.2.0 → 26.1.0, `prometheus-client` 0.20.0 →
  0.26.0, `opentelemetry-sdk` / `-exporter-otlp-proto-grpc` 1.25.0 → 1.44.0.
- Integrations: `stripe` 10.0.0 → 15.6.1, `twilio` 9.0.0 → 9.11.0,
  `websockets` 17.0 → 17.1, `python-jose[cryptography]` 3.3.0 → 3.5.0,
  `python-dotenv` 1.0.1 → 1.2.3.
- Tooling: `ruff` 0.16.0 → 0.16.6, `pre-commit` 4.0.0 → 4.6.2.

## ⛔ Blocker: `bcrypt` 5.0.0 breaks every password hash and verify

`bcrypt` is pinned `==4.0.1` → `==5.0.0`, and `backend/requirements.txt:19`
pulls `passlib[bcrypt]>=1.7.4`. That pairing is broken. Reproduced in a
throwaway venv (`passlib==1.7.4` + `bcrypt==5.0.0`):

```
(trapped) error reading bcrypt version
AttributeError: module 'bcrypt' has no attribute '__about__'
    app/services/auth.py:21 -> pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ValueError: password cannot be longer than 72 bytes, truncate manually if necessary
```

Two separate breakages: passlib 1.7.4 reads `bcrypt.__about__.__version__`, which
bcrypt removed in 4.1, and bcrypt 5 dropped the silent 72-byte truncation that
passlib's handler depends on. `CryptContext(...)` itself raises at import time of
`app/services/auth.py`, so login, register and refresh all fail — not just new
hashes.

**Do not merge this PR as-is.** Options, in order of preference:

1. **Keep `bcrypt==4.0.1`** in this PR and open a follow-up that drops passlib
   for the stdlib-compatible path (bcrypt directly, or `argon2-cffi`). Cheapest
   and unblocks the other 22 floor bumps, which the baseline run already
   exercises.
2. Bump `bcrypt==4.0.1` → `==4.3.0` (highest version passlib 1.7.4 tolerates)
   and defer the passlib removal to its own task.
3. Migrate off passlib first, then take bcrypt 5. Correct long-term, but it is a
   code change to `app/services/auth.py`, not a dependency bump.

## Other watch items
- 22 of the 23 bumps are floors the local `.venv` already exceeds, so the
  green baseline above is effectively a post-bump run — bcrypt 5 is the sole
  exception.
- `stripe` 10 → 15 spans five majors; `pip-audit` in `security.yml` is the gate.

## Verification
- `ruff format --check . && ruff check .` clean.
- `env -i PATH="$PATH" HOME="$HOME" python -m pytest` → 258 passed.
```

---

## 2. `dependabot/npm_and_yarn/frontend/multi-7f19880bf6` → `main`

> Base: `main` · 1 commit · +10 / −21 across 2 files

```markdown
## Summary
Bumps `react` 18.3.1 → 19.3.0 and `@types/react` 18.3.3 → 19.3.0 in
`/frontend`. **Major version — needs a codemod pass, not just a green build.**

**1 commit · +10 / −21 across 2 files**

## Why it is not a routine bump
React 19 removes `ReactDOM.render`, string refs, legacy context, and the
`propTypes` runtime check; it also changes `ref` handling for function
components and defaults `use`/`act` semantics.

## Known impact in this repo
- **146 `react/prop-types` eslint warnings** (docs/CI_PIPELINE_PLAN.md:25) — the
  `propTypes` runtime check these warnings stand in for is gone in 19, so this
  bump should be sequenced with the `lint:strict` burn-down or the warnings
  become load-bearing.
- Test roots in `src/__tests__/*.jsx` mount via `ReactDOM.createRoot`; needs
  the React 19 `act` environment flag.

## Verification
- `npm ci && npm test` → 36/36 passed.
- `npm run lint && npm run build` clean.
```

---

## 3. `dependabot/npm_and_yarn/frontend/multi-de36fa8f59` → `main`

> Base: `main` · 1 commit · +17 / −21 across 2 files

```markdown
## Summary
Bumps `react-dom` 18.3.1 → 19.3.0 and `@types/react-dom` 18.3.0 → 19.3.0 in
`/frontend`. Major version; **merge together with the `react` 19 bump
(PR 2) — the two are not independently shippable.**

**1 commit · +17 / −21 across 2 files**

## Why
`react-dom` 19 must match the `react` version exactly. Merging this alone
leaves the tree on react 18 + react-dom 19, which is unsupported.

## Verification
- `npm ci && npm test` → 36/36 passed (run after PR 2 lands).
- `npm run build` clean.
```

---

## 4. `dependabot/npm_and_yarn/frontend/react-router-dom-7.18.4` → `main`

> Base: `main` · 1 commit · +43 / −24 across 2 files

```markdown
## Summary
Bumps `react-router-dom` 6.23.0 → 7.18.4 in `/frontend`. Major version with
required source changes.

**1 commit · +43 / −24 across 2 files**

## Required codemod
React Router 7 is built on the React Router 6.4+ data APIs. Run:
    npx @react-router/upgrade@latest
Then update the affected call sites by hand:
- `src/main.jsx` — `createBrowserRouter` / `RouterProvider` wiring, and the
  `<Router>` → `createBrowserRouter([...])` route-object conversion.
- Protected-route wrappers (added on `feat/auth-frontend`) — v7 moves loader/
  redirect auth guards from `<Navigate>` wrappers to `loader` functions.
- `DispatchPage` / `RouteDetails` link and `useNavigate` call sites.

## Risk
Silent behaviour change is the concern, not compilation: redirect semantics and
route matching differ enough that the 36-test suite may pass while a deep link
or the auth guard misbehaves. Manual pass over login → optimize → dispatch →
route details is required.

## Verification
- `npm test` → 36/36 passed.
- Manual: unauthenticated deep link redirects to login and back.
```

---

## 5. `dependabot/npm_and_yarn/frontend/dev-deps-f586ce92d0` → `main`

> Base: `main` · 1 commit · +1,596 / −2,275 across 2 files

```markdown
## Summary
Bumps 14 frontend dev dependencies, four of them across major versions. This is
the highest-risk open PR and should be merged **last**, after the runtime bumps
above, so any breakage is attributable.

**1 commit · +1,596 / −2,275 across 2 files**

## Bumps
- Build/test toolchain (all major): `vite` 5.3.1 → 8.3.0, `vitest` 2.0.0 →
  5.0.1, `@vitest/coverage-v8` 2.1.9 → 5.0.1, `@vitejs/plugin-react` 4.3.1 →
  6.1.1.
- Lint: `eslint` 9.0.0 → 10.11.0, `@eslint/js` 9.0.0 → 10.0.1,
  `eslint-plugin-react-hooks` 5.0.0 → 7.1.1,
  `eslint-plugin-react` 7.37.0 → 7.37.5, `globals` 15.0.0 → 17.12.0.
- Test env: `jsdom` 24.0.0 → 30.1.0, `@testing-library/react` 16.0.0 → 16.3.3,
  `@testing-library/dom` 10.4.1 → 10.4.2, `@testing-library/jest-dom` 6.4.0 →
  7.0.1.
- `prettier` 3.4.0 → 3.9.8.

## Known impact in this repo
- **Coverage thresholds move.** `frontend/vite.config.js:43-48` sets
  30/55/25 against a measured 32.76% stmts / 59.38% branch / 26.66% funcs.
  `@vitest/coverage-v8` 2 → 5 can change instrumentation, so re-measure and
  re-ratchet before committing new numbers — do not lower the floor to make the
  job pass (docs/CI_PIPELINE_PLAN.md:261).
- **The 175-warning burn-down target moves.** ESLint 10 + `eslint-plugin-react`
  7.37.5 may add or rename rules; re-baseline `npm run lint` before starting the
  `--max-warnings 0` work (docs/CI_PIPELINE_PLAN.md:279).
- `eslint-plugin-react-hooks` 5 → 7 brings the React Compiler-aware rules; the
  existing single `react-hooks/exhaustive-deps` warning may change shape.
- `jsdom` 30 is a large jump — the `a11y.test.jsx` jest-axe smoke tests are the
  canary.

## Verification
- `npm ci && npm run format:check && npm run lint && npm test && npm run build`.
- Confirm `npm run test:ci` coverage output still clears the thresholds in
  `vite.config.js`.

## Suggested sequencing
1. PR 1 (backend runtime deps) — independent, low risk.
2. PR 2 + PR 3 together (react + react-dom 19).
3. PR 4 (react-router-dom 7) — codemod, then manual route pass.
4. PR 5 (dev deps) — re-baseline lint + coverage afterwards.
```
