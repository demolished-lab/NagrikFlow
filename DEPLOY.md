# Deploy — Civic Path Navigator (all free)

## Frontend → Cloudflare Pages (free, 500 builds/mo)
1. `cd frontend && npm run build` → `dist/`
2. Pages dashboard → Create → Upload `dist/` (or connect repo, build cmd `npm run build`, dir `dist`)
3. Set env var: `VITE_API_URL=https://<your-backend-tunnel>` (see below), rebuild.

## Backend → any always-on machine via Cloudflare Tunnel (free, no open ports)
1. On the host: `cloudflared tunnel --url http://localhost:8000` (or a named tunnel)
2. Copy the `https://*.trycloudflare.com` URL → `VITE_API_URL`, DigiLocker redirect URI, Telegram `setWebhook`:
   `https://api.telegram.org/bot<TOKEN>/setWebhook?url=<tunnel>/hooks/telegram`
3. Run backend: `.venv-civic/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` in `backend/`

## Night watchman cron (Windows Task Scheduler, free)
- Daily action: POST to `<tunnel>/admin/recheck` with admin JWT (empty slug = all maps).
- Changed maps auto-unverify + alert linked Telegram chats.

## Env checklist (backend/.env — never commit)
APP_SECRET, ADMIN_EMAILS, DIGILOCKER_CLIENT_ID/SECRET (+ENV=production after
approval), TELEGRAM_BOT_TOKEN, BYNARA_API_KEY (done), RESEND_API_KEY or SMTP_*
for mail, VITE_API_URL on the frontend side.

## Production upgrades (when usage grows)
SQLite → Neon/Supabase Postgres (SQLModel needs only DATABASE_URL change);
add Redis/Celery for /admin/build-map background jobs; Postgres pgvector for
portal-chunk retrieval.
