"""Personalization engine: vault facts -> dashboard + recommendations.

Rules are data, not code branches: each RECOMMENDATIONS entry declares
what the user HAS, what they GET, effort, and why. Deterministic and
auditable — LLM may phrase, never decide.
"""
from datetime import datetime, timezone

# kind -> human label
LABELS = {
    "aadhaar": "Aadhaar", "pan": "PAN", "udyam": "Udyam (MSME)",
    "gstin": "GSTIN", "dl": "Driving Licence", "shops": "Shops & Establishment",
}

RECOMMENDATIONS = [
    {"id": "udyam", "have": ["aadhaar", "pan"], "gives": "udyam",
     "effort": "10 min, free", "why": "Udyam needs only Aadhaar+PAN; unlocks MSME loans & subsidies."},
    {"id": "gst", "have": ["pan", "udyam"], "gives": "gstin",
     "effort": "20 min, free", "why": "With PAN + business proof, GST registration opens input tax credit."},
    {"id": "shops", "have": ["udyam"], "gives": "shops",
     "effort": "15 min, state fee varies", "why": "Shops Act registration is near-automatic once Udyam exists."},
    {"id": "pan", "have": ["aadhaar"], "gives": "pan",
     "effort": "e-KYC, ~7 days", "why": "PAN unlocks Udyam, GST and bank credit — highest leverage doc."},
]


def personalize(vault_kinds: set[str], progress: dict,
                items: list[dict] | None = None) -> dict:
    """vault_kinds: kinds present. items: [{kind,label,expires_at,meta}]
    for due/expiry attention. progress: {map_slug: done_count}."""
    have = sorted(vault_kinds)
    unlocked, next_best = [], []
    for r in RECOMMENDATIONS:
        if r["gives"] in vault_kinds:
            if r["gives"] not in ("aadhaar", "pan"):
                unlocked.append({"gives": LABELS.get(r["gives"], r["gives"]),
                                 "why": r["why"]})
        elif all(h in vault_kinds for h in r["have"]):
            missing = [h for h in r["have"] if h not in vault_kinds]
            next_best.append({"get": LABELS.get(r["gives"], r["gives"]),
                              "effort": r["effort"], "why": r["why"],
                              "missing": missing})
    # due/expiry attention from vault items (real, not stubbed)
    attention: list[dict] = []
    now = datetime.now(timezone.utc)
    for it in items or []:
        exp = it.get("expires_at")
        try:
            exp_dt = datetime.fromisoformat(exp) if exp else None
        except ValueError:
            exp_dt = None
        if exp_dt:
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            days = (exp_dt - now).days
            label = it.get("label") or LABELS.get(it.get("kind", ""), "document")
            if days < 0:
                attention.append({"level": "overdue", "text": f"{label} expired {-days}d ago — renew now."})
            elif days <= 30:
                attention.append({"level": "due", "text": f"{label} expires in {days}d."})
    # explicit due dates tucked in meta (e.g. {"due": "GST filing", "date": "2026-10-20"})
    import json as _json
    for it in items or []:
        try:
            meta = _json.loads(it.get("meta") or "{}")
        except Exception as e:
            from .obs import warn
            warn("eligibility", "corrupt item meta skipped", error=e)
            continue
        if meta.get("date"):
            try:
                d = datetime.fromisoformat(meta["date"])
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
                days = (d - now).days
                what = meta.get("due", LABELS.get(it.get("kind", ""), "item"))
                if days < 0:
                    attention.append({"level": "overdue", "text": f"{what} was due {-days}d ago."})
                elif days <= 30:
                    attention.append({"level": "due", "text": f"{what} due in {days}d."})
            except ValueError:
                continue
    return {"have": [LABELS.get(k, k) for k in have],
            "unlocked_paths": unlocked,
            "next_easiest": sorted(next_best, key=lambda x: len(x["missing"]))[:3],
            "attention": sorted(attention, key=lambda a: (a["level"] != "overdue", a["text"])),
            "in_progress_maps": progress,
            "generated_at": datetime.now(timezone.utc).isoformat()}
