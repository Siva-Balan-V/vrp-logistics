# Privacy Policy

This document describes what data the RouteForge platform collects, how it is
used, and the rights users have over their data.

## Data collected

| Category | Data | Purpose | Retention |
|----------|------|---------|-----------|
| Account | Email, password hash, role | Authentication & authorization | Until account deletion |
| Organization | Company name, plan | Multi-tenancy & billing | Until company deletion |
| Jobs | Optimization inputs, routes, results | Core service function | Until deleted by user |
| API keys | Key hash, name, permissions | B2B integration access | Until revoked |
| Usage | Optimization counts | Plan limit enforcement | Monthly reset |

## How data is used

- To provide and operate the optimization service
- To enforce subscription plan limits
- To send operational notifications (SMS/email) only when configured by you
- To improve reliability (logs may include request metadata, not payloads)

## Data storage

- PostgreSQL: durable user, company, job, and key data
- Redis: ephemeral distance-matrix cache; rebuilt automatically, not a source of truth
- Backups (see `docs/DISASTER_RECOVERY.md`) may retain copies of Postgres data
  until the configured retention period expires

## Data sharing

We do **not** sell or share personal data with third parties except:

- Payment processing providers (e.g., Stripe) for subscription billing
- Notification providers (Twilio/SendGrid) when you enable them
- As required by law

## Your rights

You may, at any time:

- **Export** your data — request a copy of your account, company, and job data
- **Correct** your account details
- **Delete** your account — removes your user record; jobs may be retained per
  company retention policy unless requested otherwise
- **Revoke** API keys at any time from the API keys page

To exercise these rights, contact the administrator of your RouteForge instance.

## Data deletion

- Deleting an account removes the user record.
- Deleting a company removes company-scoped jobs, API keys, and notification
  configuration.
- Backups containing deleted data expire per the backup retention schedule.

## Security

See `SECURITY.md` for the technical security model. Access to production data
is restricted to authorized administrators.

## Changes to this policy

Updates will be reflected here with the date below.

*Last updated: August 2026*
