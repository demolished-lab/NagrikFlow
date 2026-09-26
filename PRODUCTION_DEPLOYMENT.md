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
python -m migrate_pg
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

# Run with gunicorn (multi-worker)
gunicorn app.main:app \
  --workers 4 \
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

```bash
# UptimeRobot (free tier)
# Monitor: https://your-domain.com/health
# Check every 5 minutes
# Alert on: HTTP 5xx, timeout > 30s

# Optional: Self-hosted metrics
# Install Prometheus + Grafana for:
# - Request rates
# - Error rates
# - Latency percentiles
# - Database connections
```

### 9. Backup Strategy

```bash
# Daily automated backups to E: drive
# Retention: 7 days
# Test restore monthly

# Manual backup command
cd backend
python -m app.backup run

# Verify backup
ls -la data/backups/
```

### 10. CI/CD Pipeline Enhancement

Update `.github/workflows/ci.yml`:

```yaml
name: civic-ci

on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r backend/requirements.txt pytest
      - run: python -m pytest backend/tests/ -q
        env: { ALLOW_DEV_SECRET: "1" }
      - run: cd backend && python -m py_compile app/*.py
      
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 24, cache: npm }
      - run: npm ci --prefix frontend
      - run: npm run build --prefix frontend
      - run: npx tsc --noEmit --project frontend/tsconfig.json

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install safety
      - run: safety check -r backend/requirements.txt
```

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

# 4. Migrate database (if Postgres)
if [[ "$DATABASE_URL" == postgresql* ]]; then
    python -m migrate_pg
fi

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
    --workers 4 \
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
- [ ] Appoint Data Protection Officer
- [ ] Draft breach notification procedure
- [ ] Create incident response plan
- [ ] Obtain penetration test report
- [ ] Register with MeitY/Digital India Corp
- [ ] Get ISO 27001 certification (recommended)
- [ ] Sign Data Processing Agreements with vendors
- [ ] Publish accessibility statement
- [ ] Conduct usability testing with real citizens

### Infrastructure ❌ (Requires Investment)
- [ ] PostgreSQL database (Neon/Supabase free tier or paid)
- [ ] SSL certificate (Let's Encrypt free)
- [ ] Domain name registration
- [ ] Uptime monitoring setup
- [ ] CI/CD pipeline enhancement
- [ ] Staging environment
- [ ] Backup automation

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
- [ ] Set up monitoring
- [ ] Create DPO appointment letter

### Week 2: Compliance
- [ ] Submit to MeitY startup recognition
- [ ] Draft breach notification procedure
- [ ] Create incident response plan
- [ ] Publish privacy policy and TOS
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
