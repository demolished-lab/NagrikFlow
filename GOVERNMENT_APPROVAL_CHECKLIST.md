# Government Approval Checklist — Civic Path Navigator

## Status: Technical Foundation Ready, Legal/Organizational Steps Pending

---

## 1. DPDP Act 2023 Compliance (Data Protection)

### Already Implemented ✓
- [x] Consent-first architecture (DEPA model)
- [x] Data principal rights: access, correction, erasure
- [x] Consent withdrawal mechanism (`/me/consent/withdraw`)
- [x] Data export functionality (`/me/data-export`)
- [x] Account deletion (`/me/account`)
- [x] Privacy policy (`backend/privacy_policy.md`)
- [x] Terms of service (`backend/terms_of_service.md`)
- [x] Grievance endpoint (`/me/grievance`, `/admin/grievances`)

### Required Before Approval ✗
- [ ] **Appoint Data Protection Officer (DPO)** — Name, contact, credentials on file
- [ ] **Grievance Officer Appointment Letter** — Formal document naming officer
- [ ] **Data Processing Agreements (DPAs)** — With DigiLocker/API Setu, Telegram
- [ ] **Breach Notification Procedure** — Documented process for 72-hour reporting
- [ ] **Data Localization Confirmation** — All data stored in India (verify hosting)
- [ ] **Privacy Impact Assessment (PIA)** — Third-party or internal audit report
- [ ] **Consent Receipt Format** — Standardized template (aligned with DEPA)
- [ ] **Retention Schedule** — Documented retention periods per data category
- [ ] **Third-Party Vendor Assessments** — Security reviews of API Setu, Telegram

---

## 2. Security & Infrastructure

### Already Implemented ✓
- [x] Rate limiting (5-strike lockout, 15-min lock)
- [x] Password hashing (PBKDF2, 200k iterations)
- [x] JWT session rotation (2h TTL)
- [x] Security headers (X-Frame-Options, CSP, etc.)
- [x] Body size limits (1 MB cap)
- [x] SSRF protection (.gov.in URL validation)
- [x] Per-user token isolation
- [x] Audit logging (agent actions)
- [x] JSON structured logs
- [x] Online backups to E: drive

### Required Before Approval ✗
- [ ] **Penetration Test Report** — Certified security firm assessment
- [ ] **Vulnerability Assessment** — Automated scan results (OWASP ZAP/Burp)
- [ ] **Infrastructure Hardening Checklist** — OS, network, database configs
- [ ] **Incident Response Plan** — Documented procedures for breach containment
- [ ] **Disaster Recovery Plan** — RTO/RPO targets, backup restoration tests
- [ ] **Business Continuity Plan** — Uptime SLA, failover procedures
- [ ] **Monitoring & Alerting** — UptimeRobot/Grafana configured
- [ ] **SSL/TLS Certificate** — Valid cert from trusted CA (not self-signed)
- [ ] **DDoS Mitigation** — Cloudflare/protection layer in place
- [ ] **WAF Configuration** — Web application firewall rules

---

## 3. Accessibility & UX

### Already Implemented ✓
- [x] WCAG 2.1 A basics (skip-link, aria-labels, focus indicators)
- [x] Full Hindi i18n (Devanagari rendering)
- [x] Bilingual interface toggle
- [x] Color contrast ratios (>4.5:1)
- [x] Keyboard navigation support
- [x] Reduced motion support

### Required Before Approval ✗
- [ ] **Full WCAG 2.1 AA Audit** — Certified accessibility audit report
- [ ] **Screen Reader Testing** — Verified with NVDA/JAWS
- [ ] **Mobile Responsiveness** — Tested on iOS/Android devices
- [ ] **Usability Testing Report** — Real citizen feedback (sample size 30+)
- [ ] **Accessibility Statement** — Published on website
- [ ] **Error Recovery Patterns** — Clear error messages, recovery guidance
- [ ] **Help Documentation** — User guides in both languages

---

## 4. Legal & Regulatory

### Already Implemented ✓
- [x] Privacy policy generated
- [x] Terms of service generated
- [x] Grievance mechanism endpoint
- [x] Consent receipts

### Required Before Approval ✗
- [ ] **Legal Review of TOS + Privacy Policy** — By qualified Indian lawyer
- [ ] **Government Empanelment Application** — Submit to MeitY/Digital India Corp
- [ ] **Certificate of Incorporation** — If operating as company/LLP
- [ ] **GST Registration** — If applicable
- [ ] **IRACT Registration** — If classified as intermediary
- [ ] **ISO 27001 Certification** — Information security management (recommended)
- [ ] **CERT-In Empanelment** — Cyber emergency response team recognition
- [ ] **MeitY Startup Recognition** — If eligible

---

## 5. Operational Readiness

### Already Implemented ✓
- [x] Admin dashboard for map management
- [x] Automated source verification (watchman)
- [x] Background job queue
- [x] Health check endpoint (`/health`)
- [x] Metrics endpoint (`/admin/metrics`)

### Required Before Approval ✗
- [ ] **Uptime SLA Commitment** — e.g., 99.5% availability
- [ ] **Support Channels** — Email, phone, chat support documented
- [ ] **Response Time Commitments** — e.g., grievance resolved in 7 days
- [ ] **Staff Training Materials** — Operator guides, runbooks
- [ ] **SOP Documents** — Standard operating procedures for key workflows
- [ ] **Change Management Process** — Version control, rollback procedures
- [ ] **Capacity Planning** — Expected load, scaling strategy
- [ ] **Cost Projections** — Hosting, maintenance, support costs
- [ ] **Exit Strategy** — Data portability if service terminates

---

## 6. Data & Content Quality

### Already Implemented ✓
- [x] Source verification via content hash comparison
- [x] Admin verify/unverify workflow
- [x] Source URL tracking per step
- [x] Fallback heuristic extraction (no LLM required)

### Required Before Approval ✗
- [ ] **Content Accuracy Audit** — Manual spot-check of top 20 maps
- [x] **Freshness Monitoring** — Watchman detects source changes
- [ ] **User Feedback Mechanism** — Report incorrect info endpoint
- [ ] **Correction Workflow** — Process for fixing inaccurate data
- [ ] **Map Coverage Report** — Which schemes/services are mapped
- [ ] **Source Reliability Score** — Track which gov URLs succeed/fail

---

## 7. Deployment Architecture

### Current State
- SQLite (dev-grade)
- Single-process Python server
- Cloudflare Pages + Tunnel (planned)

### Required Before Approval ✗
- [ ] **PostgreSQL Migration** — Neon/Supabase free tier or managed instance
- [ ] **Multi-worker Setup** — gunicorn/uwsgi with multiple workers
- [ ] **Reverse Proxy** — Nginx/Caddy configuration
- [ ] **Containerization** — Docker compose for reproducibility
- [ ] **CI/CD Pipeline** — GitHub Actions (exists but needs enhancement)
- [ ] **Environment Parity** — Staging environment matching production
- [ ] **Database Migration Strategy** — Version-controlled schema changes
- [ ] **Secrets Management** — HashiCorp Vault or AWS Secrets Manager

---

## Priority Roadmap

### Phase 1: Immediate (Week 1-2)
1. Generate proper APP_SECRET (32+ bytes)
2. Add Telegram bot token
3. Register DigiLocker Requester credentials
4. Create DPO appointment letter
5. Draft breach notification procedure
6. Run OWASP ZAP scan

### Phase 2: Short-term (Week 3-4)
1. Deploy to Postgres (Neon free tier)
2. Configure UptimeRobot monitoring
3. Create incident response plan
4. Publish accessibility statement
5. Submit MeitY startup recognition application

### Phase 3: Medium-term (Month 2-3)
1. Full WCAG 2.1 AA audit
2. Penetration test by certified firm
3. ISO 27001 certification process
4. Usability testing with real citizens
5. Build staging environment

### Phase 4: Long-term (Month 4-6)
1. CERT-In empanelment
2. Scaling infrastructure for production traffic
3. Multi-region deployment consideration
4. Advanced analytics/dashboard
5. Integration with other gov portals (UMANG, etc.)

---

## Required Documents to Create

1. `docs/DPO_APPOINTMENT.pdf` — Data Protection Officer appointment letter
2. `docs/BRACH_NOTIFICATION_PROCEDURE.md` — Step-by-step breach response
3. `docs/INCIDENT_RESPONSE_PLAN.md` — IR playbook
4. `docs/DISASTER_RECOVERY_PLAN.md` — DR playbook
5. `docs/SUPPORT_SLA.md` — Support commitments
6. `docs/ACCESSIBILITY_STATEMENT.html` — WCAG compliance statement
7. `docs/VENDOR_ASSESSMENTS/` — Third-party security reviews
8. `docs/TRAInING_MATERIALS/` — Operator guides

---

## Quick Win Actions (Can Do Now)

```bash
# 1. Generate secure secret
python -c "import secrets; print(secrets.token_hex(32))"

# 2. Add Telegram bot token to .env
echo "TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE" >> backend/.env

# 3. Create DPO appointment letter template
# See docs/DPO_TEMPLATE.md

# 4. Run OWASP ZAP basic scan
docker run -t owasp/zap2docker-weekly zap-baseline.py -t http://localhost:8000

# 5. Check SSL configuration
openssl s_client -connect your-domain.com:443 -showcerts
```

---

## Government Contacts

- **MeitY Helpline**: helpline@meity.gov.in
- **CERT-In**: incyber@cert-in.org.in
- **Digital India Corporation**: helpdesk@digitalindia.gov.in
- **API Setu Support**: support@apisetu.gov.in

---

*Last Updated: 2026-09-27*
*Status: Technical foundation complete, legal/organizational steps pending*
