"""Personalization engine: vault facts -> dashboard + recommendations.

Rules are data, not code branches: each RECOMMENDATIONS entry declares
what the user HAS, what they GET, effort, and why. Deterministic and
auditable — LLM may phrase, never decide.
"""
from datetime import datetime

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


def personalize(vault_kinds: set[str], progress: dict) -> dict:
    """vault_kinds: kinds present in user vault. progress: {map_slug: done_count}."""
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
    # due/expiry attention from vault meta handled by caller; stub here
    return {"have": [LABELS.get(k, k) for k in have],
            "unlocked_paths": unlocked,
            "next_easiest": sorted(next_best, key=lambda x: len(x["missing"]))[:3],
            "in_progress_maps": progress,
            "generated_at": datetime.utcnow().isoformat() + "Z"}
