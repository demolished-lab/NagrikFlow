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
- [x] **pytest suite (99 tests) + GitHub Actions CI** — backend + frontend build.
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
  workers (Redis errors degrade to the in-process limiter — never a full
  bypass; `RATE_LIMIT_FAIL_CLOSED=1` rejects instead); memory store
  unchanged otherwise.
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
- [x] **Postgres proof** — `backend-pg` CI job runs all 99 tests against a
  real postgres:16 service (migrations, pg_trgm, pg_dump path).
- [x] **compose/Dockerfile** — added redis service + healthchecks,
  REDIS_URL/METRICS_TOKEN/BACKUP_S3_* passthrough, api healthcheck.
- [x] **compliance/ pack** — DPO letter, breach response (6h CERT-In),
  DPDP s.4–s.17 map, pen-test scope, usability protocol.
- [x] **81 tests at round 2 — 99 now** (14 new in `test_prod_hardening.py`,
  18 more in `test_audit_fixes.py` for the 2026-09-27 external audit).

## External audit remediation (2026-09-27, round 3)
Full re-audit verdict was "not production-ready"; every listed blocker fixed:
- [x] **Map visibility scoping** — `GET /maps/{slug}` + `GET /task/{slug}`
  serve unverified maps only to their builder (`TaskMap.created_by`) and
  admins; everyone else gets 404 (no existence leak).
- [x] **OTP hardening** — per-account lockout honoured (`locked_until` → 423,
  `failed_attempts` + lock at 5/15 min); each new request retires previous
  unused codes (single active code per account).
- [x] **Erasure completeness** — `DELETE /me/account` now also purges
  RoadmapMilestone, Notification, Grievance, and Job rows.
- [x] **Admin verify gates** — verification now requires a structurally valid
  graph (parses, has steps, no dangling edges, acyclic) AND fresh provenance
  (non-empty `source_urls`, `content_hash`, `checked_at` ≤ 45 days —
  `VERIFY_MAX_AGE_DAYS`). Seed carries provenance (m002 + m007 backfill).
- [x] **Rate limiter fail mode** — Redis errors degrade to the in-process
  MemoryStore (limits stay enforced, no bypass); `RATE_LIMIT_FAIL_CLOSED=1`
  rejects outright instead.
- [x] **Job hygiene** — startup `recover_orphans` (revive <24 h, fail the
  rest; `RECOVER_JOBS=0` to skip), `fail_if_stale` on job-status endpoints
  (3600 s), per-slug build locks (concurrent build → failed, not corrupt).
- [x] **SSRF guard** — `_require_public` entry check on every fetch tier +
  redirect hops + the wigolo `discover.fetch_text` path (hermes fetch tool
  included); `SSRF_PROBE=0` is the explicit dev/sim opt-out (sim fixture).
- [x] **Build-task 400** — discovery retries (enriched → bare → curated
  `catalog.py` fallback, response says which lane hit); per-URL policy
  rejections no longer abort the whole run (fixed `except ValueError` bug).
- [x] **Scraper quality** — `pick_link` never selects grievance/help/FAQ
  pages, hints match path+query only (not hostname), cross-host needs path
  evidence, `registration` hint added; paperless pages (Udyam) no longer get
  a fabricated "gather documents" step.
- [x] **Ops gaps** — `python -m app.migrate_pg` entrypoint (old documented
  command was broken), `python -m app.backup restore FILE [--yes]` with
  validation (sqlite integrity_check / pg_restore --list) + WAL sidecar
  cleanup, `postgresql-client` in the Dockerfile, CI `image` job builds the
  container and smoke-tests `/healthz` + `/readyz`.
- [x] **Frontend** — `#/admin` + `#/agent` show a friendly 403 view for
  non-admins (was blank white; loading state while profile resolves);
  Documents tab tracks the citizen's own pathways (pathway picker + honest
  "no pathway yet" CTA — no more hard-wired `udyam-register`).
- [x] **npm audit clean** — vite 5→8 + @vitejs/plugin-react 4→5.2
  (esbuild advisory chain fixed; build/dev-server/e2e verified).
- Verified: **pytest 99/99**, life-sim 8/8, personas 20/20, `tsc` + vite
  build clean, e2e 8/8 (serial — parallel chromium OOMs this 16 GB box),
  `npm audit` 0 vulnerabilities.

## External audit remediation (2026-09-27, round 4)
- [x] **Catalog fallback** — `build_task` re-runs `catalogmod.fallback_sources`
  after URL filtering empties the list (`discovery="catalog"`), 400 only if
  still empty; `_valid()` helper catches HTTPException + ValueError per URL.
- [x] **Heuristic quality** — `FREE_RE`/`REQ_DOC_RE` gates: fee falls back to
  "₹0 (stated on the official page)" only when free-text matches, document
  requirements only when a requirement verb appears ±60 chars of the token,
  no-docs pages get "Paperless — no documents to upload", apply CTA falls
  back to source URL (never empty).
- [x] **Chain guard** — `guard_chain(url)` validates every redirect hop;
  used by tier-2/3 fetches and `discover.fetch_text`; scheme/non-public
  failures re-raise, other failures fall back to `_require_public`.
- [x] **Job durability** — `Job.worker_id` + `lease_until` columns,
  atomic `claim()` (UPDATE ... WHERE status='queued'), `poll_once` dispatch +
  expired-lease revive + >24h fail, `start_poller` daemon (on unless
  `JOB_POLLER=0`), lease-aware `recover_orphans`, claim-at-top in
  `run_build`/`run_recheck`/`run_agent_job`/`run_hermes_job`, IntegrityError
  insert-race fallback via `_apply` closure, idempotent
  `uq_taskmap_slug` unique index in `_ensure_columns` (avoids migration
  version skew on SQLite+PG).
- [x] **Erasure** — `account_delete` purges user's unverified draft maps,
  anonymizes verified ones (`created_by=0`), purges Progress/milestones on
  erased slugs.
- [x] **Telegram hardening** — `telegram_validate.check` fail-closed
  (401 on unset secret unless `CIVIC_DEV=1`/`ALLOW_DEV_SECRET=1`),
  `uq_progress_user_map_step` + `uq_notification_user_ref` unique indexes +
  IntegrityError-tolerant commits, build-task field caps (422) and
  per-user active-build quota (429, `JOB_MAX_ACTIVE_PER_USER=3`).
- [x] **CI** — frontend job runs `npm audit --audit-level=moderate`.
- [x] **GOVERNMENT_READINESS_AUDIT.md** rewritten evidence-based
  (explicit "NOT ready to register" status, controls + external gaps).
- Verified: **pytest 112/112** (13 new round-4 tests in
  `test_audit_fixes.py`).

## Path-workflow packet feature (2026-09-27)
- [x] **Source meta** — tier fetches return `(text, final_url)`;
  `cascade_fetch_full` order trafilatura→crawl4ai→obscura→(extra)→
  scrapling→jina→wigolo (`CIVIC_EXTRA_TIERS=0` opts out); `TaskMap.source_urls`
  entries now `{url, ok, tier, final_url, guides, fetched_at}` (legacy
  strings still handled — no DB migration); `extract_guides` scores
  host-gated guide/report/so PDF+HTML links from fetched text.
- [x] **Packet** — new `backend/app/packet.py`: `build_packet` (ordered steps
  with prereqs from edges, document checklist from prereq-step DOC_RE
  tokens, fees, apply links, aggregated guides, counts) +
  `render_markdown`; endpoints `GET /task/{slug}/packet`,
  `GET /task/{slug}/packet.md` (attachment download),
  `POST /task/{slug}/deliver` (Telegram via linked chat or
  `CIVIC_TELEGRAM_CHAT_ID`, 400 without chat, 502 on send failure, ~3900-char
  truncation, alert → `console` when no Telegram).
- [x] **Hermes integration** — `path_packet(slug)` tool in `hermes_core`
  (`@_register_tool`, returns packet summary + first 6000 chars of markdown);
  `worker._fetch_scrapling_full` (omniharness `scrapling_bridge.py`,
  `SCRAPLING_PY`/python, 60s) and `worker._fetch_jina_full` (`r.jina.ai`,
  guarded opener, 25s) wired into the cascade.
- [x] **Frontend** — `api.ts` `taskPacket`/`deliverPacket`/
  `downloadPacketMd` (auth-header blob download); Roadmap "PATH WORKFLOW
  PACKET" panel: load-on-demand, checklist + guides render, Download .md,
  Send to Telegram (chat id + via shown), Hide.
- Verified: **pytest 119/119** (7 packet tests in `test_packet.py`),
  life-sim 8/8, personas 20/20, `tsc` + vite build clean, **e2e 9/9**
  (new packet test, serial), `npm audit` 0 vulnerabilities.

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
