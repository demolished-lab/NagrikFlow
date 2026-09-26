# Production path — derived 2026-09-26 from full re-sweep

Sources: internet sweep (YouTube/Bilibili/V2EX/Jina via agent-reach;
Reddit+Twitter login-gated = honest gap), 28-row repo re-audit (zero drift),
machine introspection (Ryzen 5700U/15.3 GB/iGPU-only, E: healthy, C: 100.7 GB).

## Core derivation (what the internet taught us)

1. **Consent rails first, scraping last.** India Stack architects (DEPA model)
   and practitioners agree: DigiLocker/API Setu consent APIs are the sanctioned
   path; scraping is swimming upstream. Our architecture already does this —
   keep the cascade strictly as a *fallback*, never the story.
2. **Anti-bot doctrine: reduce triggers, don't buy solves.** Fingerprint
   *consistency* (OS↔UA, tz↔geo-IP), residential rotation, session hygiene.
   Per-solve CAPTCHA buying is a cost leak. Our tier escalation matches this.
3. **Legal caution is real.** Watch scraping-law primers before pointing the
   cascade at any .gov.in target; prefer API Setu publisher approval.
4. **Differentiator confirmed.** Bilibili shows policy-text scraping is the top
   gov-scrape use case, and *nobody* is doing government-RAG roadmaps — that
   gap is our hackathon thesis.
5. **Machine verdict.** This laptop = excellent dev host (Ollama small models,
   all tooling), unfit as public host (iGPU-only, residential IP, sleeps).
   Public face stays Cloudflare Pages + Tunnel, exactly per DEPLOY.md.

## Minimal-effort production list (in order)

### P0 — hours, ₹0
- [ ] Pin versions (`fastapi==0.141.1`, node engines) before freeze.
- [ ] Delete `qwen3.5:latest` (6.6 GB, OOMs) → keep minicpm5; reclaims RAM headroom.
- [ ] Manually read (browser) the 3 API Setu PDFs CloudFront blocks from fetchers:
  Requester Spec v1.12, Meri Pehchaan v2.4 (newest SSO path), Partner Onboarding
  SOP + June-2025 Requester ToU (must-sign).
- [ ] Read `apisetu.gov.in/developer` (agent flagged, unread).
- [ ] Register API Setu org NOW (approval clock takes days; everything else waits on it).

### P1 — half-days, ₹0
- [ ] SQLite hardening instead of Postgres: WAL mode + nightly backup to E: +
  documented restore. Postgres only when multi-user concurrency demands it.
- [ ] DPDP kit: grievance-contact page, retention/erasure job
  (`DELETE vault WHERE consent withdrawn`), breach runbook, consent-receipt export.
- [ ] Observability: GlitchTip self-host (or Sentry free) + UptimeRobot monitors.
- [ ] Job timeouts/retries on build + recheck (single hang must not wedge the queue).

### P2 — only when users arrive
- [ ] Redis/Celery, Neon/Supabase Postgres, Resend/SMTP keys, Telegram token,
  DigiLocker production flip — all interfaces already exist; these are config.
- [ ] Hindi Roadmap/Admin chrome (App+Dashboard done), full WCAG audit.

## Explicit DO-NOT list (from license + platform research)
- Never vendor AGPL code (wigolo, Recordly, macro, MiroFish) — process boundary only.
- Never vendor cloakbrowser binary — pin, isolate, keep distributable clean.
- Never present scrape fallback as primary; never auto-submit gov forms.
- Never run public traffic from this laptop; never store raw doc blobs without consent.
- hermes gateway is absent — our `app/hermes.py` worker IS the Telegram path. No migration needed.

## Coverage gaps admitted
Reddit/Twitter sentiment sweep not done (login-gated backends); Exa search
unconfigured (Jina used instead); Bynara model count not rechecked (key untouched
by policy); spec-PDF contents unverified (CloudFront-403 to machines).
