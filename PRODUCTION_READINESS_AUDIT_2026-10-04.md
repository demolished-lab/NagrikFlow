# NagrikFlow production-readiness audit — 2026-10-04

## Verdict

**Not yet confirmed production-ready.** The existing multisite experience is present, its core user journeys now have repeatable browser coverage, and the application code/build checks pass. A mode-600, Git-ignored `backend/.env` now exists for local development only; its generated local key, SQLite URL, localhost CORS origin, and DigiLocker sandbox setting are **not production configuration**. No live deployment was available to verify. Do not treat the reserved CI API URL as a production endpoint.

## Work completed

- Added deterministic Playwright coverage for guest task entry and location handoff into sign-in, registration fields, authenticated task build, pathway overview, interactive map and step detail, official-source links, saved progress and dashboard, admin source freshness/recheck, and a 390px mobile viewport.
- Made the real-backend UI audit opt-in with `LIVE_E2E=1`; its screenshots now go into Playwright's portable test output directory rather than a hard-coded Windows path.
- Removed the obsolete Python smoke test. It was outside Playwright Test's configured `frontend/e2e` directory, depended on an unconfigured Python `page` fixture, and asserted removed navigation labels.
- Added a Vite production-build guard: a production build now fails when `VITE_API_URL` is absent instead of silently publishing API calls to `/api`, which is only proxied by the local development server.
- Updated CI to use a reserved, non-routable API URL only for build validation, and clarified the real API-origin/CORS requirements in `DEPLOY.md`.
- Created a mode-600 local `backend/.env` with a generated local-only `APP_SECRET`; confirmed Git ignores the file. Production values were deliberately not fabricated.

## Validation evidence

| Check | Result |
|---|---|
| Frontend TypeScript + Vite production build | Passed with an explicit test-only API origin |
| Missing-API-origin guard | Passed: production build fails when `VITE_API_URL` is unset |
| Frontend `npm audit --audit-level=moderate` | Passed: 0 vulnerabilities reported |
| Playwright browser suite | Passed: 14 tests; 1 opt-in real-backend audit skipped |
| Backend pytest suite | Passed: 157 tests; 9 SQLite datetime deprecation warnings |
| Backend Ruff lint | Passed: all checks passed |
| Backend `pip-audit` | No known vulnerabilities found; the one documented exception `PYSEC-2026-3740` remains ignored per repository CI policy |
| `check_production_readiness.py` | Passed with 5 production warnings: SQLite database, DigiLocker sandbox, and empty Telegram/DigiLocker/Bynara credentials |

The browser suite uses deterministic API mocks for its UI journeys; it does **not** prove connectivity to a deployed backend. The real-backend audit is intentionally opt-in and was not run because no backend deployment/configuration was supplied.

## Production blockers before release

1. **Set a real `VITE_API_URL`.** Configure a stable HTTPS backend origin in the Pages build environment. `https://api.example.invalid` is used only in CI and is deliberately non-routable. If using a relative `/api`, first configure and test a real same-origin reverse proxy or Pages Function.
2. **Configure CORS for the deployed site.** Set backend `FRONTEND_ORIGINS` to the exact public frontend origin. The current backend default is local development (`http://localhost:5173`). Verify browser preflight and authenticated requests against the deployed API.
3. **Provision production secrets and infrastructure.** Replace local-only settings with a production `APP_SECRET`, PostgreSQL `DATABASE_URL`, HTTPS/domain, backups and `/readyz` monitoring. Keep secrets in the deployment's environment/secret manager; do not commit them. The generated local key is not suitable for production.
4. **Run the live browser smoke test against staging.** With the backend running and the deployed origin configured, run `LIVE_E2E=1 npm run test:e2e -- --grep "live end-to-end UI audit"`. Review the live build, source-warning, packet, dashboard, and help results before release.
5. **Complete optional/institutional launch requirements as applicable.** The existing deployment/government-readiness documents still list DigiLocker production approval/credentials, signed DPO appointment, pen test, vendor DPAs, accessibility statement, real-citizen usability testing, TLS/domain, and operational monitoring as pending. Do not imply government endorsement or regulatory approval without the required approvals.

## Files changed

- `frontend/e2e/multisite.spec.ts`
- `frontend/e2e/live-console-audit.spec.ts`
- `frontend/vite.config.ts`
- `.github/workflows/ci.yml`
- `DEPLOY.md`
- Removed: `frontend/playwright/e2e/test_smoke.py`
