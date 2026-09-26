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
- [x] **pytest suite (8 tests) + GitHub Actions CI** — backend + frontend build.
- [x] **page-agent Guide-me** — installed, per-step Q&A with user's own key (app key never leaves server).
- [x] **Postgres-ready** — `psycopg` driver in, URL-driven; needs a server to go live.
- [ ] **Hermes worker rebuild** — source absent; only `alerts.py` + webhook exist.
- [x] **Background jobs** — queued build/recheck + polling UI (single-process; Redis later).
- [ ] **Postgres migration** — SQLite is dev-grade. SQLModel needs only a
  `DATABASE_URL` swap (Neon/Supabase free tier).
- [ ] **DigiLocker sandbox end-to-end** — run the consent flow against
  `sandbox.api-setu.in` once Requester creds exist (mock passes today).
- [ ] **Parallel-branch rendering** — DAG supports it; Roadmap UI lays out top-down only.
|- [x] **pytest suite (39 tests)** — agent tools schema, audit log, admin gating, grievance model.
|- [x] **Hermes autonomous agent** — 22 tools, sub-agent spawning, web search, deployment, self-healing loop
- [ ] **MiroFish prediction lane (Phase-4)** — AGPL-3.0, heavy infra; pattern-only for now.

## Done (do not regress)
- [x] **Secrets** — rotation, 2h TTL, boot refusal without APP_SECRET.
- [x] **Observability** — JSON logs + `/admin/metrics`.
- [x] **Backups** — online snapshots to E: + retention + endpoints.
- [x] **Postgres** — compose + driver ready (needs a server to go live).
- [x] **WCAG/i18n** — full Hindi chrome, contrast, skip-link, aria-live.
- [x] **Load/edge** — headers, 1 MB cap, JSON errors, p95 dashboard test.
- [x] `.venv-civic` (Py 3.11): agent-reach 1.5, crawl4ai 0.9.4, trafilatura, cloakbrowser, FastAPI stack
- [x] Auth/JWT, per-user vault + Telegram link isolation (lab-tested)
- [x] Bynara-first LLM lane (4 probed free models) + minicpm5 offline fallback
- [x] Scrape cascade (3 tiers live) + worker build-map + admin verify desk
- [x] Watchman change-detector (proven: mutation → auto-unverify)
- [x] **Persona suite 20/20 + life-sim 8/8 green; frontend builds clean**\n- [x] **Mini-Hermes agent subsystem** — 10 tools (read/write/patch/search/cmd), audit log, sub-agent spawning via ThreadPoolExecutor, REST API + frontend widget\n- [x] **Landing page** — tricolor branding, feature grid, trust badges, bilingual (en/hi) with proper Devanagari rendering
- [x] **Full Hindi i18n** — all UI strings including agent panel and landing page translated
