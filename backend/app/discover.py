"""Discovery lane via wigolo (KnockOutEZ/wigolo, AGPL-3.0, 5k stars).

wigolo = local-first web intelligence: 18-engine keyless search, tiered
fetch, crawl, diff/watch. Used here as a SEPARATE PROCESS over CLI/REST
boundary (never vendored) — keeps this MIT project license-clean.

Lanes: (1) discover official gov URLs for a task (no Exa key needed);
(2) keyless fetch fallback text for the scrape cascade.
Requires: `npx -y wigolo` on PATH (already on this box, ~/.wigolo cache).
"""
import json
import subprocess

WIGOLO = ["npx", "-y", "wigolo"]
TIMEOUT = 180
GOV_HINTS = (".gov.in", ".nic.in", "gst.gov.in", "mca.gov.in")


def _run(*args: str) -> dict:
    out = subprocess.run([*WIGOLO, *args, "--json"], capture_output=True,
                         text=True, timeout=TIMEOUT, shell=True)
    txt = (out.stdout or "").strip()
    try:
        return json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
    except Exception:
        return {"error": (out.stderr or txt)[:300]}


def discover(task: str, max_results: int = 8) -> list[dict]:
    """Keyless multi-engine search, gov domains boosted to the top."""
    res = _run("search", task, "--max-results", str(max_results))
    items = res.get("results", []) if isinstance(res, dict) else []
    def score(it: dict) -> tuple:
        url = it.get("url", "")
        return (0 if any(h in url for h in GOV_HINTS) else 1,
                -(it.get("score", 0) or 0))
    return sorted(items, key=score)[:max_results]


def fetch_text(url: str) -> str:
    """Keyless tiered fetch (auto-escalates to headless on bot walls)."""
    res = _run("fetch", url)
    md = (res.get("markdown", "") or res.get("text", "") or "").strip()
    if len(md) < 40:
        raise RuntimeError(f"wigolo fetch thin: {str(res)[:160]}")
    return md[:20000]
