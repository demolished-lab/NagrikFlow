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
    raise RuntimeError(f"all fetch tiers failed for {url}")


FEE_RE = re.compile(r"(?:fee|fees|charge|cost|Rs\.?|₹)\s*[:\-]?\s*([₹Rs\.\s]*\d[\d,]*)", re.I)
DOC_RE = re.compile(r"\b(Aadhaar|PAN|passport|ration card|birth certificate|address proof|bank (?:statement|passbook)|photograph|Form\s*\d*[A-Z]*)\b", re.I)


def heuristic_extract(text: str, url: str) -> list[dict]:
    """Zero-LLM fallback: fees + document mentions -> candidate steps."""
    fees = sorted(set(FEE_RE.findall(text)))[:5]
    docs = sorted(set(m.group(1) for m in DOC_RE.finditer(text)))[:10]
    steps = []
    if docs:
        steps.append({"id": "docs", "type": "prereq", "title": "Gather documents",
                      "detail": "Mentioned on source: " + ", ".join(docs),
                      "url": url, "fee": ""})
    steps.append({"id": "apply", "type": "action", "title": "Apply on official portal",
                  "detail": ("Fees seen: " + ", ".join(fees) if fees else
                             "See official page for current fee schedule."),
                  "url": url, "fee": fees[0] if fees else ""})
    return steps


def llm_extract(text: str, url: str, task: str) -> list[dict]:
    prompt = (f"Task: {task}\nSource: {url}\nPage text (truncated):\n{text[:6000]}\n\n"
              "Return JSON list of steps: "
              '[{"id":str,"type":"prereq|action|payment|visit","title":str,'
              '"detail":str,"fee":str}]. Max 8 steps, ordered. No prose.')
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
        return steps[:8] if steps else heuristic_extract(text, url)
    except Exception:
        return heuristic_extract(text, url)


def build_map(task: str, urls: list[str]) -> dict:
    """Fetch each URL via cascade, extract steps, merge into node-link graph."""
    nodes, edges, sources = [], [], []
    seen = set()
    for url in urls:
        try:
            text, tier = cascade_fetch(url)
        except Exception as e:
            sources.append({"url": url, "ok": False, "error": str(e)[:120]})
            continue
        steps = llm_extract(text, url, task)
        prev = None
        for s in steps:
            sid = re.sub(r"\W+", "-", s.get("id", s.get("title", ""))).strip("-").lower()[:40]
            if sid not in seen:
                seen.add(sid)
                nodes.append({"id": sid, "type": s.get("type", "action"),
                              "title": s.get("title", sid), "detail": s.get("detail", ""),
                              "url": url, "fee": s.get("fee", "")})
            if prev and prev != sid:
                e = [prev, sid]
                if e not in edges:
                    edges.append(e)
            prev = sid
        sources.append({"url": url, "ok": True, "tier": tier,
                        "fetched_at": datetime.now(timezone.utc).isoformat()})
    return {"nodes": nodes, "edges": edges, "sources": sources}
