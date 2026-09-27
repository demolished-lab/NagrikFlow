"""Runtime pathsec guard for nltk model-artifact APIs (PYSEC-2026-3740).

Advisory: nltk <= 3.10.3 lets caller-controlled paths bypass pathsec in
data.find/load/retrieve via raw file operations (traversal -> arbitrary
file read/write). crawl4ai is the only requirer and passes constant corpus
paths, so it is not reachable today -- but this guard enforces containment
in-process so the vulnerable APIs cannot be abused even if a future call
site forwards external input.

No fixed nltk release exists yet (3.10.3 is latest); keep this guard until
nltk > 3.10.3 ships, then delete this module and its test.
"""
import functools
import os
from urllib.parse import unquote, urlparse

_INSTALLED = False


def _has_traversal(path: str) -> bool:
    return ".." in path.replace("\\", "/").split("/")


def _file_url_to_path(target: str) -> str:
    parsed = urlparse(target)
    path = unquote(parsed.path) if parsed.scheme == "file" else target
    if len(path) > 2 and path[0] == "/" and path[2] == ":":
        path = path[1:]  # file:///C:/... -> C:/...
    return path


def _check(name, data_mod) -> None:
    s = str(name)
    if _has_traversal(s):
        raise ValueError(f"nltk_guard: blocked traversal in resource path: {s!r}")
    is_file_url = s.startswith("file:")
    is_abs = os.path.isabs(s) or (len(s) > 1 and s[1] == ":")
    if not (is_file_url or is_abs):
        return  # relative resource names resolve inside nltk.data.path roots
    target = _file_url_to_path(s) if is_file_url else s
    real = os.path.realpath(target)
    roots = []
    for entry in list(getattr(data_mod, "path", []) or []):
        try:
            roots.append(os.path.realpath(str(entry)))
        except (OSError, ValueError):
            continue
    if not roots:
        raise ValueError("nltk_guard: no nltk_data roots configured")
    if not any(real == r or real.startswith(r + os.sep) for r in roots):
        raise ValueError(f"nltk_guard: resource outside nltk_data roots: {s!r}")


def _wrap(data_mod, fname: str) -> None:
    orig = getattr(data_mod, fname, None)
    if not callable(orig) or getattr(orig, "_civic_guarded", False):
        return

    @functools.wraps(orig)
    def guarded(resource_name, *args, **kwargs):
        _check(resource_name, data_mod)
        return orig(resource_name, *args, **kwargs)

    guarded._civic_guarded = True
    setattr(data_mod, fname, guarded)


def install() -> bool:
    """Idempotent. Returns True when nltk was found and guarded."""
    global _INSTALLED
    if _INSTALLED:
        return True
    _INSTALLED = True
    try:
        import nltk.data as data_mod
    except Exception:
        return False  # nltk absent -> nothing to guard
    _wrap(data_mod, "find")
    _wrap(data_mod, "load")
    _wrap(data_mod, "retrieve")
    return True


def is_installed() -> bool:
    try:
        import nltk.data as data_mod
    except Exception:
        return False
    return bool(getattr(getattr(data_mod, "find", None), "_civic_guarded", False))
