"""Scrape-cascade worker: official gov pages -> verified TaskMap snapshots.

Tier 1 trafilatura (fast/static) -> Tier 2 crawl4ai (JS) ->
Tier 3 obscura stealth (WAF/bot-walled). First success wins.
Then LLM extraction (Ollama -> Bynara) into the civic Step schema;
regex fallback keeps the pipeline working with zero LLM.
Every field keeps source_url + fetched_at. No proof link = dropped.
"""
import re
import subprocess
from datetime import datetime, timezone
from urllib.parse import urlparse

import trafilatura

from . import llm as llmmod

UA = "CivicPathNavigator/0.1 (civic-guidance research; contact: admin@civicpath.in)"
MIN_CHARS = 40  # floor that rejects blocks/CAPTCHAs but keeps small gov pages


def _ok(text: str) -> str:
    if len((text or "").strip()) < MIN_CHARS:
        raise RuntimeError("thin")
    return text


def fetch_tier1(url: str) -> str:
    dl = trafilatura.fetch_url(url, no_ssl=False)
    if not dl:
        raise RuntimeError("tier1 empty")
    text = trafilatura.extract(dl, include_links=True) or ""
    return _ok(text)


def fetch_tier2(url: str) -> str:
    from crawl4ai import AsyncWebCrawler
    import asyncio

    async def _go():
        async with AsyncWebCrawler() as crawler:
            r = await crawler.arun(url=url, word_count_threshold=20)
            return (r.markdown or "")[:20000]
    text = asyncio.run(_go())
    return _ok(text)


def fetch_tier3(url: str) -> str:
    import os
    exe = os.path.expanduser("~/.obscura/obscura.exe")
    out = subprocess.run([exe, "fetch", url, "--dump", "text"],
                         capture_output=True, text=True, timeout=120)
    text = (out.stdout or "")[-20000:]
    return _ok(text)


def cascade_fetch(url: str) -> tuple[str, str]:
    """Return (text, tier_used). Raises if all tiers fail."""
    for name, fn in (("trafilatura", fetch_tier1), ("crawl4ai", fetch_tier2),
                     ("obscura", fetch_tier3)):
        try:
            return fn(url), name
        except Exception:
            continue
    try:
        from . import discover as discovermod
        return discovermod.fetch_text(url), "wigolo"
    except Exception:
        pass
    raise RuntimeError(f"all fetch tiers failed for {url}")


FEE_RE = re.compile(r"(?:fee|fees|charge|cost|Rs\.?|₹)\s*[:\-]?\s*([₹Rs\.\s]*\d[\d,]*)", re.I)
DOC_RE = re.compile(r"\b(Aadhaar|PAN|passport|ration card|birth certificate|address proof|bank (?:statement|passbook)|photograph|Form\s*\d*[A-Z]*)\b", re.I)
URL_RE = re.compile(r"https?://[^\s\]\)\"'<>]+", re.I)
LINK_HINTS = ("form", "apply", "register", "pay", "payment", "download",
              "renew", "certif", "licen", "application", "applyfor")
DOC_LINK_HINTS = ("form", "doc", "download", "certificate", "checklist", "template")


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
    """Best official deep link mentioned in fetched page text (same-host or
    gov domain), preferring URLs whose path matches the given hints."""
    src_host = _url_host(source_url)
    best, best_score = "", -1
    for raw in URL_RE.findall(text or ""):
        cand = raw.rstrip(".,;:'\")")
        host = _url_host(cand)
        if not host or (host != src_host and not _govish(host)):
            continue
        score = sum(2 for hint in hints if hint in cand.lower())
        if host == src_host:
            score += 1
        if score > best_score:
            best, best_score = cand, score
    return best


def heuristic_extract(text: str, url: str) -> list[dict]:
    """Zero-LLM fallback: fees + document mentions + official links -> steps."""
    fees = sorted(set(FEE_RE.findall(text)))[:5]
    docs = sorted(set(m.group(1) for m in DOC_RE.finditer(text)))[:10]
    doc_link = pick_link(text, url, DOC_LINK_HINTS)
    app_link = pick_link(text, url, LINK_HINTS)
    steps = []
    if docs:
        steps.append({"id": "docs", "type": "prereq", "title": "Gather documents",
                      "detail": "Mentioned on source: " + ", ".join(docs),
                      "url": url, "link": doc_link, "fee": ""})
    steps.append({"id": "apply", "type": "action", "title": "Apply on official portal",
                  "detail": ("Fees seen: " + ", ".join(fees) if fees else
                             "See official page for current fee schedule."),
                  "url": url, "link": app_link, "fee": fees[0] if fees else ""})
    return steps


def llm_extract(text: str, url: str, task: str) -> list[dict]:
    prompt = (f"Task: {task}\nSource: {url}\nPage text (truncated):\n{text[:6000]}\n\n"
              "Return JSON list of steps: "
              '[{"id":str,"type":"prereq|action|payment|visit","title":str,'
              '"detail":str,"fee":str,"link":str}]. "link" is the exact application/'
              'form URL from the page text for this step ("" if none). Max 8 steps, '
              'ordered. No prose.')
    try:
        raw, _ = llmmod._chat_raw(prompt)
    except Exception:
        return heuristic_extract(text, url)
    import json
    m = re.search(r"\[.*\]", raw, re.S)
    try:
        steps = json.loads(m.group(0)) if m else []
        for s in steps:
            s["url"] = url
            s["link"] = clean_link(s.get("link", ""), url)
        return steps[:8] if steps else heuristic_extract(text, url)
    except Exception:
        return heuristic_extract(text, url)


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
    except Exception:
        return []
    try:
        m = re.search(r"\[.*\]", raw, re.S)
        pairs = json.loads(m.group(0)) if m else []
        return pairs if isinstance(pairs, list) else []
    except Exception:
        return []


def build_map(task: str, urls: list[str], city: str = "", state: str = "",
              service_type: str = "") -> dict:
    """Fetch each URL via cascade, extract steps, merge into a cross-source
    dependency graph (dedupe + prereq inference + LLM refinement + bridging)."""
    per_source: list[tuple[str, list[dict]]] = []
    sources = []
    for url in urls:
        try:
            text, tier = cascade_fetch(url)
        except Exception as e:
            sources.append({"url": url, "ok": False, "error": str(e)[:120]})
            continue
        steps = llm_extract(text, url, task)
        per_source.append((url, steps))
        sources.append({"url": url, "ok": True, "tier": tier,
                        "fetched_at": datetime.now(timezone.utc).isoformat()})

    nodes, edges, edge_sources = merge_sources(per_source)
    node_ids = {n["id"] for n in nodes}
    cap = max(40, 3 * len(nodes))
    cross_source_edges(nodes, edges, edge_sources)
    bridge_disconnected(edges, edge_sources, nodes, per_source)
    _add_edges(edges, edge_sources, llm_infer_edges(task, nodes),
               "inferred: LLM prerequisite model", node_ids, cap)

    return {"nodes": nodes, "edges": edges, "edge_sources": edge_sources,
            "sources": sources, "city": city, "state": state,
            "service_type": service_type}
