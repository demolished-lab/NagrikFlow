# DPDP Act, 2023 — Compliance Map

Clause-by-clause mapping of the Digital Personal Data Protection Act, 2023
to controls in this codebase and its operations. **Legend:** ✅ implemented ·
🟡 partial · ⬜ organisational. Last reviewed: 2026-09-27.

| DPDP provision | Requirement | Control | Status |
|---|---|---|---|
| s.4 Notice | Give notice of purpose + data principal rights before collection | Consent notice shown at signup / first data action; text stored with consent records | 🟡 copy pending legal review |
| s.5 Consent | Free, specific, informed, unconditional, unambiguous consent; signifiable | `consent` table per purpose; withdraw endpoint `POST /me/consent/withdraw` revokes processing | ✅ |
| s.5(4)/(7) | Consent not required for specified legitimate uses / certain purposes | Public-service roadmap data (non-personal) processed without consent; documented purpose list in notice | 🟡 |
| s.6 Result of processing | Purpose limitation; no non-compliant rerouting of already-consent-reasonably-expected data | Data access confined to declared tables; no third-party sale; AI flows use user-provided content only | ✅ |
| s.7 Quality | Accurate, complete, up-to-date personal data | Profile edit + correction path; OTP-verified phone; content-hash freshness checks on maps | 🟡 |
| s.8 Security safeguards | Protect personal data with reasonable safeguards | Argon2id credentials, role gates, CSRF/state OAuth, SSRF guard on all fetch URLs, rate limiting + lockout, optional Redis store, encrypted vault storage path | ✅ |
| s.8(6) | Breach: notify Board + affected principals without delay | `compliance/BREACH_RESPONSE.md` (6-hour CERT-In + DPDP path) | ⬜ adopt + drill |
| s.9 | Erasure on withdrawal of consent / purpose no longer served | `POST /me/account/delete` purges user, vault, consent, progress, OTP/link/oauth rows; backups age out ≤ 7 snapshots | ✅ (grievance text retained as record — see below) |
| s.10 DPO | Appoint DPO; contact published | `compliance/DPO_APPOINTMENT.md` | ⬜ needs signatory |
| s.11 | Data principal rights: access, correction, erasure, grievance redressal, nomination | Access (`/me/profile`), correction (profile edit), erasure (account delete), grievances (`POST /me/grievance` → admin resolve); **nomination not yet built** | 🟡 nomination ⬜ |
| s.12 Children's data | Verifiable parental consent; no tracking/behavioural monitoring/targeted ads aimed at children | No ads; no third-party trackers; age gate present — parental-consent flow for under-18s **not built** | 🟡 |
| s.13/17 | Cross-border transfer per notified countries; significant-data-fiduciary duties | All processing on Indian/regional infra chosen at deploy; hosted frontends must stay same-region | ⬜ confirm at deploy |

## Known handling decisions

- **Grievance text retention:** deleting an account leaves grievance rows for
  statutory record-keeping; DPO to decide whether they are anonymised or
  attached to a tombstone subject ID instead of the (deleted) user row.
- **Backups:** erasure completes in primary storage immediately; encrypted
  dumps drop out of rotation within the retention window (max 7 snapshots).

## Open items (non-code)

1. Legal review of the consent notice copy (Hindi + English).
2. Nomination feature (record a nominee for the account) — engineering ticket.
3. Parental-consent flow for under-18 users — engineering ticket.
4. DPIA-lite write-up for the LLM/AI processing paths.
5. Annual audit cadence — sign-off recorded in this file.
