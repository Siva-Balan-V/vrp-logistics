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

| Branch | PR | CI | Blocker (verified from run logs) |
|--------|---:|----|------------------------------------|
| `dependabot/npm_and_yarn/frontend/react-router-dom-7.18.4` | [#19](https://github.com/Siva-Balan-V/vrp-logistics/pull/19) | **12/12 green, CLEAN** | none — **merge this one now** |
| `dependabot/npm_and_yarn/frontend/multi-7f19880bf6` | [#17](https://github.com/Siva-Balan-V/vrp-logistics/pull/17) | 6 fail | `npm ci` ERESOLVE: `@types/react-dom@18.3.7` peers `@types/react@^18` |
| `dependabot/npm_and_yarn/frontend/multi-de36fa8f59` | [#16](https://github.com/Siva-Balan-V/vrp-logistics/pull/16) | 6 fail | same ERESOLVE — merge jointly with #17 |
| `dependabot/npm_and_yarn/frontend/dev-deps-f586ce92d0` | [#20](https://github.com/Siva-Balan-V/vrp-logistics/pull/20) | 6 fail | `npm ci` ERESOLVE: `eslint-plugin-react@7.37.5` peers `eslint ≤ 9.7`, PR bumps to 10.11.0 |
| `dependabot/pip/backend/runtime-deps-9fd38ec251` | [#12](https://github.com/Siva-Balan-V/vrp-logistics/pull/12) | 7 fail | `numpy>=2.5.3` needs Python ≥3.12, CI pins 3.11 → **install fails**; also bcrypt 5.0.0 breaks passlib |

Every failure above is a `npm ci` / `pip install` resolution error, not a test
failure — no dependabot branch has a code-level regression.

## Recommended order

Sections below are numbered in this merge order, not by PR number.

1. **#19** — merge as-is. Green, no code changes needed.
2. **#16 + #17 → one PR** — combine into a single React 19 bump.
3. **#20 → rework** — hold `eslint` at `^9`, then re-split toolchain vs lint majors.
4. **#12 → rework** — fix the numpy floor *and* hold bcrypt; decide on passlib.

## Baseline on `main`

Green at `5a1711f`, so any failure after a bump is attributable to the bump:

- Backend: `pytest` → 258 passed (Python **3.14** local venv).
- Frontend: `npm test` (vitest 2.1.9) → 36/36 passed across 7 files;
  prettier clean, `vite build` clean, eslint 0 errors / 175 warnings.

⚠️ **The local Python is 3.14 but CI pins `PYTHON_VERSION: "3.11"`
(`.github/workflows/ci.yml:10`).** A green local run is therefore *not*
equivalent to CI for dependency-floor work — this is exactly why the
`numpy>=2.5.3` breakage in #12 was invisible locally. Verify dependency changes
on 3.11, or raise the CI pin.

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

---


## 1. `dependabot/npm_and_yarn/frontend/react-router-dom-7.18.4` → `main` (PR #19)

> Base: `main` · 1 commit · +43 / −24 across 2 files

```markdown
## Summary
Bumps `react-router-dom` 6.23.0 → 7.18.4 in `/frontend`. Despite being a major
version, **all 12 CI checks pass and no source changes are needed** — merge as-is.

**1 commit · +43 / −24 across 2 files**

## Verification
- `npm ci`, Frontend Lint, Frontend Tests (36/36), Frontend Build, dependency
  audit: all green.
- Full check rollup: 12/12 SUCCESS, `mergeStateStatus: CLEAN`.

## Note
The React Router 6 → 7 data-API codemod (`npx @react-router/upgrade`) is not
required here. v7 keeps the v6 component APIs working, and this codebase stays
on the declarative `<BrowserRouter>`/`<Routes>` style rather than the data
routers, so nothing in `src/main.jsx` or the protected-route wrappers changes.

Worth a manual smoke test before release, since redirect semantics differ
subtly and no test covers an unauthenticated deep link:

    login → optimize → dispatch → route details

    and: deep-link to a protected route unauthenticated, expect redirect to
    login and back to the original URL.
```

---


## 2. `dependabot/npm_and_yarn/frontend/multi-de36fa8f59` → `main` (PR #16)

> Base: `main` · 1 commit · +17 / −21 across 2 files

```markdown
## Summary
Bumps `react-dom` 18.3.1 → 19.3.0 and `@types/react-dom` 18.3.0 → 19.3.0 in
`/frontend`. **Merge together with PR #17 — the two are not independently
shippable.**

**1 commit · +17 / −21 across 2 files**

## Why
Same ERESOLVE as PR #17, from the other direction: `react-dom@19` peers
`react@^19` while `react` is still 18.3.1. Both halves of the React 19 bump must
land in one commit.

## Verification
- `npm ci && npm test` → 36/36 passed (run after the combined PR lands).
- `npm run build` clean.
```

---


## 3. `dependabot/npm_and_yarn/frontend/multi-7f19880bf6` → `main` (PR #17)

> Base: `main` · 1 commit · +10 / −21 across 2 files

```markdown
## Summary
Bumps `react` 18.3.1 → 19.3.0 and `@types/react` 18.3.3 → 19.3.0 in
`/frontend`. **Cannot be merged alone** — it must be combined with PR #16
(react-dom 19), because on its own `npm ci` cannot resolve the tree.

**1 commit · +10 / −21 across 2 files**

## ⛔ Blocker: split-bump ERESOLVE
From the run log:
```
npm error code ERESOLVE
npm error While resolving: @types/react-dom@18.3.7
npm error Found: @types/react@19.3.0
npm error Could not resolve dependency:
npm error peer @types/react@"^18.0.0" from @types/react-dom@18.3.7
```
This PR raises `@types/react` to 19 while `@types/react-dom` stays at 18.3.x,
which peers on `@types/react@^18`. Dependabot split one logical React 19 bump
across two PRs; each half is individually unsatisfiable.

Fix: close #16 and #17, and open a single PR bumping all four together —
`react`, `react-dom`, `@types/react`, `@types/react-dom` → 19.x. Then re-run
dependabot so it does not re-propose them separately.

## Known impact once unblocked
- React 19 removes `ReactDOM.render`, string refs, legacy context, and the
  `propTypes` runtime check.
- **146 `react/prop-types` eslint warnings** (docs/CI_PIPELINE_PLAN.md:25) — the
  runtime check those warnings stand in for is gone in 19, so this bump should
  be sequenced with the `lint:strict` burn-down or the warnings become
  load-bearing.
- Test roots in `src/__tests__/*.jsx` mount via `ReactDOM.createRoot`; verify the
  React 19 `act` environment flag still holds.

## Verification
- `npm ci && npm test` → 36/36 passed.
- `npm run lint && npm run build` clean.
```

---


## 4. `dependabot/npm_and_yarn/frontend/dev-deps-f586ce92d0` → `main` (PR #20)

> Base: `main` · 1 commit · +1,596 / −2,275 across 2 files

```markdown
## Summary
Bumps 14 frontend dev dependencies, four of them across major versions.
**Cannot be merged as-is** — the PR is internally inconsistent and `npm ci`
fails.

**1 commit · +1,596 / −2,275 across 2 files**

## ⛔ Blocker: `eslint` 10 has no compatible `eslint-plugin-react`

From the run log:
```
npm error code ERESOLVE
npm error ERESOLVE could not resolve
npm error Found: eslint@10.11.0
npm error Could not resolve dependency:
npm error peer eslint@"^3 || ^4 || ^5 || ^6 || ^7 || ^8 || ^9.7" from eslint-plugin-react@7.37.5
```
`eslint-plugin-react@7.37.5` is capped at eslint 9.7, but this PR raises eslint
to 10.11.0 in the same commit. Six frontend checks fail at `npm ci`.

Fix: hold `eslint` at `^9.39.5` (and `@eslint/js` at `^9`) for now, and revisit
when `eslint-plugin-react` publishes ESLint 10 support. `globals` and the other
lint packages are fine on eslint 9.

## Bumps
- Build/test toolchain (all major): `vite` 5.3.1 → 8.3.0, `vitest` 2.0.0 →
  5.0.1, `@vitest/coverage-v8` 2.1.9 → 5.0.1, `@vitejs/plugin-react` 4.3.1 →
  6.1.1.
- Lint: `eslint` 9.0.0 → 10.11.0 (**blocked**, see above), `@eslint/js` 9.0.0 →
  10.0.1 (**blocked** with it), `eslint-plugin-react-hooks` 5.0.0 → 7.1.1,
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
- **The 175-warning burn-down target moves.** Re-baseline `npm run lint` after
  this lands, before starting the `--max-warnings 0` work
  (docs/CI_PIPELINE_PLAN.md:279).
- `eslint-plugin-react-hooks` 5 → 7 brings the React Compiler-aware rules; the
  existing single `react-hooks/exhaustive-deps` warning may change shape.
- `jsdom` 30 is a large jump — the `a11y.test.jsx` jest-axe smoke tests are the
  canary.

## Suggested split
Once eslint is held back, this PR is still four majors in one commit. Split it:
1. Toolchain: `vite`, `@vitejs/plugin-react`, `vitest`, `@vitest/coverage-v8`.
2. Test env: `jsdom`, `@testing-library/*`, `prettier`.
3. Lint (once ESLint 10 is viable): `eslint`, `@eslint/js`,
   `eslint-plugin-react-hooks`, `globals`.

## Verification
- `npm ci && npm run format:check && npm run lint && npm test && npm run build`.
- Confirm `npm run test:ci` coverage output still clears the thresholds in
  `vite.config.js`.
```

---


## 5. `dependabot/pip/backend/runtime-deps-9fd38ec251` → `main` (PR #12)

> Base: `main` · 1 commit · +23 / −23 across 1 file

```markdown
## Summary
Bumps 23 backend runtime dependency floors in `backend/requirements.txt`. **Do
not merge as-is — it fails `pip install` before a single test runs, and it also
carries a runtime-breaking auth change.**

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

## ⛔ Blocker 1: `numpy>=2.5.3` cannot install on CI's Python 3.11

`.github/workflows/ci.yml:10` pins `PYTHON_VERSION: "3.11"`. numpy 2.5.x
declares `Requires-Python >=3.12`, so `pip install -r requirements.txt` fails
with `No matching distribution found for numpy>=2.5.3`. Every backend job
(Alembic, Backend Tests, Backend Lint, Backend Coverage, Docker Build, Compose
smoke) fails at the install step — 7 of 12 checks red.

Fix, pick one:
- Hold `numpy>=2.3.0` (2.4.6 is the newest release with 3.11 wheels), or
- Raise `PYTHON_VERSION` to `"3.12"` across `ci.yml`, `e2e.yml`,
  `security.yml`, `db-migrations.yml` and the backend `Dockerfile`. This is the
  better long-term move — 3.11 is the oldest supported CPython — but it is a
  deliberate policy change, not a dependabot merge.

Note the local `.venv` is Python 3.14, which is why this was invisible locally.

## ⛔ Blocker 2: `bcrypt` 5.0.0 breaks every password hash and verify

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

Fix, pick one:
1. **Hold `bcrypt==4.0.1`** in this PR and drop passlib in a follow-up.
2. Bump to `bcrypt==4.3.0` (newest passlib 1.7.4 tolerates) and defer passlib
   removal.
3. Migrate off passlib first — it has been unmaintained since 2020 — then take
   bcrypt 5. `app/services/auth.py:11-21` is the only call site, so this is a
   small, contained change.

## Other watch items
- 21 of the 23 bumps are floors the local `.venv` already exceeds, so the green
  baseline above is effectively a post-bump run — bcrypt 5 is the sole
  runtime exception.
- `stripe` 10 → 15 spans five majors; `pip-audit` in `security.yml` is the gate.

## Verification
- `ruff format --check . && ruff check .` clean.
- `pytest` → 258 passed.
```
