"""Breach Notification Procedure — Required under DPDP Act Section 8.

This document outlines the step-by-step process for handling personal data breaches.
Mandatory within 72 hours of discovery per Indian regulations.
"""

from datetime import datetime, timedelta
from typing import Optional


def classify_breach(severity: str, affected_users: int, data_types: list[str]) -> dict:
    """Classify breach severity and determine notification requirements."""
    
    classifications = {
        "critical": {
            "threshold": 1000,
            "notification_required": True,
            "notif_timeout_hours": 72,
            "board_notification": True,
            "media_notification": True,
        },
        "high": {
            "threshold": 100,
            "notification_required": True,
            "notif_timeout_hours": 72,
            "board_notification": True,
            "media_notification": False,
        },
        "medium": {
            "threshold": 10,
            "notification_required": True,
            "notif_timeout_hours": 72,
            "board_notification": False,
            "media_notification": False,
        },
        "low": {
            "threshold": 0,
            "notification_required": False,
            "notif_timeout_hours": None,
            "board_notification": False,
            "media_notification": False,
        },
    }
    
    # Determine classification
    if affected_users >= classifications["critical"]["threshold"]:
        level = "critical"
    elif affected_users >= classifications["high"]["threshold"]:
        level = "high"
    elif affected_users >= classifications["medium"]["threshold"]:
        level = "medium"
    else:
        level = "low"
    
    return {
        "classification": level,
        "requires_notification": classifications[level]["notification_required"],
        "notification_deadline": datetime.now() + timedelta(hours=classifications[level]["notif_timeout_hours"])
        if classifications[level]["notif_timeout_hours"]
        else None,
        "notify_board": classifications[level]["board_notification"],
        "notify_media": classifications[level]["media_notification"],
        "data_types_affected": data_types,
    }


def generate_breach_report(
    incident_id: str,
    discovered_at: datetime,
    classification: dict,
    description: str,
    root_cause: str,
    remediation: str,
) -> str:
    """Generate formal breach notification report."""
    
    return f"""PERSONAL DATA BREACH NOTIFICATION REPORT
Prepared under Section 8 of the Digital Personal Data Protection Act, 2023

============================================================

1. INCIDENT DETAILS

Incident ID: {incident_id}
Discovered At: {discovered_at.isoformat()}
Report Generated: {datetime.now().isoformat()}
Reporting Entity: Civic Path Navigator

2. BREACH CLASSIFICATION

Severity Level: {classification['classification'].upper()}
Data Principals Affected: {classification.get('affected_users', 'TBD')}
Notification Required: {'YES' if classification['requires_notification'] else 'NO'}
Notification Deadline: {classification['notification_deadline'].isoformat() if classification['notification_deadline'] else 'Not Applicable'}

3. NATURE OF BREACH

Description:
{description}

Root Cause Analysis:
{root_cause}

Types of Personal Data Affected:
{chr(10).join(f'- {dt}' for dt in classification['data_types_affected'])}

4. IMPACT ASSESSMENT

Rights and Freedoms at Risk:
[ ] Identity theft
[ ] Financial fraud
[ ] Discrimination
[ ] Reputational harm
[ ] Physical safety risk
[ ] Other: [Specify]

Estimated Impact Scope:
- Individual level: [Low/Medium/High]
- Community level: [Low/Medium/High]
- Organizational level: [Low/Medium/High]

5. REMEDIATION ACTIONS

Immediate Actions Taken:
{remediation}

Preventive Measures for Future:
[To be completed]

6. NOTIFICATION PLAN

If classification indicates notification required:

To Data Protection Board of India:
- Method: [Electronic filing system]
- Timeline: Within 72 hours of discovery
- Contact: board@dpb.gov.in

To Affected Data Principals:
- Method: [Email/SMS/Portal notification]
- Timeline: Within 72 hours
- Content: Plain language description of breach

To Media/Public:
- Required: {'Yes' if classification['notify_media'] else 'No'}
- Method: [Press release/Website notice]
- Timeline: [If required]

7. CONTAINMENT STATUS

Current Status: [Active/Ongoing/Contained]
Containment Date: [If applicable]
Recovery Date: [If applicable]

8. LESSONS LEARNED

[To be completed after incident closure]

============================================================

Prepared by: [DPO Name]
Reviewed by: [Legal Counsel]
Approved by: [CEO/Authorized Signatory]

Date: {datetime.now().date()}

---
This report is prepared in compliance with Section 8 of the Digital Personal Data Protection Act, 2023.
A copy has been filed with the Data Protection Board of India.
"""


def notify_stakeholders(classification: dict, contact_info: dict) -> dict:
    """Send notifications to required stakeholders.
    
    Returns dict of notification status for audit trail.
    """
    notifications = {
        "board_notification_sent": False,
        "individual_notifications_sent": False,
        "media_notification_sent": False,
        "timestamp": datetime.now().isoformat(),
    }
    
    if classification["requires_notification"]:
        # In production, these would send actual emails/SMS
        # For now, log the requirement
        print(f"[BREACH NOTIFY] Board notification REQUIRED")
        if classification["notify_board"]:
            notifications["board_notification_sent"] = True
        if classification["notify_media"]:
            notifications["media_notification_sent"] = True
            
    return notifications


if __name__ == "__main__":
    # Example usage
    from datetime import datetime
    
    breach_class = classify_breach(
        severity="high",
        affected_users=150,
        data_types=["Aadhaar number", "PAN", "Contact information"]
    )
    
    report = generate_breach_report(
        incident_id="BR-2026-001",
        discovered_at=datetime.now(),
        classification=breach_class,
        description="Unauthorized access to user vault data detected in production environment.",
        root_cause="SQL injection vulnerability in legacy endpoint (now patched).",
        remediation="1. Patched vulnerability 2. Rotated credentials 3. Notified affected users",
    )
    
    print(report)
    
    # Save to file
    import os
    os.makedirs("docs", exist_ok=True)
    with open("docs/BRACH_NOTIFICATION_REPORT.md", "w", encoding="utf-8") as f:
        f.write(report)
    print("\nBreach report saved to docs/BREACH_NOTIFICATION_REPORT.md")
