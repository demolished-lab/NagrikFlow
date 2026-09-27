# Pending things — Civic Path Navigator

Ordered by unblock-value. Checked items are done; unchecked need you or a key.

## Credentials (only you can provide these)
- [ ] **DigiLocker Requester `client_id` + `client_secret`** — register at
  `partners.apisetu.gov.in` (Consumer APIs → Requester config, scopes
  `userdetails,files.issueddocs`). Sandbox works without it; live identity
  import needs it. Then set `DIGILOCKER_ENV=production`.
- [ ] **Telegram bot token** — @BotFather → `/newbot` → `TELEGRAM_BOT_TOKEN` in
  `backend/.env`. Then expose backend via tunnel and call
  `setWebhook?url=<tunnel>/hooks/telegram`.
- [ ] (Optional) `RESEND_API_KEY` or SMTP creds for real mail (console works now).
- [ ] (Optional) Exa / Brave Search keys for richer gov-URL discovery.

## Environment / machine
- [ ] **Remount E:** — `schtasks /run /tn VyuhaMountVHD` returns 0 but no volume
  appears; needs admin `diskpart /s C:\vdisks\mount-vyuha.cmd`. Venv lives on C:
  until then (fine — 103 GB free).
- [ ] Decide `.agent-reach-venv.bak` fate: delete once `.venv-civic` has served a month.
- [ ] `qwen3.5` OOMs on 16 GB RAM — Ollama fallback pinned to `minicpm5`. If you
  want stronger local models, free RAM or wait for E: models dir.

## Product gaps (build next)
- [x] **Real browser click-through** — Playwright: register → dashboard → roadmap green (`smoke.png`).
- [x] **pytest suite (81 tests) + GitHub Actions CI** — backend + frontend build.
- [x] **page-agent Guide-me** — installed, per-step Q&A with user's own key (app key never leaves server).
- [x] **Postgres-ready** — `psycopg` driver in, URL-driven; full suite now runs
  on Postgres 16 in CI (`backend-pg` job with a real postgres service).
- [ ] **Hermes worker rebuild** — source absent; only `alerts.py` + webhook exist.
- [x] **Background jobs** — queued build/recheck + polling UI (single-process; Redis later).
- [x] **Dynamic task-to-roadmap flow** — citizens describe task → discover sources → build map async
- [x] **Hash-based routing** — /roadmap/:slug navigation
- [x] **Security audit fixes** — Telegram webhook secret validation, LLM health check, HTTPS middleware

## Production hardening (2026-09-27, round 2)
- [x] **Real Redis rate-limit backend** — `security_redis.py` `RedisStore` +
  `security.py` store abstraction; `REDIS_URL` set → shared counters across
  workers (fail-open if Redis is down); memory store unchanged otherwise.
- [x] **Observability endpoints** — `/healthz`, `/readyz` (DB + schema +
  Redis), `/metrics` (Prometheus, bounded card., optional `METRICS_TOKEN`),
  structured logs with normalized paths (`obs.norm_path`).
- [x] **Integration doctor** — `GET /admin/integrations` (booleans only),
  `?probe=1` also pings Telegram getMe.
- [x] **Backups upgraded** — `pg_dump` for Postgres (PGPASSWORD env, never
  argv) + optional S3 upload via boto3 (`BACKUP_S3_*`), non-fatal failures.
- [x] **nltk PYSEC-2026-3740 guard** — `app/nltk_guard.py` blocks path
  traversal/file-URL loads of nltk data; hooked at startup; CI `deps` job
  carries an explicit pip-audit exception (no fixed release exists).
- [x] **Postgres proof** — `backend-pg` CI job runs all 81 tests against a
  real postgres:16 service (migrations, pg_trgm, pg_dump path).
- [x] **compose/Dockerfile** — added redis service + healthchecks,
  REDIS_URL/METRICS_TOKEN/BACKUP_S3_* passthrough, api healthcheck.
- [x] **compliance/ pack** — DPO letter, breach response (6h CERT-In),
  DPDP s.4–s.17 map, pen-test scope, usability protocol.
- [x] **81 tests** (14 new in `test_prod_hardening.py`).

## Audit Fixes Applied (2026-09-27)
- [x] Added missing dependencies: `crawl4ai>=0.5`, `python-dotenv>=1.0`
- [x] Created `.env.example` with all required variables documented
- [x] Added Telegram webhook secret validation (`telegram_validate.py`)
- [x] Added LLM health check endpoint (`/health/llm`)
- [x] Added HTTPS redirect middleware (`https_middleware.py`)
- [x] Added Redis rate limiter backend option (`security_redis.py`)
- [x] Added obscura install script (`install-obscura.bat`)
- [x] Updated CI workflow with complete test pipeline
- [x] Added 81 passing tests including new security tests
- [x] Documented troubleshooting in README.md

## Done (do not regress)
- [x] **PSWB 02 gap closures** — cross-source dependency inference (merge +
  prereq matching + LLM refinement + component bridging, acyclic/validated,
  JSON-safe `edge_sources` keys — fixed latent tuple-key crash), real dagre
  layered layout in Roadmap, per-step admin editing (GET/PUT/POST/DELETE
  `/admin/maps/{slug}/steps` + editor UI + audit log), explicit type-of-service
  input (form → `/build-task` → job → `TaskMap.service_type` → API → UI),
  per-step application/form deep links (`link` field: heuristic URL extraction
  + LLM with page-grounding — the URL must literally appear in the fetched
  page — plus gov-domain check and reachability probe). 81 pytest tests green.
- [x] **Secrets** — rotation, 2h TTL, boot refusal without APP_SECRET.
- [x] **Observability** — JSON logs + `/admin/metrics`.
- [x] **Backups** — online snapshots to E: + retention + endpoints.
- [x] **Postgres** — compose + driver ready; full suite runs on Postgres 16 in
  CI (local Docker/WSL engine on this box is broken — repair to test locally).
- [x] **WCAG/i18n** — full Hindi chrome, contrast, skip-link, aria-live.
- [x] **Load/edge** — headers, 1 MB cap, JSON errors, p95 dashboard test.
- [x] `.venv-civic` (Py 3.11): agent-reach 1.5, crawl4ai 0.9.4, trafilatura, cloakbrowser, FastAPI stack
- [x] Auth/JWT, per-user vault + Telegram link isolation (lab-tested)
- [x] Bynara-first LLM lane (4 probed free models) + minicpm5 offline fallback
- [x] Scrape cascade (3 tiers live) + worker build-map + admin verify desk
- [x] Watchman change-detector (proven: mutation → auto-unverify)
- [x] **Persona suite 20/20 + life-sim 8/8 green; frontend builds clean**
- [x] **Mini-Hermes agent subsystem** — 10 tools (read/write/patch/search/cmd), audit log, sub-agent spawning via ThreadPoolExecutor, REST API + frontend widget
- [x] **Landing page** — tricolor branding, feature grid, trust badges, bilingual (en/hi) with proper Devanagari rendering
- [x] **Full Hindi i18n** — all UI strings including agent panel and landing page translated
