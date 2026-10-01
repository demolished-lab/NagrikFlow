"""LLM health check and configuration utility.

Provides:
- health_check(): Returns status of all LLM backends (Bynara, Ollama)
- get_active_llm(): Returns the currently configured primary LLM
- llm_available(): Boolean check for any working LLM backend
"""
import os
from datetime import datetime, timezone

import httpx

BYNARA_API_KEY = os.environ.get("BYNARA_API_KEY", "").strip()
BYNARA_BASE_URL = os.environ.get("BYNARA_BASE_URL", "https://router.bynara.id/v1")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "openbmb/minicpm5:latest")
OFFLINE_ONLY = os.environ.get("OFFLINE_ONLY", "0") == "1"


async def health_check() -> dict:
    """Check health of all configured LLM backends.
    
    Returns:
        Dict with status of each backend and overall availability.
    """
    result = {
        "bynara": {"configured": bool(BYNARA_API_KEY), "status": "unknown"},
        "ollama": {"configured": True, "status": "unknown"},
        "overall": "unknown",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    # Check Bynara
    if BYNARA_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{BYNARA_BASE_URL}/models",
                    headers={"Authorization": f"Bearer {BYNARA_API_KEY}"}
                )
                if resp.status_code == 200:
                    result["bynara"]["status"] = "ok"
                else:
                    result["bynara"]["status"] = f"error_{resp.status_code}"
        except Exception as e:
            result["bynara"]["status"] = f"error_{type(e).__name__}"
    
    # Check Ollama
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                result["ollama"]["status"] = "ok"
                models = resp.json().get("models", [])
                result["ollama"]["model_count"] = len(models)
            else:
                result["ollama"]["status"] = f"error_{resp.status_code}"
    except Exception as e:
        result["ollama"]["status"] = f"error_{type(e).__name__}"
    
    # Determine overall status
    statuses = [result["bynara"]["status"], result["ollama"]["status"]]
    if any(s == "ok" for s in statuses):
        result["overall"] = "ok"
    elif OFFLINE_ONLY:
        result["overall"] = "offline_only_ollama_down"
    else:
        result["overall"] = "no_llm_available"
    
    return result


def get_primary_llm() -> str:
    """Return the primary LLM to use based on configuration.
    
    Returns:
        String identifier for the primary LLM backend.
    """
    if OFFLINE_ONLY:
        return "ollama"
    if BYNARA_API_KEY:
        return "bynara"
    return "ollama"


def llm_available() -> bool:
    """Quick boolean check for any LLM backend."""
    return bool(BYNARA_API_KEY) or not OFFLINE_ONLY
