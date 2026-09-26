"""Notifications lane: OTP + due-date nudges + change alerts.

Providers (env-selected, all free-tier friendly):
- console: dev/log only
- smtp: stdlib smtplib, works with Zoho Mail free (5 users) or any SMTP
- resend: HTTP API, 3,000 emails/mo free (needs RESEND_API_KEY)

Patterns borrowed from macro-inc/macro (email->task linking, unified
triage) and MicahParks/magiclinksdev (OTP workflow). No Macro code is
vendored: Macro is AGPL-3.0, this project stays MIT-compatible.
"""
import os
import smtplib
from email.message import EmailMessage

import httpx

PROVIDER = os.environ.get("NOTIFY_PROVIDER", "console")
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
MAIL_FROM = os.environ.get("MAIL_FROM", "Civic Path Navigator <noreply@civicpath.in>")
RESEND_KEY = os.environ.get("RESEND_API_KEY", "")


def send(to: str, subject: str, body: str) -> dict:
    if PROVIDER == "resend" and RESEND_KEY:
        r = httpx.post("https://api.resend.com/emails",
                       headers={"Authorization": f"Bearer {RESEND_KEY}"},
                       json={"from": MAIL_FROM, "to": [to],
                             "subject": subject, "text": body}, timeout=30)
        r.raise_for_status()
        return {"via": "resend", "id": r.json().get("id")}
    if PROVIDER == "smtp" and SMTP_HOST:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = MAIL_FROM, to, subject
        msg.set_content(body)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
            s.starttls()
            if SMTP_USER:
                s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return {"via": "smtp"}
    print(f"[notify:console] to={to} subject={subject}\n{body}")
    return {"via": "console"}


def otp_message(code: str) -> tuple[str, str]:
    return ("Your Civic Path login code",
            f"Your verification code is {code}. Valid 10 minutes. "
            "Never share it.")


def due_message(title: str, due: str) -> tuple[str, str]:
    return (f"Reminder: {title} due {due}",
            f"{title} needs attention by {due}. Open your Civic Path "
            "dashboard to see the exact step and official link.")
