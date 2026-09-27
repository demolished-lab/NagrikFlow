# Production Deployment Checklist — Civic Path Navigator

## Pre-Deployment Requirements

### 1. Security Hardening

#### Secrets Management
```bash
# Generate secure APP_SECRET (run once, save securely)
python -c "import secrets; print(secrets.token_hex(32))"
```
- [ ] Set `APP_SECRET` in `.env` (32+ random hex characters)
- [ ] Set `APP_SECRET_PREV` only during rotation
- [ ] Never commit `.env` to git
- [ ] Rotate secrets quarterly

#### Environment Variables Required
```bash
# Production .env
APP_SECRET=<32-byte-hex-string>
APP_SECRET_PREV=          # Only during rotation
SESSION_TTL_SECONDS=7200  # 2 hours
ALLOW_DEV_SECRET=         # Empty in production
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=                # redis://host:6379/0 — enables shared rate limits + multi-worker
TELEGRAM_WEBHOOK_SECRET=  # webhook header validation (set + send as X-Telegram-Bot-Api-Secret-Token)
METRICS_TOKEN=            # if set, /metrics requires Bearer/X-Metrics-Token
BACKUP_S3_ENDPOINT=       # S3-compatible endpoint (empty = local files only)
BACKUP_S3_BUCKET=
BACKUP_S3_KEY_ID=
BACKUP_S3_SECRET=
BACKUP_S3_REGION=
BACKUP_S3_PREFIX=civic-pathfinder/
DIGILOCKER_CLIENT_ID=<from-api-setu>
DIGILOCKER_CLIENT_SECRET=<from-api-setu>
DIGILOCKER_REDIRECT_URI=https://your-domain.com/auth/digilocker/callback
DIGILOCKER_ENV=production
TELEGRAM_BOT_TOKEN=<from-@BotFather>
BYNARA_API_KEY=<your-key>
BYNARA_BASE_URL=https://router.bynara.id/v1
BYNARA_MODEL=nemotron-3-ultra-free
SMTP_HOST=smtp.your-provider.com
SMTP_PORT=587
SMTP_USER=noreply@civicpath.in
SMTP_PASS=<app-password>
MAIL_FROM="Civic Path Navigator <noreply@civicpath.in>"
GRIEVANCE_EMAIL=grievance@civicpath.in
FRONTEND_ORIGINS=https://your-domain.com
```

### 2. Database Migration to PostgreSQL

```bash
# Deploy to Neon/Supabase (free tier available)
# 1. Create database at neon.tech or supabase.com
# 2. Get connection string
# 3. Run migrations
DATABASE_URL=postgresql://user:pass@ep-xxx.region.aws.neon.tech/civic_pathfinder

# Test migration
cd backend
python -m app.migrate_pg
```

### 3. SSL/TLS Configuration

```bash
# Using Cloudflare (recommended)
# 1. Add domain to Cloudflare
# 2. Enable SSL: Full (strict)
# 3. Force HTTPS redirect
# 4. Enable HSTS

# Or use certbot
sudo certbot --nginx -d your-domain.com
```

### 4. Server Configuration (Production)

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Run with gunicorn.
# WORKERS: single worker with SQLite (single-writer + process-local limits).
# With DATABASE_URL=Postgres AND REDIS_URL set, rate-limit state is shared via
# Redis and the DB handles concurrency → --workers 4 is allowed (jobs run
# per-request in-process; no external queue needed).
# Scaling rules:
#   SQLite  → always --workers 1
#   Postgres only → --workers 1 (rate limit still per-process)
#   Postgres + REDIS_URL → --workers 4 (recommended)
gunicorn app.main:app \
  --workers 1 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 127.0.0.1:8000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

### 5. Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Body size limit
        client_max_body_size 1M;
    }

    # Static files
    location /static/ {
        alias /path/to/frontend/dist/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

### 6. Telegram Bot Setup

```bash
# 1. Message @BotFather on Telegram
# 2. Create new bot: /newbot
# 3. Set bot name and username
# 4. Copy token to .env as TELEGRAM_BOT_TOKEN
# 5. Set webhook (after deployment):
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain.com/hooks/telegram"}'
```

### 7. DigiLocker API Registration

```bash
# Visit: https://partners.apisetu.gov.in
# 1. Register organization
# 2. Apply for Requester credentials
# 3. Specify scopes: userdetails, files.issueddocs
# 4. Wait for approval (2-5 business days)
# 5. Set credentials in .env
```

### 8. Monitoring & Alerting

Endpoints (all implemented):

```bash
GET /healthz          # liveness — 200 {"ok":true}
GET /readyz           # readiness: DB connect + schema_version + Redis (if configured)
                      # → 503 on failure; point k8s/compose healthchecks here
GET /metrics          # Prometheus text: civic_http_requests_total,
                      # civic_http_errors_total, civic_http_request_duration_ms_total
                      # (paths normalized to 2 segments → bounded cardinality)
                      # If METRICS_TOKEN set: Authorization: Bearer <token> or X-Metrics-Token
GET /admin/integrations?probe=1   # admin-only doctor: database, rate_limiter, redis,
                      # telegram, digilocker, llm, backup, email, nltk_guard (booleans only)
```

```yaml
# prometheus.yml scrape example
- job_name: civic-api
  metrics_path: /metrics
  # authorization: { credentials: <METRICS_TOKEN> }   # if set
  static_configs: [{ targets: ["127.0.0.1:8000"] }]
```

```bash
# UptimeRobot (free tier)
# Monitor: https://your-domain.com/readyz   # fails when DB/Redis down
# Check every 5 minutes
# Alert on: HTTP 5xx, timeout > 30s
```

Structured request logs (`{"m","p","s","ms"}`) go to stderr — ship them
wherever you keep logs; `/readyz` is the alerting signal, `/healthz` the
restart signal.

### 9. Backup Strategy

```bash
# Manual backup (works on SQLite + Postgres)
cd backend
python -m app.backup run
#  sqlite → file copy (online, consistent)
#  Postgres → pg_dump (password passed via PGPASSWORD, never argv)
#  When BACKUP_S3_* configured → uploads to S3-compatible storage
#    BACKUP_S3_ENDPOINT / BACKUP_S3_BUCKET / BACKUP_S3_KEY_ID /
#    BACKUP_S3_SECRET / BACKUP_S3_REGION / BACKUP_S3_PREFIX
#  Retention: keeps 7 newest snapshots; upload failures are logged, never fatal

# Verify backup
ls -la backups/
python -m app.backup list

# Restore drill (works on SQLite + Postgres; run with the app STOPPED):
python -m app.backup list                     # find the snapshot to restore
python -m app.backup restore backups/civic-20260927-030000.dump
python -m app.backup restore backups/civic-20260927-030000.db --yes   # sqlite only
#  backup is validated first (sqlite integrity_check / pg_restore --list)
#  sqlite  → target file replaced, stale -wal/-shm sidecars removed (needs --yes)
#  postgres → pg_restore --clean --if-exists into DATABASE_URL (PGPASSWORD env)
# Schedule: daily (cron/systemd timer), test restore quarterly
```

### 10. CI/CD Pipeline

`.github/workflows/ci.yml` runs on every push/PR:

| Job | What it proves |
|---|---|
| `backend` | Full pytest suite (99 tests) on SQLite |
| `backend-pg` | **Full suite on real PostgreSQL 16** (migrations, pg_trgm, pg_dump backup path) |
| `image` | Backend **Docker image builds** and boots: postgresql-client present, startup migrations run, `/healthz` + `/readyz` answer |
| `frontend` | `vite build` + `tsc --noEmit` |
| `deps` | `pip-audit` (nltk PYSEC-2026-3740 tracked as explicit exception — crawl4ai transitive, no fix yet) |

---

## Deployment Commands

### Quick Deploy Script

```bash
#!/bin/bash
# deploy.sh - One-command deployment

set -e

echo "🚀 Deploying Civic Path Navigator..."

# 1. Pull latest
git pull origin main

# 2. Install dependencies
pip install -r backend/requirements.txt
npm ci --prefix frontend

# 3. Run tests
python -m pytest backend/tests/ -q
npm run build --prefix frontend

# 4. Migrate database (SQLite or Postgres — both work, PG adds pg_trgm indexes)
(cd backend && python -m app.migrate_pg)

# 5. Restart service
sudo systemctl restart civic-pathfinder

echo "✅ Deployment complete!"
echo "📊 Health check: https://your-domain.com/health"
```

### Systemd Service

```ini
# /etc/systemd/system/civic-pathfinder.service
[Unit]
Description=Civic Path Navigator Backend
After=network.target

[Service]
User=civic
Group=civic
WorkingDirectory=/opt/civic-pathfinder/backend
ExecStart=/opt/civic-pathfinder/.venv/bin/gunicorn app.main:app \
    --workers 1 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --timeout 120
Environment=PATH=/opt/civic-pathfinder/.venv/bin
EnvironmentFile=/opt/civic-pathfinder/backend/.env

[Install]
WantedBy=multi-user.target
```

---

## Government Approval Readiness

### Technical ✅ (Complete)
- [x] Consent-first architecture
- [x] Data principal rights (access, correction, erasure)
- [x] Rate limiting + lockout
- [x] Password hashing (PBKDF2, 200k iterations)
- [x] JWT session rotation (2h TTL)
- [x] Security headers
- [x] Audit logging
- [x] Online backups
- [x] Bilingual support (en/hi)
- [x] WCAG basics (skip-link, aria-labels)
- [x] Grievance mechanism

### Legal/Organizational ❌ (Requires Action)
- [x] Draft breach notification procedure → `compliance/BREACH_RESPONSE.md`
- [x] DPO appointment letter template → `compliance/DPO_APPOINTMENT.md`
- [x] DPDP clause → control map → `compliance/DPDP_COMPLIANCE_MAP.md`
- [x] Pen-test scope & rules of engagement → `compliance/PEN_TEST_SCOPE.md`
- [x] Usability testing protocol → `compliance/USABILITY_TESTING_PROTOCOL.md`
- [ ] **Sign/issue** the DPO letter (needs real signatory)
- [ ] Conduct pen test (issue `PEN_TEST_SCOPE.md` to vendor)
- [ ] Register with MeitY/Digital India Corp
- [ ] Get ISO 27001 certification (recommended)
- [ ] Sign Data Processing Agreements with vendors
- [ ] Publish accessibility statement
- [ ] Conduct usability testing with real citizens (run protocol, N=8)
- [ ] Parental-consent flow + nomination feature (DPDP s.11/s.12 gaps)

### Infrastructure ❌ (Requires Investment)
- [x] CI/CD: SQLite suite + **Postgres suite** + frontend + pip-audit
- [x] Backup automation (local dumps + optional S3, retention 7)
- [x] Monitoring endpoints (healthz/readyz/metrics + integrations doctor)
- [ ] PostgreSQL database (Neon/Supabase free tier or paid) — CI-proven; wire at deploy
- [ ] Redis (for multi-worker rate limits; in-process fallback exists)
- [ ] SSL certificate (Let's Encrypt free)
- [ ] Domain name registration
- [ ] External uptime monitor (UptimeRobot) pointed at /readyz
- [ ] Staging environment

---

## Cost Estimates

### Free Tier (Minimum Viable)
- **Hosting**: Cloudflare Pages (frontend) + Cloudflare Tunnel (backend)
- **Database**: Neon free tier (500MB)
- **Monitoring**: UptimeRobot free (5 monitors)
- **SSL**: Let's Encrypt (free)
- **Domain**: ~₹800/year

**Total: ~₹800/year** (just domain)

### Production Tier (Recommended)
- **Hosting**: AWS Lightsail ($20/month) or DigitalOcean ($12/month)
- **Database**: Neon Pro ($20/month) or Supabase Pro ($25/month)
- **Monitoring**: UptimeRobot Pro ($8/month) or Grafana Cloud (free tier)
- **Email**: Resend ($20/month for 30k emails)
- **Domain**: ~₹800/year

**Total: ~$50-60/month (₹4,000-5,000/month)**

### Government Approval Tier
- **Penetration Test**: ₹25,000-50,000 (one-time)
- **ISO 27001 Certification**: ₹1,00,000-2,00,000 (first year)
- **Legal Review**: ₹25,000-50,000 (one-time)
- **DPO Consultation**: ₹10,000-20,000/month (or internal appointment)

**Total Additional: ~₹1,60,000-3,20,000 first year**

---

## Timeline

### Week 1: Foundation
- [ ] Generate APP_SECRET
- [ ] Deploy to staging
- [ ] Configure DNS and SSL
- [x] Monitoring endpoints (healthz/readyz/metrics)
- [x] Create DPO appointment letter (template ready in `compliance/`)

### Week 2: Compliance
- [ ] Submit to MeitY startup recognition
- [x] Draft breach notification procedure (`compliance/BREACH_RESPONSE.md`)
- [x] Create incident response plan (same + `PEN_TEST_SCOPE.md`)
- [ ] Sign & publish DPO letter; publish privacy policy and TOS
- [ ] Set up grievance email

### Month 2: Security
- [ ] Schedule penetration test
- [ ] Run OWASP ZAP scan
- [ ] Fix identified vulnerabilities
- [ ] Document security controls
- [ ] Prepare for ISO 27001

### Month 3: Approval
- [ ] Complete penetration test
- [ ] Submit security documentation
- [ ] Apply for government empanelment
- [ ] Conduct usability testing
- [ ] Iterate based on feedback

---

*Last Updated: 2026-09-27*
*Next Review: After first security audit*
