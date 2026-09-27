"""Scrape-cascade worker: official gov pages -> verified TaskMap snapshots.

Tier 1 trafilatura (fast/static) -> Tier 2 crawl4ai (JS) ->
Tier 3 obscura stealth (WAF/bot-walled). First success wins.
Then LLM extraction (Ollama -> Bynara) into the civic Step schema;
regex fallback keeps the pipeline working with zero LLM.
Every field keeps source_url + fetched_at. No proof link = dropped.
"""
import html
import ipaddress
import os
import re
import socket
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

import trafilatura

from . import llm as llmmod
from .obs import warn

UA = "CivicPathNavigator/0.1 (civic-guidance research; contact: admin@civicpath.in)"
MIN_CHARS = 40  # floor that rejects blocks/CAPTCHAs but keeps small gov pages


def _ok(text: str) -> str:
    if len((text or "").strip()) < MIN_CHARS:
        raise RuntimeError("thin")
    return text


def _require_public(url: str) -> None:
    """SSRF entry guard for every fetch tier: http(s) only, never a private/
    loopback/link-local target (DNS failure stays indeterminate and is left
    to the fetch itself; explicit non-public resolution is blocked).

    SSRF_PROBE=0 disables the private-target check only (scheme check stays) —
    an explicit dev/sim opt-out for localhost fixture servers, mirroring
    LINK_PROBE. Default is ON in production."""
    if not (url or "").lower().startswith(("http://", "https://")):
        raise RuntimeError("ssrf: non-http scheme")
    if os.environ.get("SSRF_PROBE", "1") == "0":
        return
    if _probe_target_ok(url) is False:
        raise RuntimeError("ssrf: non-public target")


def guard_chain(url: str) -> str:
    """Follow the redirect chain through the guarded opener, validating EVERY
    hop (public target only), and return the final URL.

    Fetchers that manage their own connections (crawl4ai, obscura, wigolo)
    cannot hook their redirect handling, so they start from this
    chain-validated final URL instead of the raw entry URL. The entry guard
    alone does not stop a 302 to http://169.254.169.254/."""
    _require_public(url)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    opener = urllib.request.build_opener(_GuardedRedirect)
    with opener.open(req, timeout=20) as resp:
        final = resp.geturl() or url
        try:
            resp.read(1)  # drain one byte so the conn can be released
        except Exception:
            pass
    _require_public(final)
    return final


def _fetch_tier1_full(url: str) -> tuple[str, str]:
    """(text, final_url) — final_url is where the redirect chain landed."""
    _require_public(url)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    opener = urllib.request.build_opener(_GuardedRedirect)
    with opener.open(req, timeout=25) as resp:
        data = resp.read(2_000_000)
        charset = resp.headers.get_content_charset() or "utf-8"
        final = resp.geturl() or url
    dl = data.decode(charset, errors="replace")
    text = trafilatura.extract(dl, include_links=True) or ""
    return _ok(text), final


def fetch_tier1(url: str) -> str:
    return _fetch_tier1_full(url)[0]


def _fetch_tier2_full(url: str) -> tuple[str, str]:
    final = guard_chain(url)  # validate the whole redirect chain first
    from crawl4ai import AsyncWebCrawler
    import asyncio

    async def _go():
        async with AsyncWebCrawler() as crawler:
            r = await crawler.arun(url=final, word_count_threshold=20)
            return (r.markdown or "")[:20000]
    text = asyncio.run(_go())
    return _ok(text), final


def fetch_tier2(url: str) -> str:
    return _fetch_tier2_full(url)[0]


def _fetch_tier3_full(url: str) -> tuple[str, str]:
    final = guard_chain(url)  # validate the whole redirect chain first
    import os
    exe = os.path.expanduser("~/.obscura/obscura.exe")
    out = subprocess.run([exe, "fetch", final, "--dump", "text"],
                         capture_output=True, text=True, timeout=120)
    text = (out.stdout or "")[-20000:]
    return _ok(text), final


def fetch_tier3(url: str) -> str:
    return _fetch_tier3_full(url)[0]


def _fetch_scrapling_full(url: str) -> tuple[str, str]:
    """Extra stealth tier: Evonext/D4Vinci Scrapling through the omniharness
    bridge (installed in the base Python, not this venv). Subprocess + env
    kill-switch (CIVIC_EXTRA_TIERS=0) so a missing bridge just skips."""
    final = guard_chain(url)
    import json as _json
    import shutil as _shutil
    bridge = os.path.join(os.environ.get("OMNIHARNESS_DIR",
                                          r"C:\Users\Raja\omniharness"),
                          "scrapling_bridge.py")
    if not os.path.isfile(bridge):
        raise RuntimeError("scrapling bridge not present")
    py = os.environ.get("SCRAPLING_PY") or _shutil.which("python") or ""
    if not py:
        raise RuntimeError("no python interpreter for scrapling")
    out = subprocess.run([py, bridge, "--url", final],
                         capture_output=True, text=True, timeout=60)
    line = (out.stdout or "").strip().splitlines()
    if out.returncode != 0 or not line:
        raise RuntimeError(f"scrapling failed: "
                           f"{(out.stderr or out.stdout or '')[:120]}")
    data = _json.loads(line[-1])
    if not data.get("ok"):
        raise RuntimeError(f"scrapling status {data.get('status')}")
    return _ok((data.get("text") or "")[:20000]), final


def _fetch_jina_full(url: str) -> tuple[str, str]:
    """Reader tier: r.jina.ai renders JS/bot-walled pages into clean text."""
    final = guard_chain(url)
    req = urllib.request.Request(
        "https://r.jina.ai/" + final,
        headers={"User-Agent": UA, "Accept": "text/plain"})
    opener = urllib.request.build_opener(_GuardedRedirect)
    with opener.open(req, timeout=25) as resp:
        data = resp.read(2_000_000)
        charset = resp.headers.get_content_charset() or "utf-8"
    return _ok(data.decode(charset, errors="replace")[:20000]), final


def cascade_fetch_full(url: str) -> tuple[str, str, str]:
    """Return (text, tier_used, final_url_after_redirects).

    final_url is where the guarded redirect chain actually landed — the
    packet artifact links citizens to that, not to a 302-hop entry URL."""
    _require_public(url)
    tiers = [("trafilatura", _fetch_tier1_full),
             ("crawl4ai", _fetch_tier2_full),
             ("obscura", _fetch_tier3_full)]
    if os.environ.get("CIVIC_EXTRA_TIERS", "1") != "0":
        tiers += [("scrapling", _fetch_scrapling_full),
                  ("jina", _fetch_jina_full)]
    tier_errors = []
    for name, fn in tiers:
        try:
            text, final = fn(url)
            return text, name, final
        except Exception as e:
            tier_errors.append(f"{name}: {str(e)[:80]}")
            continue
    try:
        from . import discover as discovermod
        text, final = discovermod.fetch_text(url, return_final=True)
        return text, "wigolo", final
    except Exception as e:
        tier_errors.append(f"wigolo: {str(e)[:80]}")
    warn("fetch", "all fetch tiers failed for source", url=url,
         errors=" | ".join(tier_errors))
    raise RuntimeError(f"all fetch tiers failed for {url}"
                       f" ({' | '.join(tier_errors)})")


def cascade_fetch(url: str) -> tuple[str, str]:
    """Return (text, tier_used). Raises if all tiers fail."""
    text, tier, _final = cascade_fetch_full(url)
    return text, tier


FEE_RE = re.compile(r"(?:fee|fees|charge|cost|Rs\.?|₹)\s*[:\-]?\s*([₹Rs\.\s]*\d[\d,]*)", re.I)
DOC_RE = re.compile(r"\b(Aadhaar|PAN|passport|ration card|birth certificate|address proof|bank (?:statement|passbook)|photograph|Form\s*\d*[A-Z]*)\b", re.I)
URL_RE = re.compile(r"https?://[^\s\]\)\"'<>]+", re.I)
LINK_HINTS = ("form", "apply", "register", "registration", "pay", "payment",
              "download", "renew", "certif", "licen", "application", "applyfor")
DOC_LINK_HINTS = ("form", "doc", "download", "certificate", "checklist", "template")
BAD_LINK_HINTS = ("grievance", "complaint", "assist", "feedback", "contact",
                  "helpdesk", "helpline", "faq", "charter", "enquiry",
                  "inquiry", "ticket", "support", "suggestion", "champions")
# Guide/official-document links (guidelines, handbooks, PDFs, circulars).
# Narrower blocklist than BAD_LINK_HINTS: a citizen *should* get the citizen
# charter / FAQ as reading material — just never as an application link.
GUIDE_HINTS = ("guideline", "guidelines", "handbook", "manual", "brochure",
               "circular", "instruction", "directory", "checklist", "template",
               ".pdf", "form", "download", "citizen", "charter", "scheme",
               "rules", "act", "leaflet", "document")
GUIDE_BAD = ("grievance", "complaint", "feedback", "enquiry", "inquiry",
             "suggestion", "helpline", "helpdesk", "ticket", "champions")
NO_DOCS_RE = re.compile(
    r"(?:\bno\b[^.]{0,40}\b(?:documents?|proof|copies|papers)\b"
    r"|\bpaperless\b"
    r"|\bwithout\b[^.]{0,30}\b(?:documents?|proof)\b"
    r"|\bnothing to (?:upload|submit)\b"
    r"|\bnot require\b[^.]{0,30}\b(?:documents?|proof)\b)",
    re.I)

# Page states the service is free ("Registration is Free of Cost", "No fee").
FREE_RE = re.compile(
    r"(?:free\s+of\s+(?:cost|charge)"
    r"|\bis\s+(?:entirely\s+|completely\s+|totally\s+)?free\b"
    r"|\b(?:registration|application)\s+is\s+free\b"
    r"|\bno\s+(?:fee|fees|charge|cost|payment)\b"
    r"|\b(?:fee|charge|cost)\s*[:\-]?\s*(?:rs\.?|₹)?\s*0(?:\.00)?\b"
    r"|₹\s*0\b)",
    re.I)

# A bare document mention (a word in prose) is not a documents-to-gather
# requirement; require a requirement verb near the mention.
REQ_DOC_RE = re.compile(
    r"\b(?:require[ds]?|must|need(?:ed)?|bring|carry|present|produce|upload|"
    r"attach|submit|enclose)\b", re.I)


def _url_host(u: str) -> str:
    try:
        return (urlparse(u or "").hostname or "").lower().rstrip(".")
    except Exception:
        return ""


def _govish(host: str) -> bool:
    return bool(host) and (host.endswith(".gov.in") or host.endswith(".nic.in")
                           or host in {"gov.in", "nic.in"})


def clean_link(link: str, source_url: str) -> str:
    """Accept a per-step deep link only if it is http(s) AND on the source's
    own host or an official .gov.in/.nic.in host. Blocks LLM-hallucinated
    foreign URLs (phishing risk for citizens)."""
    link = (link or "").strip().rstrip(".,;:'\")")
    if not link.lower().startswith(("http://", "https://")):
        return ""
    host = _url_host(link)
    if not host:
        return ""
    if host == _url_host(source_url) or _govish(host):
        return link
    return ""


def pick_link(text: str, source_url: str, hints=LINK_HINTS) -> str:
    """Best application deep link from fetched page text.

    Same-host beats cross-host; hints match path+query only (not hostname);
    help/complaint/grievance pages are never eligible (they out-score real
    forms on raw substrings); cross-host needs positive path evidence."""
    src_host = _url_host(source_url)
    best, best_score = "", -999
    for raw in URL_RE.findall(text or ""):
        cand = raw.rstrip(".,;:'\")")
        host = _url_host(cand)
        if not host or (host != src_host and not _govish(host)):
            continue
        low = cand.lower()
        if any(bad in low for bad in BAD_LINK_HINTS):
            continue
        try:
            p = urlparse(cand)
            pathq = f"{p.path or ''}?{p.query or ''}".lower()
        except Exception:
            pathq = low
        score = 0
        for hint in hints:
            if hint in pathq:
                score += 2
        if host == src_host:
            score += 3
        elif not pathq.strip("/?"):
            score -= 2  # cross-domain bare root: weak evidence
        else:
            score -= 1  # cross-domain must earn it with path hints
        if score > best_score:
            best, best_score = cand, score
    return best if best_score > 0 else ""


def page_has_link(link: str, text: str) -> bool:
    """Source-grounding: the exact deep link must literally appear in the
    fetched page text (an LLM cannot invent a URL that was never there)."""
    if not link or not text:
        return False
    norm = link.rstrip(".,;:'\")").rstrip("/")
    for raw in URL_RE.findall(html.unescape(text)):
        if raw.rstrip(".,;:'\")").rstrip("/") == norm:
            return True
    return False


def probe_link(link: str, timeout: float = 4.0):
    """Reachability probe: True = server answers, False = provably dead
    (404/410) or unsafe target, None = indeterminate (DNS/timeout/WAF)."""
    if os.environ.get("LINK_PROBE", "1") == "0":
        return None
    ok = _probe_target_ok(link)
    if ok is False:
        return False  # private/internal address: never fetched
    if ok is None:
        return None  # DNS failure -> indeterminate, link kept
    opener = urllib.request.build_opener(_GuardedRedirect)
    req = urllib.request.Request(link, method="HEAD", headers={"User-Agent": UA})
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status not in (404, 410)
    except _BadRedirect:
        return False
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return False
        return True  # server answered (incl. 403/405 bot-walls, 5xx)
    except Exception:
        return None


def _probe_target_ok(url: str):
    """True = host resolves to public IPs only, False = private/loopback/
    link-local target (blocked, never fetched), None = DNS failure."""
    host = urlparse(url).hostname
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except OSError:
        return None
    if not infos:
        return None
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if not ip.is_global:
            return False
    return True


class _BadRedirect(Exception):
    """Redirect target failed the public-address guard."""


class _GuardedRedirect(urllib.request.HTTPRedirectHandler):
    """Follow redirects only to public addresses (SSRF guard: a gov page
    must not be able to bounce the probe onto 169.254.169.254/RFC1918)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if os.environ.get("SSRF_PROBE", "1") != "0" \
                and _probe_target_ok(newurl) is not True:
            raise _BadRedirect(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def verify_links(nodes: list[dict]) -> None:
    """Best-effort reachability sweep: drop provably dead deep links (capped)."""
    probed = 0
    for n in nodes:
        link = n.get("link")
        if not link or probed >= 10:
            continue
        probed += 1
        if probe_link(link) is False:
            n["link"] = ""


def extract_guides(text: str, source_url: str, limit: int = 5) -> list[dict]:
    """Official reading material linked from a fetched source: guidelines,
    handbooks, PDFs, circulars, citizen charters, templates.

    Host-gated like pick_link (source host or .gov.in/.nic.in), never a
    grievance/helpdesk page. Returns [{url, title}] sorted by path hint
    strength, capped at `limit`."""
    src_host = _url_host(source_url)
    scored: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    for raw in URL_RE.findall(text or ""):
        cand = raw.rstrip(".,;:'\")")
        if cand in seen:
            continue
        host = _url_host(cand)
        if not host or (host != src_host and not _govish(host)):
            continue
        low = cand.lower()
        if any(bad in low for bad in GUIDE_BAD):
            continue
        score = sum(2 for hint in GUIDE_HINTS if hint in low)
        if score == 0:
            continue
        if host == src_host:
            score += 1
        seen.add(cand)
        name = unquote(urlparse(cand).path.rsplit("/", 1)[-1]) or host
        title = re.sub(r"[-_]+", " ", name).strip() or cand
        scored.append((score, cand, title))
    scored.sort(key=lambda item: -item[0])
    return [{"url": u, "title": t} for _s, u, t in scored[:limit]]


def heuristic_extract(text: str, url: str) -> list[dict]:
    """Zero-LLM fallback: fees + document mentions + official links -> steps."""
    text = text or ""
    fees = sorted(set(FEE_RE.findall(text)))[:5]
    docs = sorted(set(m.group(1) for m in DOC_RE.finditer(text)))[:10]
    # "paperless / no documents to upload" pages (e.g. Udyam) must not get a
    # fabricated document-gathering step just because PAN is mentioned in prose
    if docs and NO_DOCS_RE.search(text):
        docs = []
    # even on non-paperless pages, a doc token needs a requirement verb nearby
    # ("PAN is accepted as proof" != "bring your PAN")
    docs = [m.group(1) for m in DOC_RE.finditer(text)
            if m.group(1) in docs
            and REQ_DOC_RE.search(text[max(0, m.start() - 60):m.end() + 60])]
    docs = sorted(set(docs))[:10]
    doc_link = pick_link(text, url, DOC_LINK_HINTS)
    app_link = pick_link(text, url, LINK_HINTS)
    steps = []
    if docs:
        steps.append({"id": "docs", "type": "prereq", "title": "Gather documents",
                      "detail": "Mentioned on source: " + ", ".join(docs),
                      "url": url, "link": doc_link, "fee": ""})
    # fee: quote a figure the page states; a page that says "free" shows ₹0;
    # a silent page must not invent or promise a fee schedule
    free = bool(FREE_RE.search(text))
    fee = fees[0] if fees else ("₹0" if free else "")
    if fees:
        detail = "Fees seen: " + ", ".join(fees)
    elif free:
        detail = "Free of cost (stated on the official page)."
    else:
        detail = "See official page for current fee schedule."
    if NO_DOCS_RE.search(text):
        detail += " Paperless — no documents to upload (stated on the official page)."
    steps.append({"id": "apply", "type": "action", "title": "Apply on official portal",
                  "detail": detail,
                  "url": url,
                  # no deep link on the page? the fetched official source IS
                  # the portal entry point — never leave the CTA empty
                  "link": app_link or clean_link(url, url),
                  "fee": fee})
    return steps


def _llm_extract_full(text: str, url: str, task: str) -> tuple[list[dict], str, str]:
    """Return (steps, lane, error). lane = 'llm' | 'heuristic'; error explains
    any fallback so it can be stored in the map and shown to the user —
    a degraded extraction is never silent."""
    prompt = (f"Task: {task}\nSource: {url}\nPage text (truncated):\n{text[:6000]}\n\n"
              "Return JSON list of steps: "
              '[{"id":str,"type":"prereq|action|payment|visit","title":str,'
              '"detail":str,"fee":str,"link":str}]. "link" is the exact application/'
              'form URL from the page text for this step ("" if none). Max 8 steps, '
              'ordered. No prose.')
    try:
        raw, _ = llmmod._chat_raw(prompt, max_tokens=2000)
    except Exception as e:
        reason = f"LLM unavailable: {str(e)[:160]}"
        warn("extract", "LLM extraction failed, rules fallback", url=url, error=e)
        return heuristic_extract(text, url), "heuristic", reason
    import json
    m = re.search(r"\[.*\]", raw, re.S)
    try:
        steps = json.loads(m.group(0)) if m else []
        if not isinstance(steps, list) or not steps:
            raise ValueError("LLM reply contained no step list")
        for s in steps:
            s["url"] = url
            s["link"] = clean_link(s.get("link", ""), url)
            if s["link"] and not page_has_link(s["link"], text):
                s["link"] = ""  # absent from the fetched page -> hallucinated
        return steps[:8], "llm", ""
    except Exception as e:
        reason = f"unparseable LLM reply ({str(e)[:100]}): {raw[:160]}"
        warn("extract", "unparseable LLM reply, rules fallback",
             url=url, error=e, raw=raw[:200])
        return heuristic_extract(text, url), "heuristic", reason


def llm_extract(text: str, url: str, task: str) -> list[dict]:
    return _llm_extract_full(text, url, task)[0]


# ---------------- Graph assembly: merge + cross-source dependency inference ----

STOPWORDS = frozenset(
    "the and for with from that this your you are was has have been will can may "
    "not but any all who whom our their what when where which how why get got apply "
    "application step steps must should need needs required require requires online "
    "portal site page form forms office visit procedure process following follow "
    "please ensure ensure's onto into over under before after during within via".split())

PREREQ_HINTS = frozenset(
    "document documents proof verify verification obtain gather eligibility "
    "certificate registration register identity address proof".split())


def _norm_title(title: str) -> str:
    return re.sub(r"\W+", " ", (title or "").lower()).strip()


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(w) > 2 and w not in STOPWORDS}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _edge_key(a: str, b: str) -> str:
    return f"{a}|{b}"  # JSON-safe (tuple keys are not serializable)


def _would_cycle(edges: list, a: str, b: str) -> bool:
    """True if adding a->b closes a cycle (path b ~> a already exists)."""
    adj: dict[str, list[str]] = {}
    for s, t in edges:
        adj.setdefault(s, []).append(t)
    seen, stack = {b}, [b]
    while stack:
        cur = stack.pop()
        if cur == a:
            return True
        for nxt in adj.get(cur, ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return False


def _add_edges(edges: list, edge_sources: dict, new_edges, provenance: str,
               node_ids: set, cap: int) -> int:
    """Append validated, acyclic edges. Returns count accepted."""
    added = 0
    for pair in new_edges:
        if len(edges) >= cap:
            break
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        a, b = str(pair[0]), str(pair[1])
        if a == b or a not in node_ids or b not in node_ids:
            continue
        if [a, b] in edges:
            continue
        if _would_cycle(edges, a, b):
            continue
        edges.append([a, b])
        edge_sources[_edge_key(a, b)] = provenance
        added += 1
    return added


def merge_sources(per_source: list[tuple[str, list[dict]]]) -> tuple[list[dict], list, dict]:
    """Merge duplicate steps across sources (title-token overlap) and chain each
    source's internal order into sequential edges. Returns (nodes, edges,
    edge_sources); edge provenance keys are JSON-safe strings ("a|b")."""
    nodes: list[dict] = []
    edge_sources: dict = {}
    resolved_all: list[tuple[str, list[str]]] = []  # (url, resolved node ids)
    for url, steps in per_source:
        resolved: list[str] = []
        for s in steps:
            title = str(s.get("title") or s.get("id") or "step")
            ttoks = _tokens(title)
            sid = re.sub(r"\W+", "-", s.get("id", title)).strip("-").lower()[:40] or "step"
            match_id = None
            for existing in nodes:
                if _jaccard(_tokens(existing["title"]), ttoks) >= 0.6 or \
                        _norm_title(existing["title"]) == _norm_title(title):
                    match_id = existing["id"]
                    break
            if match_id is None:
                base, n = sid, 2
                while any(node["id"] == base for node in nodes):
                    base, n = f"{sid}-{n}", n + 1
                match_id = base
                nodes.append({"id": match_id, "type": s.get("type", "action"),
                              "title": title, "detail": s.get("detail", ""),
                              "url": url, "link": s.get("link", ""),
                              "fee": s.get("fee", "")})
            else:
                node = next(nd for nd in nodes if nd["id"] == match_id)
                if not node.get("detail") and s.get("detail"):
                    node["detail"] = s["detail"]
                if not node.get("fee") and s.get("fee"):
                    node["fee"] = s["fee"]
                if not node.get("link") and s.get("link"):
                    node["link"] = s["link"]
            resolved.append(match_id)
        resolved_all.append((url, resolved))
    edges: list = []
    for url, ids in resolved_all:
        for a, b in zip(ids, ids[1:]):
            if a != b and [a, b] not in edges:
                edges.append([a, b])
                edge_sources[_edge_key(a, b)] = url
    return nodes, edges, edge_sources


def cross_source_edges(nodes: list[dict], edges: list, edge_sources: dict) -> None:
    """Prerequisite nodes -> dependent nodes in OTHER sources via title/detail
    token overlap (e.g. 'Gather PAN card' -> 'Register for GST')."""
    node_ids = {n["id"] for n in nodes}
    cap = max(40, 3 * len(nodes))
    candidates = []
    for consumer in nodes:
        ctoks = _tokens(f"{consumer['title']} {consumer.get('detail', '')}")
        if len(ctoks) < 2:
            continue
        c_index = nodes.index(consumer)
        for src in nodes:
            if src["id"] == consumer["id"]:
                continue
            if src["url"] == consumer["url"]:
                continue  # same-source order already captured
            src_toks = _tokens(src["title"])
            if not src_toks:
                continue
            is_prereq = src["type"] == "prereq" or bool(src_toks & PREREQ_HINTS)
            if not is_prereq:
                continue
            shared = src_toks & ctoks
            if not shared:
                continue
            if len(shared) >= 2 or max(len(t) for t in shared) >= 5:
                # direction: prerequisite earlier in assembly order
                if nodes.index(src) < c_index or src["type"] == "prereq":
                    candidates.append((src["id"], consumer["id"], src["url"]))
    # dedupe keeping first provenance
    seen = set()
    fresh = []
    for a, b, prov in candidates:
        if (a, b) not in seen:
            seen.add((a, b))
            fresh.append(((a, b), prov))
    remaining = cap - len(edges)
    for (a, b), prov in fresh[:max(0, remaining)]:
        _add_edges(edges, edge_sources, [(a, b)], f"inferred: prerequisite match ({prov})",
                   node_ids, cap)


def bridge_disconnected(edges: list, edge_sources: dict, nodes: list[dict],
                        per_source: list[tuple[str, list[dict]]]) -> None:
    """Connect source components that share no dependency path, so a multi-source
    procedure renders as one DAG. Provenance recorded as source-order inference."""
    node_ids = {n["id"] for n in nodes}
    cap = max(40, 3 * len(nodes))
    groups = []
    for url, _steps in per_source:
        ids = [n["id"] for n in nodes if n["url"] == url]
        if ids:
            groups.append(ids)
    if len(groups) < 2:
        return

    def reaches_any(sources: list[str], targets: set[str]) -> bool:
        adj: dict[str, list[str]] = {}
        for s, t in edges:
            adj.setdefault(s, []).append(t)
        seen, stack = set(sources), list(sources)
        while stack:
            cur = stack.pop()
            if cur in targets:
                return True
            for nxt in adj.get(cur, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return False

    connected = set(groups[0])
    for group in groups[1:]:
        gset = set(group)
        if not (reaches_any(group, connected) or reaches_any(list(connected), gset)):
            # no path either direction -> bridge terminal of connected -> entry of group
            out_nodes = {s for s, _ in edges}
            in_nodes = {t for _, t in edges}
            tail = next((n for n in reversed(list(connected)) if n not in out_nodes),
                        None)
            head = next((n for n in group if n not in in_nodes), group[0])
            if tail and head:
                _add_edges(edges, edge_sources, [(tail, head)],
                           "inferred: source-order bridge (no shared prerequisite)",
                           node_ids, cap)
        connected |= gset


def llm_infer_edges(task: str, nodes: list[dict]) -> list[list[str]]:
    """Ask the LLM for real prerequisite edges across ALL sources. Never raises;
    validation (ids, dedupe, acyclicity) happens in _add_edges."""
    if len(nodes) < 3:
        return []
    listing = "\n".join(f'- {n["id"]}: {n["title"]} ({n["type"]})' for n in nodes[:40])
    prompt = (f"Civic task: {task}\nSteps from multiple government sources:\n{listing}\n\n"
              "Return a JSON array of [before_id, after_id] pairs where 'before' must be "
              "completed before 'after'. Only genuine prerequisite dependencies between "
              "these exact ids. Max 10 pairs. No prose.")
    import json
    try:
        raw, _ = llmmod._chat_raw(prompt)
    except Exception as e:
        warn("edges", "LLM edge inference unavailable, no cross-source edges",
             error=e)
        return []
    try:
        m = re.search(r"\[.*\]", raw, re.S)
        pairs = json.loads(m.group(0)) if m else []
        if not isinstance(pairs, list):
            raise ValueError("reply was not a JSON array")
        return pairs
    except Exception as e:
        warn("edges", "unparseable edge reply", error=e, raw=raw[:200])
        return []


def build_map(task: str, urls: list[str], city: str = "", state: str = "",
              service_type: str = "") -> dict:
    """Fetch each URL via cascade, extract steps, merge into a cross-source
    dependency graph (dedupe + prereq inference + LLM refinement + bridging)."""
    per_source: list[tuple[str, list[dict]]] = []
    sources = []
    for url in urls:
        try:
            text, tier, final = cascade_fetch_full(url)
        except Exception as e:
            sources.append({"url": url, "ok": False, "error": str(e)[:200]})
            continue
        steps, lane, llm_error = _llm_extract_full(text, url, task)
        per_source.append((url, steps))
        entry = {"url": url, "ok": True, "tier": tier,
                 "final_url": final,
                 "guides": extract_guides(text, final or url),
                 "extract": lane,
                 "fetched_at": datetime.now(timezone.utc).isoformat()}
        if llm_error:
            entry["llm_error"] = llm_error
        sources.append(entry)

    nodes, edges, edge_sources = merge_sources(per_source)
    node_ids = {n["id"] for n in nodes}
    cap = max(40, 3 * len(nodes))
    cross_source_edges(nodes, edges, edge_sources)
    bridge_disconnected(edges, edge_sources, nodes, per_source)
    _add_edges(edges, edge_sources, llm_infer_edges(task, nodes),
               "inferred: LLM prerequisite model", node_ids, cap)

    verify_links(nodes)

    return {"nodes": nodes, "edges": edges, "edge_sources": edge_sources,
            "sources": sources, "city": city, "state": state,
            "service_type": service_type}
