# Production readiness — Shewiun CFA

## Current product implementation
- The task composer uses the built-in Local Planner when no model key is configured. It is a deterministic, rules-based helper, not an LLM. Model-backed generation remains optional.
- The workspace supports creating named agents with roles, icons and optional instructions; custom agents are stored in the configured database.
- CFA Brain now has Graph and Entries views. Explicit note links are shown as graph edges, and agent runs can be saved as decisions for later retrieval. This is curated memory, not autonomous model self-modification.
- Product positioning, design direction, pricing hypotheses, validation interviews and go-to-market steps are in [PRODUCT_AND_GO_TO_MARKET.md](PRODUCT_AND_GO_TO_MARKET.md).

## Current release gate

The application intentionally reports `production_ready: false`. Do not use the current SQLite/in-process runtime for confidential data or reliability-critical workflows.

### Required before a real production release

1. **Persistent database and durable jobs**
   - Configure a dedicated PostgreSQL database with `DATABASE_URL` or `CFA_DATABASE_URL`, apply `migrations/001_postgres_schema.sql`, and verify that all workspace/review records are being written to PostgreSQL. The adapter and initial schema migration are now in the branch, but no live database connection has been configured or integration-tested.
   - Move the runtime worker from an in-process task loop to a durable queue/worker with idempotent jobs, retries, leases, cancellation, and recovery.
   - Configure backups and restore testing. A daily Vercel retention endpoint is wired to delete review-related data after 90 days; set CRON_SECRET and verify the scheduled job after deployment.
   - The app can use `DATABASE_URL` or `CFA_DATABASE_URL` through the PostgreSQL adapter. A connection string alone is not enough: provision a dedicated database, apply/verify the schema, and test backups and concurrent runtime operations.
2. **Identity and authorization**
   - Current branch adds a fail-closed shared-password gate for workspace APIs when deployed to Vercel. This is a temporary single-workspace safeguard, not enterprise identity.
   - For production, integrate an identity provider with individual accounts, MFA, organization membership, role-based access control, session revocation, audit trails, and tenant-scoped database access.
   - Until the shared-password gate is configured, Vercel-hosted workspace API routes return 503 rather than allowing anonymous access.
3. **Secrets**
   - In Vercel Project Settings → Environment Variables, set `CFA_ACCESS_PASSWORD` (at least 16 characters) and `CFA_SESSION_SECRET` (at least 32 random characters). Use encrypted/sensitive values, production scope, and redeploy.
   - To enable model-backed Council/review calls, set `GEMINI_API_KEY` as a server-side encrypted environment variable. The model is not enabled by source code alone.
   - Email unlock and Authorization Test intake on Vercel require a durable PostgreSQL database and `CFA_PRIVACY_NOTICE_URL` pointing to a public HTTPS privacy notice. Set `CRON_SECRET` for the daily retention job.
   - Never commit or place any of these values in browser code, tickets, or source control.
4. **Abuse protection**
   - When PostgreSQL is configured, request limits use an atomic shared-table upsert; SQLite fallback limits are process-local and can reset or diverge across serverless instances. Add per-account quotas, model spend budgets, and alerting.
5. **Operational assurance**
   - Add error reporting, traces, structured redacted logs, uptime/latency alerts, backup restore tests, dependency and secret scanning, and a documented incident/rollback procedure.
   - Run the end-to-end and model-evaluation suites against a preview deployment before promotion.

## What this branch implements

- A signed, eight-hour, HttpOnly, SameSite=Strict session cookie for the shared-password gate.
- Constant-time password/signature comparisons, CSRF origin checking for authenticated state-changing workspace API requests, request body length caps, baseline browser security headers, and process-local request limits.
- A frontend sign-in/setup gate; workspace data APIs fail closed on Vercel when auth secrets are absent.
- PostgreSQL connection pooling, initial schema migration, shared-database rate limits, consent-based memo unlock, Authorization Test request intake, protected analytics/request endpoints, browser Print/Save as PDF, and 90-day retention cleanup.
- A health/readiness response that lists known blockers instead of claiming production readiness.
- A fixed eight-case deterministic Agent Launch Review evaluation suite. Critical deterministic findings remain authoritative over any model recommendation.

## Limits and product claims

- Agent Launch Review is a user-answer-based self-assessment. It is not a penetration test, security audit, certification, or proof of safety.
- A configured model key proves only that configuration is present; it does not guarantee provider availability or free-tier quota.
- The default persistence backend remains SQLite. On Vercel it uses ephemeral `/tmp` storage. PostgreSQL is selected only when `DATABASE_URL` or `CFA_DATABASE_URL` is configured and reachable.
- The runtime job worker is still in-process and is not durable. Rate limits are shared across instances only when PostgreSQL is configured; otherwise they are process-local.
- The shared-password gate is not a substitute for SSO, MFA, organization/tenant authorization, or per-user audit attribution.

## Release checklist

- [ ] Dedicated PostgreSQL database provisioned; migration applied; live integration, concurrency, and backup/restore tests passed.
- [ ] Durable queue/worker implemented and tested under retries, timeouts, and concurrent execution.
- [ ] Individual identity, MFA/SSO, roles, tenant isolation, and session revocation implemented.
- [ ] Distributed rate limits and provider budget caps configured.
- [ ] `CFA_ACCESS_PASSWORD`, `CFA_SESSION_SECRET`, `DATABASE_URL`, `GEMINI_API_KEY`, `CFA_PRIVACY_NOTICE_URL`, and `CRON_SECRET` configured as Vercel secrets/values where applicable.
- [ ] Preview deploy passes API, browser, auth, security-header, data-isolation, and eight-case rule-evaluation checks.
- [ ] Backup/restore and deletion/retention workflows verified.
- [ ] Production deployment promoted only after checks pass.
