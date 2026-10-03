# Deploy — Civic Path Navigator

## Frontend → Cloudflare Pages

The frontend is a static Vite build. It cannot reach the backend through a local Vite proxy after deployment. Production builds now fail unless `VITE_API_URL` is explicitly set, preventing a published bundle from silently sending API requests to an unconfigured relative `/api` path.

1. In Pages build settings, set `VITE_API_URL` to the **stable public backend origin**, for example `https://api.your-domain.example` (no `/api` suffix; the backend routes are mounted at `/`).
2. Set the backend's `FRONTEND_ORIGINS` to the exact public site origin, e.g. `https://your-domain.example`. The default only allows `http://localhost:5173` and is not suitable for a public site.
3. Build with `npm run build` in `frontend/` and publish `frontend/dist/`.
4. After deployment, verify the site can register/login and call backend health/readiness endpoints from the production origin. Confirm browser preflight/CORS responses allow that exact origin.

For a deliberate same-origin deployment, configure a real `/api` reverse proxy or Pages Function first, then set `VITE_API_URL=/api` explicitly. Vite's `/api` development proxy is not included in the static production build.

## Backend → stable public origin

1. Run the FastAPI backend on an always-on host, bound to the intended local interface and protected by HTTPS at its public edge.
2. Use a **named/stable Cloudflare Tunnel and owned domain** for production. Quick `trycloudflare.com` tunnels are ephemeral and should be limited to local experiments.
3. Set backend environment variables from the production runbook; never commit `.env` or credentials. At minimum, configure a random 32+ character `APP_SECRET`, PostgreSQL `DATABASE_URL`, production `FRONTEND_ORIGINS`, and required integration credentials for the features being enabled.
4. Set `DIGILOCKER_REDIRECT_URI` to `https://<backend-host>/auth/digilocker/callback`; use `DIGILOCKER_ENV=production` only after API Setu approval and real credentials are provisioned.

## Night watchman

Configure a daily authenticated request to `/admin/jobs/recheck` (empty slug checks all maps). Changed maps are automatically unverified and linked users are alerted.

## Environment checklist

Backend variables are managed by the host, not committed to the repository: `APP_SECRET`, `DATABASE_URL`, `ADMIN_EMAILS`, `FRONTEND_ORIGINS`, `DIGILOCKER_REDIRECT_URI`, DigiLocker client credentials, Telegram token/webhook secret, mail provider settings, and monitoring/backup credentials as needed. Optional services remain disabled until configured.

## Production upgrades

Use managed PostgreSQL for production; use Redis when running multiple backend workers so rate-limit state is shared. Keep backups and `/readyz` monitoring configured.
