"""Privacy Policy - Civic Path Navigator

Last Updated: [Date]

1. DATA CONTROLLER
   Civic Path Navigator
   Admin: admin@civicpath.in

2. DATA COLLECTION
   We collect only consent-gated document metadata:
   - Document type (aadhaar, pan, udyam, gstin, dl, etc.)
   - Issuer information (e.g., "in.gov.pan")
   - Reference/URI (DigiLocker URI or registration number)
   - Verification status and expiry dates
   - Never store document blobs - only verified facts

3. LAWFUL BASIS
   Consent-first design per India's DEPA model (DPDP Act, 2023)
   All document processing requires explicit user consent
   Consent can be withdrawn at any time

4. DATA RETENTION
   - Vault items retained until consent withdrawn
   - Erasure job runs daily: DELETE vault WHERE consent withdrawn
   - Logs retained 180 days minimum
   - Backups retained per BACKUP_KEEP setting (default: 7)

5. DATA SUBJECT RIGHTS
   - Right to withdraw consent at any time
   - Right to data export (JSON receipt)
   - Right to data correction
   - Right to grievance escalation

6. THIRD PARTY DISCLOSURES
   - DigiLocker / API Setu: Only with explicit user consent
   - Telegram: Only with user-chat binding (single user per chat)
   - Never sell user data

7. SECURITY MEASURES
   - PBKDF2 password hashing (200,000 iterations)
   - JWT session rotation (2-hour TTL, rotation-safe)
   - Rate limiting (5-strike lockout, 15-min lock)
   - Per-user token isolation (no cross-user data leakage)
   - Audit trail for all access

8. CONTACT
   For grievances: grievance@civicpath.in
   DPDP Officer: [To be appointed]

9. CHANGES TO THIS POLICY
   Material changes will be communicated via dashboard and email"""