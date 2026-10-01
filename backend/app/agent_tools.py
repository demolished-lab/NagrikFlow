"""Available tools for the mini-Hermes agent.

Tools are callable by the LLM reasoning loop AND via REST endpoints
(GET /agent/tools, POST /agent/tool/<name>) so the frontend dashboard
can invoke them too.
"""
import ast
import os
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PYTHON = os.path.join(sys.prefix, "Scripts", "python.exe") if sys.platform == "win32" else "python3"


# ---- tool registry --------------------------------------------------------

TOOLS: dict[str, dict] = {}


def _tool(fn):
    """Decorate a function to register it as an agent tool."""
    TOOLS[fn.__name__] = {
        "name": fn.__name__,
        "description": getattr(fn, "__doc__", "").strip(),
        "params": getattr(fn, "__params__", {}),
        "_fn": fn,
    }
    return fn


# ---- read-file -------------------------------------------------------------

@_tool
def read_file(path: str, offset: int = 1, limit: int = 500) -> dict:
    """Read a file with line numbers. Use for inspecting code before patching."""
    p = BASE / path.lstrip("/")
    try:
        with open(p, "r", encoding="utf-8") as f:
            lines = f.readlines()
        start = max(0, offset - 1)
        window = lines[start:start + limit]
        return {"path": str(p), "total_lines": len(lines),
                "content": "".join(window), "shown": slice(start, start + limit)}
    except Exception as e:
        return {"error": str(e)[:500]}


# ---- write-file ------------------------------------------------------------

@_tool
def write_file(path: str, content: str) -> dict:
    """Overwrite a file completely. Safe for new files; use patch_file for edits."""
    p = BASE / path.lstrip("/")
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        prev = p.read_text(encoding="utf-8") if p.exists() else ""
        p.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(p), "bytes": len(content.encode()),
                "prev_bytes": len(prev.encode())}
    except Exception as e:
        return {"error": str(e)[:500]}


# ---- patch-file ------------------------------------------------------------

@_tool
def patch_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> dict:
    """Find-and-replace in a file (fuzzy match). Returns diff."""
    p = BASE / path.lstrip("/")
    try:
        text = p.read_text(encoding="utf-8")
    except Exception as e:
        return {"error": f"read failed: {e}"}
    if old_string not in text and not replace_all:
        # Try fuzzy: strip whitespace differences
        norm_old = re.sub(r'\s+', ' ', old_string.strip())
        norm_text = re.sub(r'\s+', ' ', text)
        if norm_old in norm_text:
            old_string = old_string.strip()
        else:
            return {"error": f"old_string not found in {p.name}. Use read_file to inspect first.",
                    "suggested": "Use read_file then craft exact old_string"}
    new_text = text.replace(old_string, new_string, 1 if not replace_all else 0)
    if new_text == text:
        return {"error": "no change made (old/new identical after replacement)"}
    # diff
    import difflib
    diff = list(difflib.unified_diff(text.splitlines(keepends=True),
                                     new_text.splitlines(keepends=True),
                                     fromfile=f"a/{p.name}", tofile=f"b/{p.name}"))
    p.write_text(new_text, encoding="utf-8")
    return {"ok": True, "path": str(p), "diff": "".join(diff)[:3000]}


# ---- search-files ----------------------------------------------------------

@_tool
def search_files(pattern: str, path: str = ".", target: str = "content",
                 file_glob: str | None = None, limit: int = 30) -> dict:
    """Search file contents or find files by glob (uses ripgrep if available)."""
    p = BASE / path.lstrip("/")
    try:
        import subprocess as sp
        args = ["rg", "--color=never"]
        if target == "files":
            args += ["--files-with-matches"]
        if file_glob:
            args += ["--glob", file_glob]
        args += ["-n", "-l" if target == "files" else "-C3",
                 "--max-count", str(limit), pattern, str(p)]
        r = sp.run(args, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return {"matches": r.stdout[:5000], "cmd": " ".join(args)}
        return {"error": r.stderr[:300], "stdout": r.stdout[:500]}
    except FileNotFoundError:
        # Fallback: grep
        import subprocess as sp2
        cmd = ["grep", "-rn", "--include=*" + (file_glob or ""),
               "-l" if target == "files" else "-C2",
               "-m", str(limit), pattern, str(p)]
        r = sp2.run(cmd, capture_output=True, text=True, timeout=30)
        return {"matches": r.stdout[:5000], "fallback": "grep"}
    except Exception as e:
        return {"error": str(e)[:300]}


# ---- run-cmd ---------------------------------------------------------------

@_tool
def run_cmd(command: str, cwd: str | None = None,
            timeout: int = 120, env_extra: dict | None = None) -> dict:
    """Run a shell command and return stdout/stderr/exit_code."""
    c = cwd or str(BASE)
    full_env = {**os.environ}
    if env_extra:
        full_env.update(env_extra)
    try:
        r = subprocess.run(command, shell=True, cwd=c, capture_output=True,
                           text=True, timeout=timeout, env=full_env)
        out = (r.stdout or "")[:8000]
        err = (r.stderr or "")[:2000]
        return {"exit_code": r.returncode, "stdout": out, "stderr": err}
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout}s", "partial": True}
    except Exception as e:
        return {"error": str(e)[:500]}


# ---- validate-python -------------------------------------------------------

@_tool
def validate_python(path: str) -> dict:
    """Syntax-check a Python file. Returns errors or ok."""
    p = BASE / path.lstrip("/")
    try:
        with open(p, "r", encoding="utf-8") as f:
            src = f.read()
        ast.parse(src, filename=str(p))
        return {"ok": True, "path": str(p), "lines": len(src.splitlines())}
    except SyntaxError as e:
        return {"ok": False, "path": str(p),
                "error": f"Line {e.lineno}: {e.msg}",
                "highlight": e.text}
    except Exception as e:
        return {"ok": False, "path": str(p), "error": str(e)}


# ---- list-files ------------------------------------------------------------

@_tool
def list_files(path: str = ".", recursive: bool = False,
               max_depth: int = 3) -> dict:
    """List files/dirs under path, respecting max_depth."""
    p = BASE / path.lstrip("/")
    out = []
    def _walk(d, depth):
        if depth > max_depth:
            return
        try:
            for child in sorted(d.iterdir()):
                rel = child.relative_to(p)
                out.append({"path": str(rel), "type": "dir" if child.is_dir() else "file",
                            "size": child.stat().st_size if child.is_file() else None})
                if child.is_dir() and recursive:
                    _walk(child, depth + 1)
        except PermissionError:
            out.append({"path": str(d.relative_to(p)), "type": "dir", "error": "perm"})
    _walk(p, 0)
    return {"count": len(out), "entries": out[:200]}


# ---- git-status ------------------------------------------------------------

@_tool
def git_status() -> dict:
    """Show git status, recent commits, and any uncommitted changes."""
    try:
        r = subprocess.run(["git", "status", "--short", "--porcelain"],
                           capture_output=True, text=True, cwd=str(BASE), timeout=10)
        r2 = subprocess.run(["git", "log", "--oneline", "-10"],
                            capture_output=True, text=True, cwd=str(BASE), timeout=10)
        r3 = subprocess.run(["git", "diff", "HEAD", "--stat"],
                            capture_output=True, text=True, cwd=str(BASE), timeout=10)
        return {"status_lines": (r.stdout or "").strip(),
                "recent": (r2.stdout or "").strip(),
                "diff_stat": (r3.stdout or "").strip()}
    except Exception as e:
        return {"error": str(e)}


# ---- run-tests -------------------------------------------------------------

@_tool
def run_tests(filter_str: str = "", verbosity: int = 1) -> dict:
    """Run pytest suite. filter_str narrows to a module or keyword."""
    args = [PYTHON, "-m", "pytest", "backend/tests/", "-q"]
    if verbosity > 1:
        args.insert(-1, "-v")
    if filter_str:
        args.append(f"-k {filter_str}")
    try:
        r = subprocess.run(args, capture_output=True, text=True, cwd=str(BASE), timeout=120)
        return {"exit_code": r.returncode, "stdout": (r.stdout or "")[:5000],
                "stderr": (r.stderr or "")[:1000]}
    except Exception as e:
        return {"error": str(e)[:500]}


# ---- diagnose-db -----------------------------------------------------------

@_tool
def diagnose_db() -> dict:
    """Inspect SQLite schema, row counts, and health."""
    import sqlite3
    db = BASE / "backend" / "civic.db"
    if not db.exists():
        return {"error": "civic.db not found"}
    try:
        conn = sqlite3.connect(str(db))
        cur = conn.cursor()
        tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        info = []
        for (t,) in tables:
            try:
                cnt = cur.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
                cols = [d[1] for d in cur.execute(f"PRAGMA table_info([{t}])").fetchall()]
                info.append({"table": t, "rows": cnt, "columns": cols})
            except Exception as e:
                info.append({"table": t, "error": str(e)})
        conn.close()
        return {"db": str(db), "tables": info}
    except Exception as e:
        return {"error": str(e)}


# Build the public schema (strip _fn)
TOOL_SCHEMA = [{k: v for k, v in t.items() if k != "_fn"} for t in TOOLS.values()]
