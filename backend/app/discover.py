"""Discovery lane via wigolo (KnockOutEZ/wigolo, AGPL-3.0, 5k stars).

wigolo = local-first web intelligence: 18-engine keyless search, tiered
fetch, crawl, diff/watch. Used here as a SEPARATE PROCESS over CLI/REST
boundary (never vendored) — keeps this MIT project license-clean.

Lanes: (1) discover official gov URLs for a task (no Exa key needed);
(2) keyless fetch fallback text for the scrape cascade;
(3) Common Crawl CDX archive lane — find deep pages on known government
    domains WITHOUT touching the live government site (polite by design;
    CIVIC_CDX=0 opts out).
Requires: `npx -y wigolo` on PATH (already on this box, ~/.wigolo cache).
"""
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request

WIGOLO = ["npx", "-y", "wigolo"]
TIMEOUT = 180
GOV_HINTS = (".gov.in", ".nic.in", "gst.gov.in", "mca.gov.in")

CC_BASE = "https://index.commoncrawl.org"
_cc_cache: dict = {}

# tokens too generic to prove a URL is task-relevant
_CDX_STOP = frozenset({"http", "https", "www", "gov", "html", "aspx", "php",
                       "page", "main", "home", "index", "the", "and", "for",
                       "with", "from", "that", "this", "your", "what", "how"})


def _run(*args: str) -> dict:
    try:
        out = subprocess.run([*WIGOLO, *args, "--json"], capture_output=True,
                             text=True, timeout=TIMEOUT, shell=False,
                             check=False)
    except (OSError, subprocess.SubprocessError) as ex:
        return {"error": f"wigolo unavailable: {ex}"[:300]}
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


def fetch_text(url: str, return_final: bool = False):
    """Keyless tiered fetch (auto-escalates to headless on bot walls).

    return_final=True -> (text, final_url_after_redirects) for the packet
    artifact; default returns text only (back-compat)."""
    from .worker import _require_public, guard_chain
    final = url
    try:
        final = guard_chain(url)  # validate every redirect hop (wigolo fetches raw)
    except RuntimeError:
        raise  # explicit scheme/non-public block — never proceed past this
    except Exception:
        # entry unreachable from here (DNS/network): same indeterminate stance
        # as _require_public — entry guard only, the fetch resolves it itself
        _require_public(url)
    res = _run("fetch", final)
    md = (res.get("markdown", "") or res.get("text", "") or "").strip()
    if len(md) < 40:
        raise RuntimeError(f"wigolo fetch thin: {str(res)[:160]}")
    text = md[:20000]
    return (text, final) if return_final else text


# ------------------------- Common Crawl CDX lane --------------------------

def _cdx_enabled() -> bool:
    return os.environ.get("CIVIC_CDX", "1") != "0"


def _cc_get(url: str, timeout: int = 20) -> str:
    if not url.startswith("https://"):
        raise RuntimeError("cdx: non-https index url")
    req = urllib.request.Request(url, headers={"User-Agent": (
        "CivicPathNavigator/0.1 (civic-guidance research; "
        "contact: admin@civicpath.in)")})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(2_000_000).decode("utf-8", "replace")


def _cc_index() -> str:
    """Current crawl collection id (cached per process); "" when unreachable."""
    preset = os.environ.get("CC_INDEX", "").strip()
    if preset:
        return preset
    if _cc_cache.get("name") is not None:
        return _cc_cache["name"]
    name = ""
    try:
        data = json.loads(_cc_get(f"{CC_BASE}/collinfo.json", timeout=15))
        if isinstance(data, list) and data and isinstance(data[0], dict):
            name = str(data[0].get("id") or "")
    except Exception as e:
        from .obs import warn
        warn("cdx", "collinfo lookup failed, CDX lane idle", error=e)
    _cc_cache["name"] = name
    return name


def _parse_cdx(body: str) -> list[str]:
    """Pull URLs out of CDX responses regardless of shape: JSON objects,
    JSON arrays (with or without a field-name header line), or TSV."""
    urls: list[str] = []
    fields: list[str] | None = None
    for line in (body or "").splitlines():
        line = line.strip()
        if not line:
            continue
        u = None
        if line.startswith("{"):
            try:
                u = json.loads(line).get("url")
            except (ValueError, TypeError):
                u = None
        elif line.startswith("["):
            try:
                arr = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(arr, list):
                continue
            if (arr and all(isinstance(x, str) for x in arr)
                    and "urlkey" in arr
                    and not any(str(x).startswith("http") for x in arr)):
                fields = arr  # header line declaring column order
                continue
            if fields and "url" in fields:
                i = fields.index("url")
                u = arr[i] if i < len(arr) else None
            else:
                u = next((x for x in arr
                          if isinstance(x, str) and x.startswith("http")), None)
        else:
            cols = line.split("\t")
            cand = cols[2] if len(cols) > 2 else (cols[0] if cols else "")
            u = cand if cand.startswith("http") else None
        if isinstance(u, str) and u.startswith("http"):
            urls.append(u)
    return urls


def cdx_urls(host: str, limit: int = 60) -> list[str]:
    """Archived URLs for a domain from the Common Crawl index (1 request)."""
    if not _cdx_enabled() or not host:
        return []
    name = _cc_index()
    if not name:
        return []
    query = urllib.parse.urlencode({
        "url": host, "matchType": "domain", "filter": "status:200",
        "collapse": "urlkey", "limit": str(limit), "output": "json"})
    try:
        return _parse_cdx(_cc_get(f"{CC_BASE}/{name}-index?{query}"))
    except Exception as e:
        from .obs import warn
        warn("cdx", "index query failed", host=host, error=e)
        return []


def _safe_split(u: str) -> tuple[str, str]:
    """(hostname, path) — urlparse raises ValueError on malformed input."""
    try:
        p = urllib.parse.urlparse(u)
    except ValueError:
        return ("", "")
    return ((p.hostname or "").lower().rstrip("."), (p.path or ""))


def cdx_task_urls(task: str, seed_urls: list[str], max_urls: int = 5) -> list[str]:
    """Discovery between live search and the catalog: mine the Common Crawl
    index for deep, task-relevant pages (forms, PDFs, apply pages) on the
    catalog's own government domains — zero requests to the live site.

    Returns only https .gov.in/.nic.in URLs whose path carries a task token;
    empty result means 'fall through to the catalog'."""
    if not _cdx_enabled():
        return []
    from .worker import _govish
    tokens = [t for t in re.findall(r"[a-z0-9]{4,}",
                                    (task or "").lower())
              if t not in _CDX_STOP]
    hosts: list[str] = []
    for u in seed_urls or []:
        h, _path = _safe_split(u)
        if h and _govish(h) and h not in hosts:
            hosts.append(h)
    out: list[str] = []
    for host in hosts[:3]:
        for u in cdx_urls(host):
            if not u.startswith("https://"):
                continue
            uhost, path = _safe_split(u)
            if not _govish(uhost):
                continue
            path = path.lower()
            if tokens and not any(t in path for t in tokens):
                continue
            if u in out or u in (seed_urls or []):
                continue
            out.append(u)
            if len(out) >= max_urls:
                return out
    return out
