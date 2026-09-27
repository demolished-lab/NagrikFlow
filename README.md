# Civic Path Navigator — Municipal Bureaucracy Path Visualizer (PSWB 02)

Citizens describe a civic task in plain words — with city, state and type of
service — and the system turns fragmented
government websites into a **verified, step-by-step dependency map** — and,
after DigiLocker login, into a **personal civic twin**: what you hold, what it
unlocked, and your easiest next win.

![Roadmap smoke test](smoke.png)

## Quick start (all free, ₹0)

```bash
# backend
C:\Users\Raja\.venv-civic\Scripts\python -m uvicorn app.main:app   # in backend/
# frontend
npm run dev                                                         # in frontend/ → :5173
```

## What it does

- **Roadmap graphs** — React Flow DAGs (dagre layered layout) of forms, offices,
  fees, prerequisites; every step links its official `.gov` source. Edges are
  inferred **across sources**: duplicate-step merge, prerequisite token-matching,
  source-order bridging, LLM dependency refinement (validated: ids, dedupe,
  acyclicity) — not just sequential chains.
- **Admin step editing** — per-step update/add/delete (title, detail, fee,
  official link, type) via `/admin/maps/{slug}/steps` with audit log.
- **Personal twin** — JWT login → DigiLocker OAuth (consent-first) → per-user
  encrypted vault → deterministic eligibility engine → `/me/dashboard` +
  plain-words LLM brief (Bynara free models first, local Ollama fallback).
- **Trust core** — no proof link = no display; admin verify stamps; night
  watchman re-fingerprints sources and **auto-revokes** verification on change.
- **Security** — app-wide rate limits, 5-strike lockout (423), OTP login,
  per-user Telegram link codes (single-use, 15-min), LLM-blinded prompts.
- **Channels** — Telegram worker (`app/hermes.py`: /start /status /next),
  mail lane (console → SMTP/Zoho → Resend), in-page Guide-me (page-agent).
- **Hindi toggle** (App + Dashboard) + WCAG basics (focus rings, labels, alerts).

## Repo map

| Path | What |
|---|---|
| `backend/app/main.py` | FastAPI: auth, vault, dashboard, maps, progress, admin (incl. per-step editing), jobs, webhooks |
| `backend/app/worker.py` | Scrape cascade (trafilatura → crawl4ai → obscura → Bynara) + cross-source merge & dependency inference |
| `backend/app/watch.py` | Change detector (sha256 fingerprints, auto-unverify, alerts) |
| `backend/app/digilocker.py` | MeriPehchaan OAuth2+PKCE + issued-docs (sandbox live, prod needs creds) |
| `backend/app/eligibility.py` | Deterministic rules: have → unlocked → next-easiest |
| `backend/app/llm.py` | Bynara free-model role routing → Ollama → template (never raises) |
| `backend/app/security.py` | Rate limiter + lockout policy |
| `backend/app/hermes.py` | Telegram long-poll worker (zero extra deps) |
| `backend/app/migrate.py` | Versioned migrations — DB is never deleted |
| `backend/sim/` | Life-sim (mock DigiLocker + fixture gov page), 20-persona suite |
| `backend/tests/` | pytest suite (CI runs it) |
| `frontend/src/` | React + TS + React Flow + dagre + page-agent guide |

## Verify

```bash
python -m pytest backend/tests/ -q        # 59 tests
python backend/sim/run_sim.py             # 8-step life sim (mock world)
python backend/sim/run_personas.py        # 20 personas, 20/20 sane
```

## Hermes Autonomous Agent

The built-in agent system can handle any task — code fixes, feature adds, deployments, research:

```bash
# Run Hermes via CLI
cd backend && python -m app.hermes_core --task "fix the login bug" --budget 20

# Or via REST API (admin only)
curl -X POST http://127.0.0.1:8000/hermes/run \
  -H "Authorization: Bearer <token>" \
  -d '{"task":"add parallel-branch roadmap rendering","mode":"auto","budget":30}'

# Spawn parallel sub-agents for specialized work
curl -X POST http://127.0.0.1:8000/hermes/spawn \
  -H "Authorization: Bearer <token>" \
  -d '{"parent_job_id":1,"tasks":[{"id":"t1","task":"write docs"},{"id":"t2","task":"add tests"}]}'

# View available tools (22 total)
curl http://127.0.0.1:8000/hermes/tools -H "Authorization: Bearer <token>"
```

**Tools include:** read_file, write_file, patch_file, search_files, run_cmd, validate_python, list_files, git_status, git_commit, run_tests, diagnose_db, plan, spawn_subagent, search_web, fetch_url, deploy_frontend, commit_changes, check_health, and more.

**Frontend:** Open the Agent tab in the web UI for a visual interface with chat, tools browser, and audit log.

## Docs

- `PENDING.md` — what's left (credentials + institutional track)
- `GOVERNMENT_READINESS_AUDIT.md` — DPDP compliance checklist mapped to code
- `PRODUCTION_DEPLOYMENT.md` — deployment runbook with troubleshooting
- `.env.example` — all required environment variables documented
- `/docs` — Swagger UI at http://localhost:8000/docs
