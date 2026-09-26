"""LLM lane: Bynara cloud router FIRST, local Ollama as fallback.

Bynara free-tier five, each with a job (role routing):
- nemotron-3-ultra-free ...... strongest free -> structured extraction
- nemotron-3-super-free ...... second opinion / extraction backup
- mimo-v2.6-flash-free ....... fast phrasing (dashboard lines)
- muse-spark-1.3-contributor-free .. plain-words briefs/summaries
- ling-3.0-flash-fin-free .... finance-tuned -> fee/cost parsing

Ollama (local, zero-cost, private) is the fallback when the router
is unreachable — and the primary when OFFLINE_ONLY=1.
LLM only PHRASES/EXTRACTS — decisions stay in deterministic rules.
Prompts carry vault *labels*, never raw document numbers.
"""
import os

import httpx

OFFLINE_ONLY = os.environ.get("OFFLINE_ONLY", "") == "1"

# role -> ordered free-model preference (probed live 2026-09-26:
# ultra/super/lightning/ling-fin reachable; mimo + muse-spark 403 on this key)
ROLES = {
    "extract": ["nemotron-3-ultra-free", "nemotron-3-super-free",
                "nemotron-3.5-lightning-free"],
    "phrase": ["nemotron-3.5-lightning-free", "nemotron-3-super-free",
               "nemotron-3-ultra-free"],
    "brief": ["nemotron-3-super-free", "nemotron-3-ultra-free",
              "nemotron-3.5-lightning-free"],
    "fees": ["ling-3.0-flash-fin-free", "nemotron-3-ultra-free",
             "nemotron-3-super-free"],
}

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "openbmb/minicpm5:latest")
BYNARA_KEY = os.environ.get("BYNARA_API_KEY", "")
BYNARA_BASE = os.environ.get("BYNARA_BASE_URL", "https://router.bynara.id/v1")


def _chat(base: str, model: str, prompt: str, key: str = "",
          temperature: float = 0.2, max_tokens: int = 400) -> str:
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    r = httpx.post(f"{base}/chat/completions",
                   headers=headers,
                   json={"model": model, "temperature": temperature,
                         "max_tokens": max_tokens,
                         "messages": [{"role": "user", "content": prompt}]},
                   timeout=90)
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"].strip()
    if not text:
        raise RuntimeError(f"empty reply from {model}")
    return text


def complete(prompt: str, role: str = "extract") -> tuple[str, str]:
    """Return (text, via). Bynara role-chain first, Ollama fallback. Raises if none."""
    if not OFFLINE_ONLY and BYNARA_KEY:
        for model in ROLES.get(role, ROLES["extract"]):
            try:
                return _chat(BYNARA_BASE, model, prompt, BYNARA_KEY), f"bynara/{model}"
            except Exception:
                continue
    try:
        return _chat(f"{OLLAMA_BASE}/v1", OLLAMA_MODEL, prompt), f"ollama/{OLLAMA_MODEL}"
    except Exception as e:
        raise RuntimeError(f"no LLM reachable (bynara + ollama): {e}")


def _chat_raw(prompt: str) -> tuple[str, str]:
    return complete(prompt, role="extract")


def phrase_dashboard(board: dict) -> tuple[str, str]:
    """Plain-words 3-line brief. Template fallback — never raises."""
    have = ", ".join(board.get("have", [])) or "no verified documents yet"
    nxt = board.get("next_easiest", [])
    nxt_txt = "; ".join(f"{n.get('get')} ({n.get('effort')})" for n in nxt) or "nothing pending"
    prompt = (f"You are a civic guide. Citizen holds: {have}. "
              f"Easiest next steps: {nxt_txt}. In 3 short lines (plain words, "
              f"no jargon): celebrate what they have, name the single easiest "
              f"next win with effort, warn about official-site verification.")
    try:
        return complete(prompt, role="brief")
    except Exception:
        return (f"You hold: {have}. Easiest next win: {nxt_txt}. "
                "Always verify on the official .gov site before applying."), "template"
