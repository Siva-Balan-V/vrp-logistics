# Contributing to VRP Logistics

Thanks for taking the time to contribute. This document covers the toolchain,
branching conventions, and commands you need to keep CI green.

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.11+ | The project targets 3.14; 3.11 is the minimum supported in CI |
| Node.js | 20+ | Needed for the Vite frontend |
| PostgreSQL | 15+ | Or use the Docker Compose service (`vrp-postgres` on 5433) |
| Redis | 7+ | Or use the Docker Compose service (`vrp-redis` on 6379) |
| pre-commit | 3.x | Optional locally, enforced in CI |

Install the Python frontend tooling inside `backend/`:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install frontend tooling:

```bash
cd frontend
npm install
```

---

## Branch naming

Use the `feat/`, `fix/`, `docs/`, or `test/` prefixes with a short kebab-case
description:

```
feat/live-dispatch
fix/cors-wildcard
docs/add-changelog
test/add-replan-suite
```

---

## Pre-commit hooks

The repository ships with a `.pre-commit-config.yaml` that runs on every
commit. Install the hooks once after cloning:

```bash
pre-commit install
```

What the hooks run:

| Hook | Scope |
|------|-------|
| `trailing-whitespace` | all files |
| `end-of-file-fixer` | all files |
| `check-yaml` / `check-toml` / `check-json` | config files |
| `detect-private-key` | all files |
| `ruff --fix` | `backend/app/`, `backend/tests/` |
| `ruff-format` | same |
| `prettier` | `src/**/*.{js,jsx,css,json}` in `frontend/` |
| `eslint` | `frontend/src/` |

If a hook reformats a file mid-commit, re-`git add` the file and re-commit.

---

## Commands to run before pushing

### Backend (run from `backend/`)

**Important:** the full test suite and the integration tests require a running
Postgres and Redis. For a fast offline run that does not need a database, prefix
commands with the following environment overrides (this is what CI does):

```bash
DATABASE_URL= REDIS_URL= ROUTING_BACKEND=haversine .venv/bin/python -m pytest
```

Lint and format:

```bash
cd backend
ruff check .
ruff format --check .
```

Run the full test suite:

```bash
cd backend
DATABASE_URL= REDIS_URL= ROUTING_BACKEND=haversine .venv/bin/python -m pytest -v
```

### Frontend (run from `frontend/`)

```bash
cd frontend
npx vitest run
npx eslint src/
npx prettier --check "src/**/*.{js,jsx,css,json}"
```

The frontend linter runs at warn-only level on the repo (no `prop-types` or
unused-variable errors will fail CI). ESLint is configured in
`frontend/eslint.config.js`.

---

## Working on a feature

1. Create a branch from `main` (or `develop` if active):
   ```bash
   git checkout main && git pull
   git checkout -b feat/your-feature-name
   ```
2. Make your changes following the existing code style (see `ARCHITECTURE.md`
   for backend layout and component patterns).
3. Add or update tests in the relevant test files.
4. Run the appropriate lint and test commands above.
5. Commit with a descriptive prefix (`feat(scope):`, `fix(scope):`,
   `test(scope):`, `docs:`) and a short summary.
6. Open a PR against `main`. CI will run the same lint and test commands.

---

## Commit conventions

Each commit should be a single logical change. Use the conventional-prefix
format:

```
feat(scope): add feature description
fix(scope): describe the fix
test(scope): describe what is tested
docs(scope): describe the change
chore(scope): maintenance work
```

---

## Useful docs

| File | What it covers |
|------|----------------|
| `docs/ARCHITECTURE.md` | Backend structure, ORM models, service patterns |
| `docs/BUSINESS_ROADMAP.md` | Full feature backlog with 57 prioritized items |
| `docs/INFRASTRUCTURE_SETUP.md` | Local development and full infrastructure setup |
| `docs/PRODUCTION_DEPLOYMENT.md` | Blue-green deploy, Jenkins CI/CD, monitoring |
| `docs/CONFIGURATION.md` | All environment variables and their defaults |
| `SECURITY.md` | Security policy and responsible-disclosure guidance |
| `PRIVACY.md` | Data-handling and privacy commitments |
