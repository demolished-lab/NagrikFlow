"""schema.org / JSON-LD structured-fact extraction — zero LLM, zero deps.

Government portals increasingly emit JSON-LD blocks (GovernmentService,
Service, HowTo, FAQPage). Those blocks are machine-readable facts the page
author already structured for machines: name, description, fees (Offer),
supplies (documents), provider, application URL. LLMs paraphrase facts;
this module copies them.

stdlib only (regex + json). extruct (BSD-3) is the roadmap upgrade for
microdata/RDFa portals — see ENHANCED_FEATURES.md P1.
"""
import json
import re

JSONLD_RE = re.compile(
    r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL)

# HowTo/GovernmentService field names we care about, in priority order.
_SERVICE_TYPES = ("governmentservice", "service", "howto", "governmententity",
                  "organization")
_DOC_FIELDS = ("supply", "tool", "requirement", "requiredthing")


def _blocks(page_html: str) -> list:
    """All parsed JSON-LD roots (objects and lists), tolerating junk."""
    out = []
    for raw in JSONLD_RE.findall(page_html or ""):
        blob = raw.strip()
        blob = blob.removeprefix("<!--")
        blob = blob.removesuffix("-->")
        blob = blob.strip()
        for candidate in (blob, blob.rstrip(",")):
            try:
                data = json.loads(candidate)
            except (ValueError, TypeError):
                continue
            out.extend(data if isinstance(data, list) else [data])
            break
    return out


def _walk(node, found: list) -> None:
    """Depth-first collect every dict in the JSON-LD tree (@graph aware)."""
    if isinstance(node, dict):
        found.append(node)
        for v in node.values():
            _walk(v, found)
    elif isinstance(node, list):
        for v in node:
            _walk(v, found)


def _as_text(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return _as_text(value.get("name") or value.get("text")
                        or value.get("value") or "")
    if isinstance(value, list):
        return "; ".join(t for t in (_as_text(v) for v in value) if t)
    return "" if value is None else str(value)


def _type_names(node: dict) -> list[str]:
    t = node.get("@type", "")
    items = t if isinstance(t, list) else [t]
    return [str(x).lower().split("/")[-1] for x in items if x]


def _fee(node: dict) -> tuple[str, str]:
    """(fee_text, currency) from Offer.price / price — 0 means 'free'."""
    offers = node.get("offers")
    pool = offers if isinstance(offers, list) else [offers]
    for o in pool:
        if not isinstance(o, dict):
            continue
        price = o.get("price")
        if price in (None, ""):
            price = o.get("lowPrice")  # NB: price 0 is kept — it means free
        if price in (None, ""):
            continue
        cur = str(o.get("priceCurrency") or "").upper()
        try:
            num = float(price)
        except (TypeError, ValueError):
            return (_as_text(price), cur)
        if num == 0:
            return ("₹0", cur or "INR")
        if cur in ("", "INR"):
            return (f"₹{num:,.0f}" if num == int(num) else f"₹{num}", "INR")
        return (f"{num:,.0f} {cur}" if num == int(num) else f"{num} {cur}", cur)
    return ("", "")


def service_facts(page_html: str, url: str = "") -> dict:
    """Flatten JSON-LD on the page into plain civic facts.

    Returns a stable dict (empty strings when absent) — never raises on
    malformed markup. Only structured claims; nothing is guessed."""
    facts = {"name": "", "description": "", "fee": "", "provider": "",
             "application_url": "", "supplies": "", "type": ""}
    if not page_html:
        return facts
    nodes: list[dict] = []
    for block in _blocks(page_html):
        _walk(block, nodes)

    best: dict = {}
    best_rank = 10 ** 6
    for n in nodes:
        types = _type_names(n)
        if not types:
            continue
        for i, want in enumerate(_SERVICE_TYPES):
            if any(want in t for t in types):
                if i < best_rank and _as_text(n.get("name")):
                    best, best_rank = n, i
                break
    if not best and nodes:
        # no typed node: fall back to the first dict with a name + description
        best = next((n for n in nodes
                     if n.get("name") and n.get("description")), {})

    if best:
        facts["name"] = _as_text(best.get("name"))
        facts["description"] = _as_text(best.get("description"))[:600]
        facts["type"] = ", ".join(_type_names(best))
        fee, _cur = _fee(best)
        facts["fee"] = fee
        provider = best.get("provider") or best.get("author") \
            or best.get("publisher")
        facts["provider"] = _as_text(provider)[:200]
        url_val = best.get("url") or best.get("sameAs") \
            or best.get("mainEntity")
        cand = _as_text(url_val)
        if cand.startswith("http"):
            facts["application_url"] = cand[:500]
        supplies = []
        for f in _DOC_FIELDS:
            val = best.get(f)
            if val:
                supplies.append(_as_text(val))
        facts["supplies"] = "; ".join(s for s in supplies if s)[:400]
    facts["url"] = url
    return facts


def facts_to_step(facts: dict, url: str) -> dict | None:
    """A source-grounded step node from structured facts, or None.

    Used only when both the LLM and the heuristics produced nothing — a
    structured 'this is what the portal says this service is' beats an
    empty map, and every field is copied from the page author's own markup."""
    if not (facts or {}).get("name"):
        return None
    detail_bits = [facts.get("description", ""),
                   f"Fee: {facts['fee']}" if facts.get("fee") else "",
                   f"Provider: {facts['provider']}" if facts.get("provider") else "",
                   f"Documents: {facts['supplies']}" if facts.get("supplies") else ""]
    detail = " · ".join(b for b in detail_bits if b)[:800]
    return {"id": "service", "type": "action",
            "title": facts["name"][:120], "detail": detail,
            "url": url, "link": facts.get("application_url", ""),
            "fee": facts.get("fee", "")}
