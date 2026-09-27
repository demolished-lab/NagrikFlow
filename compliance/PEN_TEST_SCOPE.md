# Penetration Test — Scope & Rules of Engagement

**Target:** Civic Pathfinder production deployment (API, admin console, auth
flows, frontend on Cloudflare Pages)
**Version/tag under test:** [TAG]
**Window:** [DATE 22:00 IST] → [DATE+3 06:00 IST]
**Report due:** +5 business days

## In scope

1. **Web app:** API endpoints under `/auth/*`, `/me/*`, `/admin/*`, `/task/*`,
   `/roadmap/*`, `/grievance`, webhook endpoints (`/telegram/webhook`).
2. **Auth & session:** OTP request/verify, lockout + rate-limit behaviour
   (`/admin/security` metrics), JWT/session fixation, password reset paths,
   role escalation (user → admin), consent bypass attempts.
3. **Input abuse:** SSRF on every URL-accepting path (step links, admin
   fetch/probe, deep-link probe) incl. DNS-rebinding and redirect-bypass
   attempts; injection (SQL via ORM-bypass attempts, XSS in map content,
   command injection in backup/Telegram paths); file/path traversal on
   backup & archive endpoints.
4. **Transport/config:** TLS, HSTS, CORS origin reflection, cookie flags,
   security headers, `.env`/backup exposure, directory listing.
5. **Infrastructure:** host OS, reverse proxy, Postgres/Redis exposure,
   Docker/compose configuration, GitHub Actions secrets handling.
6. **Rate limiting & DoS:** moderate volumetric testing against
   `api.domain` (≤ 200 rps), credential-stuffing simulation.

## Out of scope

- Social engineering of staff/users; physical attacks.
- DoS against Cloudflare Pages, the DB beyond agreed limits, or third parties.
- Post-exploitation persistence, lateral movement into unrelated systems.
- Automated scanner-only findings without a proof-of-concept.
- The `/admin/build`, `probe`, and `fetch` paths **firing real requests to
  external government domains** — use the sandbox allowlist host instead.

## Rules

- Data: create test accounts (`pen_*`); do not access real user data. If
  access occurs, stop and notify `security@[domain]` immediately.
- Evidence: screenshots/HTTP transcripts per finding; severity per CVSS v3.1.
- Outage windows coordinated via `[CONTACT]`; production data is not to be
  copied out of the environment.
- Findings → tracker within 24 h of report; criticals remediated ≤ 7 days,
  highs ≤ 30, mediums ≤ 90; retest of criticals included.

## Prerequisites (testable surface)

- Test deployment with seeded demo maps (`backend/sim`), test admin account
  in `ADMIN_EMAILS`, seeded rate-limit counters observable via
  `/admin/security` + `/metrics`.
- Current automated baseline: `pytest` suite (99 tests) green in CI — the
  report should reference regressions against it.

## Deliverable checklist

- [ ] Executive summary + severity histogram
- [ ] Per-finding: description, PoC request/response, impact, remediation
- [ ] Attack narrative (chains, not just isolated bugs)
- [ ] Retest attestation for criticals
