# NagrikFlow production-readiness audit — 2026-10-04

## Verdict

**Not yet confirmed production-ready for a public deployment — but this
checkout is now fully verified, including the live browser audit.** The
multisite experience has repeatable browser coverage, the app code/build
checks pass, and the real-backend UI audit has been run here end-to-end
against the local backend (register → live CDX build → roadmap → packet →
dashboard, zero console errors, zero HTTP 5xx). What remains is deployment
configuration only: a real `VITE_API_URL`, exact-origin CORS, production
secrets, and PostgreSQL — all owner-supplied. A mode-600, Git-ignored
`backend/.env` exists for local development only; its generated local key,
SQLite URL, localhost CORS origin, and DigiLocker sandbox setting are
**not production configuration**. Do not treat the reserved CI API URL as a
production endpoint.

## Work completed

- Added deterministic Playwright coverage for guest task entry and location handoff into sign-in, registration fields, authenticated task build, pathway overview, interactive map and step detail, official-source links, saved progress and dashboard, admin source freshness/recheck, and a 390px mobile viewport.
- Made the real-backend UI audit opt-in with `LIVE_E2E=1`; its screenshots now go into Playwright's portable test output directory rather than a hard-coded Windows path.
- Removed the obsolete Python smoke test. It was outside Playwright Test's configured `frontend/e2e` directory, depended on an unconfigured Python `page` fixture, and asserted removed navigation labels.
- Added a Vite production-build guard: a production build now fails when `VITE_API_URL` is absent instead of silently publishing API calls to `/api`, which is only proxied by the local development server.
- Updated CI to use a reserved, non-routable API URL only for build validation, and clarified the real API-origin/CORS requirements in `DEPLOY.md`.
- Created a mode-600 local `backend/.env` with a generated local-only `APP_SECRET`; confirmed Git ignores the file. Production values were deliberately not fabricated.
- **Ran the live audit in this checkout (2026-10-04, second pass)** against
  the local backend (`uvicorn` on 127.0.0.1:8000 + vite dev proxy) — see
  evidence below. First pass failed on a 480 s terminal-state timeout while
  a real 5-source build finished at 8 m 18 s; the spec now allows 720 s
  (900 s test budget) with the measured wall time recorded in the comment.
- **Made source-warning assertions honest**: the live audit now hard-asserts
  only what is structural for a fresh map (`DRAFT PATHWAY`, review banner,
  packet render) and logs warnings when present — a 5/5-healthy-source build
  legitimately shows none. Deterministic warnings coverage (roadmap banner +
  packet banner) moved into the mocked suite, where fixtures guarantee a
  degraded source.

## Validation evidence

| Check | Result |
|---|---|
| Frontend TypeScript + Vite production build | Passed with an explicit test-only API origin |
| Missing-API-origin guard | Passed: production build fails when `VITE_API_URL` is unset |
| Frontend `npm audit --audit-level=moderate` | Passed: 0 vulnerabilities reported |
| Playwright browser suite (mocked journeys) | Passed: 14 tests incl. degraded-source warning banners; 1 opt-in live audit excluded by CI |
| **Playwright live audit (`LIVE_E2E=1`, real backend)** | **Passed: 1 test in 5.7 min — `AUDIT_HARD=[]`, `AUDIT_SOFT=[]` (zero console errors, zero 5xx, zero failed requests)** |
| Backend live probes | Passed: `/healthz` 200, `/readyz` 200 `{database: ok, migrations: ok, job_poller: ok}` |
| Backend pytest suite | Passed: 157 tests; 9 SQLite datetime deprecation warnings |
| Backend Ruff lint | Passed: all checks passed |
| Backend `pip-audit` | No known vulnerabilities found; the one documented exception `PYSEC-2026-3740` remains ignored per repository CI policy |
| `check_production_readiness.py` | Passed with 4 production warnings: SQLite database, DigiLocker sandbox, and empty Telegram/DigiLocker credentials |

Live-audit build detail: task `udyam registration` → `discovery: "cdx"`
(Common Crawl lane found the deep Udyam form/login pages), 5/5 sources
fetched (trafilatura), 29 steps, evidence snapshots + first-baseline hashes
stored by the new watch pipeline — i.e. the free-stack features ran under
real conditions, not just tests.

## Production blockers before release

1. **Set a real `VITE_API_URL`.** Configure a stable HTTPS backend origin in the Pages build environment. `https://api.example.invalid` is used only in CI and is deliberately non-routable. If using a relative `/api`, first configure and test a real same-origin reverse proxy or Pages Function.
2. **Configure CORS for the deployed site.** Set backend `FRONTEND_ORIGINS` to the exact public frontend origin. The current backend default is local development (`http://localhost:5173`). Verify browser preflight and authenticated requests against the deployed API.
3. **Provision production secrets and infrastructure.** Replace local-only settings with a production `APP_SECRET`, PostgreSQL `DATABASE_URL`, HTTPS/domain, backups and `/readyz` monitoring. Keep secrets in the deployment's environment/secret manager; do not commit them. The generated local key is not suitable for production.
4. **Run the live browser smoke test against the deployed staging origin.**
   The audit already passed here against the local backend (2026-10-04);
   after blockers 1–3 are configured on a real deployment, re-run
   `LIVE_E2E=1 npm run test:e2e -- --grep "live end-to-end UI audit"` with
   the deployed origin as the API target and review the live build,
   packet, dashboard, and help results.
5. **Complete optional/institutional launch requirements as applicable.** The existing deployment/government-readiness documents still list DigiLocker production approval/credentials, signed DPO appointment, pen test, vendor DPAs, accessibility statement, real-citizen usability testing, TLS/domain, and operational monitoring as pending. Do not imply government endorsement or regulatory approval without the required approvals.

## Files changed

- `frontend/e2e/multisite.spec.ts`
- `frontend/e2e/live-console-audit.spec.ts` (720 s terminal-state wait; structural draft assertions; warnings logged when present)
- `frontend/e2e/interactive-map.spec.ts` (deterministic roadmap + packet warning-banner coverage)
- `frontend/vite.config.ts`
- `.github/workflows/ci.yml`
- `DEPLOY.md`
- Removed: `frontend/playwright/e2e/test_smoke.py`
