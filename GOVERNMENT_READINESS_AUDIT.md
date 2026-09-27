# Government Readiness Audit — Civic Path Navigator

**Date:** 2026-09-27 · **Basis:** external re-audit at commit `8e57023` plus
this repo's own verification runs · **Status: NOT ready to register with API
Setu.** Code-side controls are in place and tested; the remaining blockers are
external actions and one deliberate scope item. This document replaces the
previous file, which contained a script fragment and an unsupported
`ready_to_register` claim.

## 1. Evidence (what was actually verified)

| Check | Result | How |
| --- | --- | --- |
| Backend test suite | **99/99 pass** (SQLite) and full suite green on **PostgreSQL 16** in CI | `python -m pytest backend/tests -q`; CI jobs `backend`, `backend-pg` |
| Simulation runbooks | 8/8 scenario sims, 20/20 personas | `backend/sim/run_sim.py`, `backend/sim/run_personas.py` |
| Frontend | `tsc --noEmit` clean, Vite production build clean, Playwright e2e 8/8 | CI job `frontend` |
| Container | Image builds; `/healthz` + `/readyz` smoke pass | CI job `image` |
| Python deps | `pip-audit` clean except documented `PYSEC-2026-3740` (nltk via crawl4ai, no fix upstream) | CI job `deps` |
| npm deps | **0 vulnerabilities** (`vite@8`, `@vitejs/plugin-react@5`), and CI now fails on `npm audit --audit-level=moderate` | local `npm audit`, CI job `frontend` |
| Live build flow | Real citizen task returned **200** with `.gov.in` sources and a generated path | external audit, verified live |

## 2. Controls implemented (code-side)

**Security & abuse**
- OTP: per-account lockout (423 while locked, 5 fails → 15 min lock), every
  request retires prior unused codes (`app/main.py`).
- Rate limiting: Redis store with fail-open memory fallback,
  `RATE_LIMIT_FAIL_CLOSED=1` option (`app/security.py`, `app/security_redis.py`).
- SSRF: every fetch tier entry-guards public targets, redirect chains are
  followed through a validating handler (`guard_chain` in `app/worker.py`),
  `SSRF_PROBE=0` dev-only opt-out.
- Build quotas: `JOB_MAX_ACTIVE_PER_USER` (default 3) → HTTP 429; field length
  caps on `BuildTaskIn` (500/100/100/100 chars).
- Telegram webhook secret **fail-closed** outside dev/test
  (`app/telegram_validate.py`); bot token never committed.

**Data protection (DPDP)**
- Right to erasure: `DELETE /me/account` purges vault, consents, progress,
  milestones, notifications, grievances, OTPs, link codes, OAuth states, jobs;
  the user's **draft maps are deleted**, verified maps are kept as public
  guidance with **attribution stripped** (`created_by=0`).
- Dedup integrity: unique indexes on `progress(user_id, map_slug, step_id)`,
  `notification(user_id, reference)`, `taskmap(slug)` — endpoints tolerate
  concurrent duplicates instead of 500ing.
- Consent tracking, grievance endpoint (`/me/grievance`), retention meta on
  vault items; privacy policy + terms templates present.

**Job durability**
- Atomic **lease/claim** (`job.worker_id`, `job.lease_until`): exactly one
  worker transitions a job to running — single UPDATE, safe on SQLite and
  PostgreSQL.
- **Poller thread** (`JOB_POLLER`, on by default, off in tests) dispatches
  queued rows and revives expired leases across worker processes; startup
  `recover_orphans` refuses to steal live leases and fails rows older than
  24 h; stale running rows fail on status reads (`JOB_STALE_SECONDS`).
- Per-slug in-process locks + DB unique slug index + insert-race fallback.

**Content accuracy**
- Source discovery chain: enriched search → bare search → curated
  **catalog fallback also after URL filtering** (a search that returns only
  non-government results no longer 400s).
- Policy gate: `.gov.in`/`.nic.in` HTTPS only, HTTP→HTTPS upgrade.
- Link selection: bad-link suppressor (grievance/FAQ/champions…), same-host
  scoring, cross-host requires path evidence; `LINK_HINTS` covers
  registration/register.
- Extraction: paperless pages never fabricate a "gather documents" step; a
  document token needs a requirement verb within 60 chars; fees only quoted
  when the page states them (else `₹0` for explicit "free", else a pointer to
  the official schedule); the apply step falls back to the fetched official
  source rather than an empty CTA.
- Provenance: `admin_verify` gate checks graph integrity (parse, ≥1 node, no
  dangling edges, acyclic) + provenance (`source_urls`, `content_hash`,
  `checked_at` ≤ 45 d, `VERIFY_MAX_AGE_DAYS`).

**Operability**
- `/healthz` (liveness) `/readyz` (DB + migrations) `/metrics`, structured
  logs; online backups with `validate`/`restore` CLI
  (`app/backup.py run|list|restore`), `postgresql-client` in the image,
  `python -m app.migrate_pg` for PostgreSQL migrations.
- Five CI jobs: sqlite tests, PostgreSQL tests, image smoke, frontend
  build+e2e, dependency audit.

## 3. Remaining gaps (why this is not "ready to register")

| Gap | Type | Needed |
| --- | --- | --- |
| API Setu organization registration | **external** | Register at partners.apisetu.gov.in, obtain org id |
| DigiLocker production credentials | **external** | Apply via API Setu; placeholder credentials in repo are dev-only |
| Telegram webhook secret in production | **config** | Set `TELEGRAM_WEBHOOK_SECRET` (webhooks 401 until then — fail-closed by design) |
| Public deployment with TLS | **ops** | CI image job is a smoke test only; needs a real host + reverse proxy + Postgres |
| Full WCAG 2.1 AA audit | **scope** | Skip-links/aria-live/Hindi toggle exist; contrast + full audit pass outstanding |
| Legal review of TOS/privacy policy | **external** | Documents are generated templates, not counsel-reviewed |
| Multi-worker queue | **mitigated** | Lease/claim + poller make it exactly-once; a dedicated queue (Celery/Redis) is the long-term swap |

## 4. How to re-verify

```
python -m pytest backend/tests -q          # 99+
python backend/sim/run_sim.py              # 8/8
python backend/sim/run_personas.py         # 20/20
npm run build --prefix frontend            # tsc + vite
npm audit --prefix frontend                # 0 vulns
```

CI on `main` must be green: `backend`, `backend-pg`, `image`, `frontend`,
`deps`.
