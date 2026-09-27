# Personal Data Breach Response Procedure

Covers: DPDP Act s.8(6) (notify the Data Protection Board and each affected
data principal without delay) and CERT-In Directions of 28 Apr 2022
(incident report within **6 hours** of noticing the incident).

## Classification

A **personal data breach** = any unauthorised acquisition, disclosure,
alteration or loss of personal data that compromises confidentiality or
integrity. Triggers include:

- Database or S3 backup access by an unauthorised party
- Credential leak (ADMIN_EMAILS, DigiLocker secrets, bot tokens, APP_SECRET)
- Exfiltration of `user`, `consent`, `vaultitem`, or grievance content
- Ransomware / unauthorised admin actions on the host

A misconfiguration with **no evidence of access** (e.g. a stray debug log
containing no personal data) is logged but not reported externally.

## Timeline

| Step | Owner | Deadline |
|---|---|---|
| 1. Detect & declare (Slack/war-room + `#incident` note) | First responder | T+0 |
| 2. Contain: rotate `APP_SECRET`, bot tokens, DigiLocker secrets; revoke sessions; isolate host | Ops | T+1 h |
| 3. Preserve evidence: access logs (`requests.log`, uvicorn/nginx logs), DB audit rows, `.env` hashes | Ops | T+2 h |
| 4. Scope: which tables/fields, how many data principals, date range | DPO + Eng | T+4 h |
| 5. **CERT-In report** (email to incident@cert-in.org.in, portal incidents@cert-in.org.in) | DPO | **T+6 h** |
| 6. **Data Protection Board notification** (DPDP s.8(6)) + affected data-principal notices | DPO | Without delay |
| 7. Post-incident review: root cause, gate that failed, test that should exist | DPO + Eng | T+7 days |

## Notification content (DPDP s.8(6))

Each affected data principal receives: description of the breach, categories
of data involved, likely consequences, measures taken/proposed, and the DPO
contact — in clear language (Hindi/English per `LANG` support).

## Standing facts for the report

- Data inventory: identity (`user`), consent records, user-provided
  documents (`vaultitem`, encrypted at rest), grievance text, roadmap
  progress — see `DPDP_COMPLIANCE_MAP.md`.
- Location: API host + Postgres volume `pgdata` + nightly dumps in
  `backups/` (encrypted S3 target when `BACKUP_S3_*` set).
- Retention: account deletion purges personal tables; backups expire by
  retention loop (max 7 snapshots).

## Drills

Tabletop walkthrough of this procedure during each quarterly review;
next scheduled: [DATE].
