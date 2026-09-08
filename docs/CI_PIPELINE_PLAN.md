# CI Pipeline Fix & Expansion Plan

Status: **implemented (Phases 1–2 on `fix/ci-green` → PR #7, and `feat/ci-pipelines` → PR #8)**
– generated after reproducing failures on `main`
Reviewed against: `origin/main` (post PR #5 `feat/turn-by-turn`, PR #6 `chore/code-quality-phase6`)

## Implementation status

| Item | Status |
|------|--------|
| 1.1 config.py indent + ruff pin | ✅ PR #7 |
| 1.2 setup-node cache path + Node 22 + action bumps | ✅ PR #7 |
| 1.3 GhCR token fallback | ✅ code in PR #7; needs `GHCR_TOKEN` secret + blue-green secrets to actually publish |
| 2.1 permissions/concurrency + deploy CI gate | ✅ PR #8 |
| 2.2 coverage gates (pytest-cov + vitest coverage) | ✅ PR #8 |
| 2.3 security.yml (pip-audit, npm audit, gitleaks) | ✅ PR #8 |
| 2.4 Trivy scan | ✅ PR #8 (report-only) |
| 2.5 db-migrations.yml | ✅ PR #8 |
| 2.6 e2e.yml compose smoke | ✅ PR #8 |
| 2.7 dependabot.yml | ✅ PR #8 |
| 2.8 PR template + CODEOWNERS | ✅ PR #8 |
| 2.9 docs (this file + CONTRIBUTING) | ✅ |
| 3 coverage ratchet | ⏳ next PRs |
| 3 branch protection (required checks) | ⛔ needs admin |
| 3 eslint `--max-warnings 0` burn-down | ⏳ subsequent PRs |

### Known deviations
- **Backend coverage excludes `tests/test_api.py`**: `pytest --cov` deadlocks (hangs
  indefinitely) when tracing FastAPI `TestClient` requests via httpx threads — reproduced
  locally with `concurrency=thread` and various rcfile settings. The safe-subset coverage
  job (`backend-coverage`) runs everything except `test_api.py`, report-only by design.
  `test_api.py` still runs uncovered in the normal `backend-test` job.
- **Trivy + `npm audit`/`pip-audit` are report-only** (`continue-on-error` /
  `exit-code: 0`) so the initial baseline can be reviewed before hard-gating.
- Frontend coverage thresholds were set to just under the measured baseline
  (32.8% stmts / 59.4% branch / 26.7% funcs) and must be ratcheted up each PR.

---

## 0. Executive summary

4 checks fail on `main`, all with **confirmed root causes** (reproduced locally / via
`gh run view --log-failed`, run `34129124739`):

| Check | Result on main | Root cause (confirmed) | Fix |
|-------|----------------|------------------------|-----|
| CI / Backend Lint | ❌ | `ruff format --check .` fails: `app/config.py:85` comment at column 1 | Indent comment; pin `ruff` |
| CI / Frontend Lint | ❌ | `actions/setup-node@v4` fails: `cache: npm` looks for lockfile at repo root | `cache-dependency-path: frontend/package-lock.json` |
| CI / Frontend Tests | ❌ | same setup-node cache failure | same |
| CI / Frontend Build | ❌ | same setup-node cache failure | same |
| CI / Backend Tests | ✅ passed (was "in progress" in the screenshot) | — | none (keep deterministic) |
| CI / Docker Build Check | ✅ passed | — | none |
| Deploy / Build and push images | ❌ | `denied: permission_denied: read_package` on `ghcr.io/siva-balan-v/vrp-backend` | PAT with `write:packages` via secret; or create/link packages |

The plan below (A) fixes the 4 failures, (B) makes CI reproducible, and (C) adds the
missing pipelines + a real test methodology (coverage gates, security scans, DB
migration checks, smoke/E2E, dependency management).

---

## 1. Fix failing checks (pull in immediately)

### 1.1 Backend Lint — `backend/app/config.py:85`

Current state on `origin/main` (`git show origin/main:backend/app/config.py | sed -n '80,92p'`):

```python
    # Batch processing
    OSRM_BATCH_SIZE: int = 100  # Max locations per OSRM request
    ORS_BATCH_SIZE: int = 50

# Dispatch / stop lifecycle            <-- column 1, must be indented 4 spaces
    NOTIFY_DELAY_THRESHOLD_MIN: float = 15.0
```

This comment sits inside `class Settings(BaseSettings)` but is at column 1, so
`ruff format --check .` reports `1 file would be reformatted` and exits 1.

**Fix**
1. `backend/app/config.py:85` → indent `# Dispatch / stop lifecycle` by 4 spaces.
2. Verify: `cd backend && .venv/bin/ruff format --check . && .venv/bin/ruff check .`

**Reproducibility follow-up (do together)**
- `requirements.txt` uses `ruff>=0.7.0` while `.pre-commit-config.yaml` pins
  `v0.16.0`. CI installs "latest" → non-deterministic format/lint verdicts.
  Pin to match pre-commit: `ruff==0.16.0`. (See §2.2 for the full pin.)

### 1.2 Frontend Lint / Tests / Build — `actions/setup-node@v4` cache path

All three frontend jobs fail inside `setup-node`, before npm runs:

```
##[error]Dependencies lock file is not found in .../vrp-logistics.
  Supported file patterns: package-lock.json,npm-shrinkwrap.json,yarn.lock
```

`cache: npm` resolves `cache-dependency-path` against the repo **root** by default;
the only lockfile is `frontend/package-lock.json`. Every `setup-node` step needs the
path pinned. Apply to the 3 `frontend-*` jobs in `.github/workflows/ci.yml`:

```yaml
- uses: actions/setup-node@v5
  with:
    node-version: ${{ env.NODE_VERSION }}
    cache: npm
    cache-dependency-path: frontend/package-lock.json
```

Notes
- **Node version**: GH runners now default to Node 24 and **deprecate Node 20**
  (run annotation). Bump `NODE_VERSION` to `22` (LTS) — lockfile `lockfileVersion: 3`
  is compatible with npm 10.x bundled with 22/24. Verified locally: with a clean
  `npm ci` (npm 9/node 22) the whole frontend surface is green — `format:check` ✓,
  `eslint` 0 errors / 176 warnings, 51/51 vitest, `vite build` ✓ (only a chunk-size
  warning, non-blocking).
- Also upgrade `actions/setup-node@v4` → `@v5` and `actions/checkout@v4` → `@v5`
  in `ci.yml` and `deploy.yml` to stop the Node-20-forced action warnings.

### 1.3 Deploy — GHCR `permission_denied: read_package`

`docker/build-push-action@v6` push fails:

```
failed to push ghcr.io/siva-balan-v/vrp-backend:3db5d445:
  denied: permission_denied: read_package
```

The workflow logs in with `${{ github.actor }}` + `secrets.GITHUB_TOKEN`
(`docker/login-action@v3`). A **repo** `GITHUB_TOKEN` can read/write packages scoped
to repos, but the target here is a **user account namespace** (`siva-balan-v`),
where the token holds read-only package access → `read_package` denial.

**Fix (choose one, in order of robustness)**
1. **(Recommended) Dedicated PAT with `write:packages`:**
   - Create a classic PAT (or fine-grained token) scoped to `write:packages`
     (and `read:packages`, `repo`) on the `siva-balan-v` account.
   - Add as repository secret `GHCR_TOKEN`.
   - In `deploy.yml` use `username: ${{ github.actor }}` /
     `password: ${{ secrets.GHCR_TOKEN }}`.
2. **Create/link the packages first**: push a first package under the repo context
   (e.g. `ghcr.io/siva-balan-v/vrp-backend`) interactively once so GHCR links it to
   the repo, then verify the workflow token can push.
3. **Move images to an org namespace** (`ghcr.io/<org>/vrp-*`) where
   `GITHUB_TOKEN` write works out of the box.

**Also required for the blue-green stage** — these secrets must exist or the deploy
job errors at the `appleboy/ssh-action` step:
`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_PATH`,
`REDIS_PASSWORD`, `POSTGRES_PASSWORD`.

### 1.4 Backend Tests — no fix needed

Passed on `main` (`✓ Backend Tests in 2m40s`). Make it deterministic per §2.2
(env-sanitized invocation, reproducible deps). Note: `tests/test_config.py`
only fails when the shell already exports DB/Redis/router env-vars; CI env is clean,
so it is stable there.

---

## 2. CI hardening (reproducibility & hygiene)

### 2.1 Workflow-level settings (both workflows)

```yaml
permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
```

Triggers: add `workflow_dispatch:` so pipelines are re-runnable without a push;
keep `push: [main]` + `pull_request: [main]`.

### 2.2 Pin dependencies (backend)

`requirements.txt` is 100% `>=` (except `bcrypt==4.0.1`) → latest-venom drift breaks
CI intermittently (ruff is the observed case). Options (choose 1):

- **Minimal**: pin the lint/test-critical trio now —
  `ruff==0.16.0`, `pytest==8.4.*`, `pytest-asyncio==0.26.*`, `pytest-cov==6.*`.
- **Full lock** (preferred for deterministic CI): generate a compiled lock
  (`pip-compile requirements.in -o requirements.txt`) and have CI install from a
  `requirements-lock.txt` that pins every transitive dep. Keep `requirements.in`
  as the intent file.

Align `[tool.ruff]` in `backend/pyproject.toml` with the pinned ruff; remove the
unused `black` dependency (CI only uses ruff — pre-commit uses ruff too).

### 2.3 Frontend scripts

Add deterministic scripts (used by CI and pre-commit):
- `frontend/package.json`:
  - `"test:ci": "vitest run --coverage"`
  - `"lint": "eslint src/"` (unchanged), add `--max-warnings` gate as a *separate*
    script `"lint:strict": "eslint src/ --max-warnings 0"` so the 176 pre-existing
    warnings can be burned down without blocking merges.
- Add `@vitest/coverage-v8` devDependency + coverage thresholds in `vite.config.js`
  (`test.coverage`): `branch/function/lines/statements` thresholds, and
  `exclude: ['src/__tests__/**', 'src/main.jsx', 'src/utils/*', '**/*.test.*']`.

---

## 3. Missing pipelines to implement

| Pipeline | File | Purpose |
|----------|------|---------|
| A. Backend coverage gate | extend `ci.yml` backend-test | `pytest --cov=app --cov-report=term-missing --cov-fail-under=<baseline>` + upload `coverage.xml` artifact |
| B. Frontend coverage gate | extend `ci.yml` frontend-test | `npm run test:ci` → vitest coverage thresholds + artifact |
| C. Dependency scan | new `security.yml` | `pip-audit -r requirements.txt` (or lock) + `npm audit --omit=dev --audit-level=high` |
| D. Trivy image scan | extend `docker-build` job | `trivy image --exit-code 1 --severity HIGH,CRITICAL` on built images (or `aquasecurity/trivy-action`) |
| E. Secret scan | new `security.yml` or pre-commit CI | `gitleaks detect` / `trufflehog` on every push+PR |
| F. DB migration check | new `db-migrations.yml` | service container `postgres:16`; run `alembic upgrade head` against it; assert `alembic heads`/`current` equal; keeps `test_database.py::test_run_migrations` as unit-level equivalent |
| G. Compose smoke / E2E | new `e2e.yml` | `docker compose -f docker-compose.yml ... up -d`, wait for `/health`, post a 2-stop `optimize-routes` request, assert 200 + stops; teardown. Gated behind build job |
| H. Dependabot | `.github/dependabot.yml` | schedules for `github-actions`, `npm` (frontend), `pip` (backend), weekly; group non-breaking bumps |
| I. Deploy gating | `deploy.yml` | deploy `build-push` job `needs: [backend-lint, backend-test, frontend-lint, frontend-test, frontend-build, docker-build]` so broken `main` never publishes images |
| J. PR scaffold | `.github/pull_request_template.md`, `CODEOWNERS` | standard PR body, reviewer routing |
| K. Status-check parity | settings | enforce required checks + `CODEOWNERS` review + `main` protection (see §5) |

### 3.1 Test methodology (recorded for the repo)

Adopt and document in `CONTRIBUTING.md` / `docs/CONFIGURATION.md`:

1. **CI-equivalent local command** (backend, no infra needed):
   ```bash
   cd backend && env -i PATH="$PATH" HOME="$HOME" .venv/bin/python -m pytest -q \
     --cov=app --cov-report=term-missing
   ```
   This matches the CI runner's clean environment. Do **not** use `env VAR=` empty
   assignments: pydantic-settings treats an *empty* `DATABASE_URL`/`REDIS_URL` as set,
   which makes `test_settings_defaults` fail locally while passing on CI.
2. **Frontend local**: `cd frontend && npm ci && npm run format:check && npm run lint && npm test && npm run build`.
3. **Three tiers**: unit (pytest / vitest), integration (FastAPI `TestClient` +
   mocked routers — already the pattern in `test_api.py`), infrastructure
   (migration run + compose smoke in §3-F/G).
4. **Accessibility**: keep `jest-axe` smoke tests and tab-keyboard tests
   (`a11y.test.jsx`, `ResultsPanel.test.jsx`) in the frontend gate.
5. **Coverage policy**: thresholds start at the measured baseline, then *ratchet up*
   (never down) each PR; CI fails below the floor.
6. **Deterministic deps**: installs come from locks (§2.2); security pins via
   dependabot + audit (pip-audit / npm audit).

---

## 4. Recommended execution order

| Step | Change | Verify |
|------|--------|--------|
| 1 | Branch `fix/ci-green` off `main` | — |
| 2 | §1.1 config.py indent + `ruff==0.16.0` pin | `ruff format --check .` + `ruff check .` |
| 3 | §1.2 setup-node cache-dependency-path + Node 22 + action bumps | `npm ci && npm run build && npm test && npm run lint` (already green locally) |
| 4 | §1.3 deploy GHCR token (needs secret `GHCR_TOKEN`) | re-run Deploy via `workflow_dispatch` |
| 5 | Push `fix/ci-green`, open PR → all 6 CI checks green on PR | GitHub statuses |
| 6 | Merge, then §2/§3 pipelines on `feat/ci-pipelines` branch | new workflow runs |
| 7 | Add dependabot + PR template + branch-protection rules | UI verification |
| 8 | Burn down the 176 eslint warnings via `lint:strict` over subsequent PRs | `lint:strict` exit 0 |

**Out of scope / notes**
- `Jenkinsfile` exists (legacy). Recommend deprecating it in favor of these GH
  Action pipelines once parity is reached (flag for the user — do not delete yet).
- No Docker daemon / kubernetes locally → §3-F/§3-G run only on CI until a local
  docker host is available.
- `main` is protected to require the CI checks (§3-K) — this is what makes the
  red statuses block merges.

## 5. Open questions for the user

1. **GHCR**: OK to create a classic/fine-grained PAT with `write:packages` and add
   it as `GHCR_TOKEN` secret? (Alternatively pre-create the two packages manually.)
2. **Coverage thresholds**: accept "measure now, set baseline, ratchet up" policy?
3. **Node version**: `22` (LTS) acceptable for CI?
4. **Deploy blue-green secrets**: are `DEPLOY_HOST/_USER/_SSH_KEY/_PATH` +
   `REDIS_PASSWORD`/`POSTGRES_PASSWORD` available? If not, keep the deploy job but
   make the SSH step `continue-on-error` until secrets land.
5. **Jenkinsfile**: keep as-is (legacy) or retire in this effort?
