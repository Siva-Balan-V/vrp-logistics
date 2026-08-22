# Security Policy

## Supported versions

| Version | Status |
|---------|--------|
| develop | In development, security fixes on merge |

## Reporting a vulnerability

Do **not** open a public issue. Report vulnerabilities privately to the
maintainers by email (replace with the project maintainer address). Please
include:

- A description of the vulnerability and the affected endpoint/component
- Steps to reproduce (minimal example)
- Impact and any suggested remediation

You will receive an acknowledgment within 3 business days and a status update
every week until the issue is resolved.

## Security model

### Authentication

- JWT access tokens (short-lived, default 30 min) via `Authorization: Bearer`.
- Refresh tokens (default 7 days) via `POST /api/v1/auth/refresh`.
- API keys for B2B integration via `X-API-Key` header, stored as SHA-256 hashes
  with per-key permissions and expiry.
- Passwords hashed with bcrypt (`passlib`/`bcrypt 4.0.1`).

### Authorization / tenancy

- Every query is scoped by `company_id`. JWT users are bound to a company;
  API keys carry a company scope. Cross-tenant reads are prevented at the
  query layer.
- `require_admin` / `require_permission` dependencies gate privileged routes.

### Transport & secrets

- Production deployment expects TLS terminated at the reverse proxy (nginx).
- Secrets (JWT key, Stripe keys, Twilio, SMTP) come from environment variables;
  never commit them.
- Redis supports `requirepass`; set `REDIS_PASSWORD`.

### Abuse protection

- Rate limiting on the expensive `POST /api/v1/optimize-routes` endpoint and
  auth endpoints.
- Optimize usage quota enforced per company/plan (see `app/services/plans.py`).
- CORS restricted to configured `ALLOWED_ORIGINS`.
- Request body size limits are expected at the reverse proxy.

### Data validation

- Pydantic schemas validate all request bodies.
- OSRM/ORS response structures are validated before indexing.
- Internal exceptions are logged, not leaked to clients (generic 500s).

## Hardening checklist

- [ ] Set strong `JWT_SECRET_KEY`, `REDIS_PASSWORD`, `POSTGRES_PASSWORD`
- [ ] Enable HTTPS + HSTS at the proxy
- [ ] Restrict `ALLOWED_ORIGINS` to your frontend domains
- [ ] Configure nginx security headers (CSP, X-Frame-Options, etc.)
- [ ] Set Stripe webhook signature verification
- [ ] Run the OWASP Top 10 review before production launch
- [ ] Enable PostgreSQL backups and test restore (see `docs/DISASTER_RECOVERY.md`)

## Known security notes

- Metrics endpoint `/metrics` is unauthenticated; keep it internal-only in
  production (do not expose publicly).
- Debug mode (`DEBUG=true`) is for development only and must stay off in prod.
