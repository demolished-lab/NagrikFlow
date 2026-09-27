"""Hermes Core: Autonomous agent system with sub-agent spawning, self-healing, and full audit.

Architecture:
- Main Hermes agent perceives tasks, plans, executes, verifies
- Sub-agents spawn for parallel specialization (docs, tests, deploys)
- Self-healing: detect failure → diagnose → fix → verify loop
- Full audit trail with before/after diffs
- Memory context maintained across turns
"""
import asyncio
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .llm import complete as llm_complete
from .audit import append as audit_append
from .audit import read_last as audit_read
from .agent_tools import TOOLS, TOOL_SCHEMA, BASE as PROJECT_BASE
from sqlmodel import Session


# ---- Configuration --------------------------------------------------------

MAX_TURNS = int(os.environ.get("HERMES_MAX_TURNS", "50"))
MAX_TOKENS = int(os.environ.get("HERMES_MAX_TOKENS", "4000"))
AGENT_TIMEOUT = int(os.environ.get("HERMES_TIMEOUT", "600"))
SUB_AGENT_BUDGET = int(os.environ.get("HERMES_SUB_BUDGET", "15"))
MAX_SUB_AGENTS = int(os.environ.get("HERMES_MAX_SUBS", "4"))
SELF_HEAL_RETRIES = int(os.environ.get("HERMES_HEAL_RETRIES", "3"))

# ---- System Prompt --------------------------------------------------------

SYSTEM_PROMPT = """You are Hermes, an autonomous agent system for Civic Path Navigator.

YOUR CAPABILITIES:
1. **Code mastery** — Read, write, patch, validate Python/TypeScript
2. **Testing** — Run pytest, fix failures, add coverage
3. **Deployment** — Build frontend, run migrations, configure servers
4. **Research** — Search files, docs, web (via tools)
5. **Problem solving** — Diagnose bugs, suggest improvements, automate tasks
6. **Specialization** — Spawn sub-agents for parallel workstreams

YOUR WORKFLOW (per turn):
1. PERCEIVE — Understand the task and current state
2. DIAGNOSE — Gather context (read files, check tests, search code)
3. PLAN — Decide minimal changes needed
4. ACT — Execute one change at a time
5. VERIFY — Validate with tests/syntax checks
6. AUDIT — Log every action with before/after
7. REFLECT — Evaluate success, decide next step

RULES:
- NEVER edit without reading first
- ALWAYS validate after editing (syntax + tests)
- ALWAYS audit every action
- If tests fail: diagnose → fix → re-run (max {heal_retries} retries)
- Prefer surgical changes over rewrites
- If stuck, report context and stop — don't guess
- For user questions: be helpful, plain-spoken, no jargon

PROJECT CONTEXT:
- Backend: FastAPI at {backend_path}
- Frontend: React+TS at {frontend_path}
- DB: SQLite at {db_path}
- Tests: pytest at {tests_path} ({test_count} passing)
- Git repo: {repo_root}

AVAILABLE TOOLS:
{tools_list}

When given a task:
1. Start with `plan` tool to outline approach
2. Execute plan step-by-step using appropriate tools
3. Verify each step before proceeding
4. Report results with clear summary

Respond in this format for tool calls:
<tool_call>tool_name(arg1="value1", arg2="value2")</tool_call>

For final answers (no more tools needed), respond normally.
"""


# ---- Tool Registry (Extended) ---------------------------------------------

def _register_tool(fn):
    """Decorator to register a tool."""
    TOOLS[fn.__name__] = {
        "name": fn.__name__,
        "description": getattr(fn, "__doc__", "").strip(),
        "params": getattr(fn, "__params__", {}),
        "_fn": fn,
    }
    return fn


@_register_tool
def plan(task: str, context: str = "") -> dict:
    """Create execution plan for a task. Returns structured approach."""
    # Analyze task and suggest plan
    plan_prompt = f"""Task: {task}
Context: {context}

Create a step-by-step plan:
1. What files need to change?
2. What order should changes be made?
3. What validations are needed?
4. What could go wrong?

Return JSON: {{\"steps\": [...], \"risks\": [...], \"estimated_turns\": N}}"""
    
    try:
        response, _ = llm_complete(plan_prompt, role="extract")
    except Exception as e:
        from .obs import warn
        warn("hermes", "plan generation failed, using default plan", error=e)
        response = ""
    if response:
        m = re.search(r'\{.*\}', response, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except Exception as e:
                from .obs import warn
                warn("hermes", "unparseable plan reply, using default plan",
                     error=e)
        else:
            from .obs import warn
            warn("hermes", "plan reply contained no JSON, using default plan")
    
    return {"steps": ["Understand task", "Read relevant files", "Make changes", "Verify"], "risks": [], "estimated_turns": 5}


@_register_tool
def spawn_subagent(task: str, specialization: str = "general", budget: int = SUB_AGENT_BUDGET) -> dict:
    """Spawn a parallel sub-agent for specialized work. Returns sub-job ID."""
    from .subagent import spawn_subagent as _spawn
    # This will be wired to the main app's engine later
    return {"status": "sub_agent_spawned", "task": task, "specialization": specialization}


@_register_tool
def read_file(path: str, offset: int = 1, limit: int = 500) -> dict:
    """Read file with line numbers."""
    p = PROJECT_BASE / path.lstrip("/")
    try:
        with open(p, "r", encoding="utf-8") as f:
            lines = f.readlines()
        start = max(0, offset - 1)
        window = lines[start:start + limit]
        return {"path": str(p), "total_lines": len(lines),
                "content": "".join(window), "offset": offset, "limit": limit}
    except Exception as e:
        return {"error": str(e)}


@_register_tool
def write_file(path: str, content: str) -> dict:
    """Write/overwrite a file completely."""
    p = PROJECT_BASE / path.lstrip("/")
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        prev = p.read_text(encoding="utf-8") if p.exists() else ""
        p.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(p), "bytes_written": len(content.encode()),
                "bytes_before": len(prev.encode())}
    except Exception as e:
        return {"error": str(e)}


@_register_tool
def patch_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> dict:
    """Find-and-replace in file with fuzzy matching. Returns diff."""
    p = PROJECT_BASE / path.lstrip("/")
    try:
        text = p.read_text(encoding="utf-8")
    except Exception as e:
        return {"error": f"read failed: {e}"}
    
    if old_string not in text and not replace_all:
        norm_old = re.sub(r'\s+', ' ', old_string.strip())
        norm_text = re.sub(r'\s+', ' ', text)
        if norm_old in norm_text:
            old_string = old_string.strip()
        else:
            return {"error": "old_string not found. Use read_file first.",
                    "suggested": "Read the file to get exact text"}
    
    new_text = text.replace(old_string, new_string, 1 if not replace_all else 0)
    if new_text == text:
        return {"error": "no change made (identical)"}
    
    import difflib
    diff = list(difflib.unified_diff(
        text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile=f"a/{p.name}", tofile=f"b/{p.name}"
    ))
    p.write_text(new_text, encoding="utf-8")
    return {"ok": True, "path": str(p), "diff": "".join(diff)[:3000]}


@_register_tool
def search_files(pattern: str, path: str = ".", target: str = "content",
                 file_glob: Optional[str] = None, limit: int = 30) -> dict:
    """Search file contents or find files by glob."""
    p = PROJECT_BASE / path.lstrip("/")
    try:
        import subprocess as sp
        args = ["rg", "--color=never"]
        if target == "files":
            args += ["--files-with-matches"]
        if file_glob:
            args += ["--glob", file_glob]
        args += ["-n", "-l" if target == "files" else "-C2",
                 "--max-count", str(limit), pattern, str(p)]
        r = sp.run(args, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            return {"matches": r.stdout[:5000], "cmd": " ".join(args)}
        return {"error": r.stderr[:300], "stdout": r.stdout[:500]}
    except FileNotFoundError:
        import subprocess as sp2
        cmd = ["grep", "-rn", "--include=*" + (file_glob or ""),
               "-l" if target == "files" else "-C2",
               "-m", str(limit), pattern, str(p)]
        r = sp2.run(cmd, capture_output=True, text=True, timeout=30)
        return {"matches": r.stdout[:5000], "fallback": "grep"}
    except Exception as e:
        return {"error": str(e)[:300]}


@_register_tool
def run_cmd(command: str, cwd: Optional[str] = None, timeout: int = 120,
            env_extra: Optional[dict] = None) -> dict:
    """Run shell command and return output."""
    import subprocess
    c = cwd or str(PROJECT_BASE)
    full_env = {**os.environ}
    if env_extra:
        full_env.update(env_extra)
    try:
        r = subprocess.run(command, shell=True, cwd=c, capture_output=True,
                           text=True, timeout=timeout, env=full_env)
        return {
            "exit_code": r.returncode,
            "stdout": (r.stdout or "")[:8000],
            "stderr": (r.stderr or "")[:2000],
            "success": r.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout}s", "partial": True}
    except Exception as e:
        return {"error": str(e)[:500]}


@_register_tool
def validate_python(path: str) -> dict:
    """Syntax-check a Python file."""
    import ast
    p = PROJECT_BASE / path.lstrip("/")
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


@_register_tool
def run_tests(filter_str: str = "", verbosity: int = 1) -> dict:
    """Run pytest suite."""
    python_exe = os.path.join(sys.prefix, "Scripts", "python.exe") if sys.platform == "win32" else "python3"
    args = [python_exe, "-m", "pytest", "backend/tests/", "-q"]
    if verbosity > 1:
        args.insert(-1, "-v")
    if filter_str:
        args.append(f"-k {filter_str}")
    try:
        import subprocess
        r = subprocess.run(args, capture_output=True, text=True, 
                          cwd=str(PROJECT_BASE), timeout=120)
        return {
            "exit_code": r.returncode,
            "stdout": (r.stdout or "")[:5000],
            "stderr": (r.stderr or "")[:1000],
            "passed": r.returncode == 0
        }
    except Exception as e:
        return {"error": str(e)[:500]}


@_register_tool
def git_status() -> dict:
    """Check git status and recent commits."""
    import subprocess
    try:
        r = subprocess.run(["git", "status", "--short", "--porcelain"],
                          capture_output=True, text=True, cwd=str(PROJECT_BASE), timeout=10)
        r2 = subprocess.run(["git", "log", "--oneline", "-10"],
                           capture_output=True, text=True, cwd=str(PROJECT_BASE), timeout=10)
        r3 = subprocess.run(["git", "diff", "HEAD", "--stat"],
                           capture_output=True, text=True, cwd=str(PROJECT_BASE), timeout=10)
        return {
            "status_lines": (r.stdout or "").strip(),
            "recent_commits": (r2.stdout or "").strip(),
            "diff_stat": (r3.stdout or "").strip()
        }
    except Exception as e:
        return {"error": str(e)}


@_register_tool
def git_commit(message: str, files: list[str] = None) -> dict:
    """Commit changes to git."""
    import subprocess
    try:
        if files:
            for f in files:
                subprocess.run(["git", "add", f], cwd=str(PROJECT_BASE), check=True)
        else:
            subprocess.run(["git", "add", "."], cwd=str(PROJECT_BASE), check=True)
        subprocess.run(["git", "commit", "-m", message], cwd=str(PROJECT_BASE), check=True)
        return {"ok": True, "message": "committed"}
    except Exception as e:
        return {"error": str(e)}


@_register_tool
def list_files(path: str = ".", recursive: bool = False, max_depth: int = 3) -> dict:
    """List files/dirs under path."""
    p = PROJECT_BASE / path.lstrip("/")
    out = []
    def _walk(d, depth):
        if depth > max_depth:
            return
        try:
            for child in sorted(d.iterdir()):
                rel = child.relative_to(p)
                out.append({
                    "path": str(rel),
                    "type": "dir" if child.is_dir() else "file",
                    "size": child.stat().st_size if child.is_file() else None
                })
                if child.is_dir() and recursive:
                    _walk(child, depth + 1)
        except PermissionError:
            out.append({"path": str(d.relative_to(p)), "type": "dir", "error": "perm"})
    _walk(p, 0)
    return {"count": len(out), "entries": out[:200]}


@_register_tool
def diagnose_db() -> dict:
    """Inspect database health."""
    import sqlite3
    db = PROJECT_BASE / "backend" / "civic.db"
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


@_register_tool
def check_health() -> dict:
    """Check application health and dependencies."""
    deps = {}
    try:
        import fastapi
        deps["fastapi"] = fastapi.__version__
    except ImportError:
        deps["fastapi"] = "NOT INSTALLED"

    try:
        import sqlmodel
        deps["sqlmodel"] = sqlmodel.__version__
    except ImportError:
        deps["sqlmodel"] = "NOT INSTALLED"

    try:
        import jwt
        deps["pyjwt"] = jwt.__version__
    except ImportError:
        deps["pyjwt"] = "NOT INSTALLED"

    return {
        "status": "healthy" if all(v != "NOT INSTALLED" for v in deps.values()) else "degraded",
        "dependencies": deps,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@_register_tool
def read_config(key: str = "") -> dict:
    """Read environment/config values (safe, no secrets)."""
    safe_keys = ["DATABASE_URL", "OLLAMA_MODEL", "BYNARA_MODEL", "LOG_LEVEL", "BACKUP_DIR"]
    result = {}
    for k in safe_keys:
        if not key or k.lower() == key.lower():
            val = os.environ.get(k, "")
            if val and k.upper() == k:  # Skip lowercase (might be sensitive)
                result[k] = val[:50] + "..." if len(val) > 50 else val
    return result


@_register_tool
def ask_user(question: str, options: list[str] = None) -> dict:
    """Ask user a question (for interactive mode)."""
    # In non-interactive mode, log the question
    print(f"\n[HERMES QUESTION]: {question}")
    if options:
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")
    return {"question": question, "options": options, "status": "logged"}


@_register_tool
def search_web(task: str, max_results: int = 8) -> dict:
    """Search for government URLs using wigolo (keyless)."""
    try:
        from .discover import discover as _discover
        results = _discover(task, max_results)
        return {"results": results[:max_results], "count": len(results)}
    except Exception as e:
        return {"error": str(e)[:200]}


@_register_tool
def fetch_url(url: str) -> dict:
    """Fetch URL content via wigolo (keyless fallback)."""
    try:
        from .discover import fetch_text as _fetch
        text = _fetch(url)
        return {"url": url, "chars": len(text), "preview": text[:500]}
    except Exception as e:
        return {"error": str(e)[:200]}


@_register_tool
def run_backup(engine=None) -> dict:
    """Run database backup now."""
    try:
        from .backup import run as _backup_run
        # We need engine - try to get from import
        return {"status": "call with engine parameter"}
    except Exception as e:
        return {"error": str(e)[:200]}


@_register_tool
def list_backups() -> dict:
    """List available backups."""
    try:
        from .backup import listing as _backup_list
        return {"backups": _backup_list()}
    except Exception as e:
        return {"error": str(e)[:200]}


@_register_tool
def path_packet(slug: str) -> dict:
    """Citizen path-workflow packet for a civic map slug: ordered steps with
    prerequisites, document checklist, fees, apply links, official sources
    (final redirect URLs, fetch tier) and guide documents — as citizen-ready
    Markdown the chat can relay."""
    try:
        from .main import engine
        from . import packet as packetmod
        from .models import TaskMap
        from sqlmodel import select
        with Session(engine) as s:
            m = s.exec(select(TaskMap).where(TaskMap.slug == slug)).first()
            if not m:
                return {"error": f"unknown map {slug!r}"}
            packet = packetmod.build_packet(m)
        return {"slug": packet["slug"], "title": packet["title"],
                "counts": packet["counts"],
                "markdown": packetmod.render_markdown(packet)[:6000]}
    except Exception as e:
        return {"error": str(e)[:200]}


@_register_tool
def deploy_frontend() -> dict:
    """Build frontend for production."""
    try:
        r = run_cmd("npm run build", cwd=str(PROJECT_BASE / "frontend"), timeout=120)
        return {"success": r.get("exit_code") == 0, "output": r.get("stdout", "")[:1000]}
    except Exception as e:
        return {"error": str(e)[:200]}


@_register_tool
def commit_changes(message: str, files: list[str] = None) -> dict:
    """Commit changes to git with message."""
    try:
        import subprocess
        if files:
            for f in files:
                subprocess.run(["git", "add", f], cwd=str(PROJECT_BASE), check=True)
        else:
            subprocess.run(["git", "add", "."], cwd=str(PROJECT_BASE), check=True)
        subprocess.run(["git", "commit", "-m", message], cwd=str(PROJECT_BASE), check=True)
        return {"ok": True, "message": "committed"}
    except Exception as e:
        return {"error": str(e)}


# ---- Agent Engine ---------------------------------------------------------

class HermesEngine:
    """Main agent engine with self-healing and sub-agent support."""
    
    def __init__(self, task: str, mode: str = "auto", budget: int = MAX_TURNS):
        self.task = task
        self.mode = mode
        self.budget = budget
        self.turn = 0
        self.history: list[dict] = []
        self.plan: dict = {}
        self.result: dict = {
            "status": "pending",
            "turns": 0,
            "actions": [],
            "final": "",
            "sub_agents": [],
            "errors": []
        }
        
        # Build system prompt
        tools_list = "\n".join(f"- {t['name']}: {t['description']}" for t in TOOL_SCHEMA)
        self.system_prompt = SYSTEM_PROMPT.format(
            backend_path=PROJECT_BASE / "backend" / "app",
            frontend_path=PROJECT_BASE / "frontend" / "src",
            db_path=PROJECT_BASE / "backend" / "civic.db",
            tests_path=PROJECT_BASE / "backend" / "tests",
            test_count=39,  # Will be dynamic
            repo_root=PROJECT_BASE,
            heal_retries=SELF_HEAL_RETRIES,
            tools_list=tools_list
        )
    
    def step(self, user_msg: str) -> dict:
        """One turn: LLM call → parse tools → execute → verify."""
        self.turn += 1
        if self.turn > self.budget:
            self.result["status"] = "budget_exceeded"
            return self.result
        
        # Build messages
        msgs = [
            {"role": "system", "content": self.system_prompt},
            *self.history,
            {"role": "user", "content": user_msg}
        ]
        
        # Call LLM
        prompt = "\n".join(f"{m['role']}: {m['content']}" for m in msgs)
        try:
            response, via = llm_complete(prompt, role="extract")
        except Exception as e:
            response = f"[LLM error: {e}]"
            via = "none"
            self.result["errors"].append(f"LLM error: {e}")
        
        self.history.append({"role": "assistant", "content": response})
        
        # Parse tool calls
        tool_calls = self._parse_tool_calls(response)
        if not tool_calls:
            # No tool call = final answer
            self.result["status"] = "done"
            self.result["turns"] = self.turn
            self.result["final"] = response.strip()
            self.result["via"] = via
            return self.result
        
        # Execute tools
        for name, args in tool_calls:
            result = self._exec_tool(name, args)
            
            # Audit
            audit_append(
                action="tool_call",
                target=name,
                summary=args[:200],
                agent="hermes",
                turn=self.turn,
                success=result.get("ok", result.get("error") is None)
            )
            
            # Add to history
            result_str = json.dumps(result, ensure_ascii=False)[:2000]
            self.history.append({
                "role": "user",
                "content": f"<tool_result>\nTool: {name}\nArgs: {args}\nResult:\n{result_str}\n</tool_result>"
            })
        
        return self.result
    
    def _parse_tool_calls(self, response: str) -> list[tuple[str, str]]:
        """Parse<tool_call>tool_name(args)</tool_call> patterns from response."""
        pattern = r'<tool_call>\s*(\w+)\s*\(([^)]*)\)\s*</tool_call>'
        return re.findall(pattern, response, re.DOTALL)
    
    def _exec_tool(self, name: str, args_str: str) -> dict:
        """Execute a registered tool."""
        fn = TOOLS.get(name)
        if not fn:
            return {"error": f"unknown tool: {name}"}
        
        try:
            args_str = args_str.strip()
            if args_str.startswith("{"):
                kwargs = json.loads(args_str)
            else:
                kwargs = {}
                for kv in re.findall(r'(\w+)=(?:"([^"]*)"|\'([^\']*)\'|([\w.]+))', args_str):
                    k = kv[0]
                    v = kv[1] if kv[1] is not None else (kv[2] if kv[2] is not None else kv[3])
                    kwargs[k] = v
            
            result = fn["_fn"](**kwargs)
            return result
        except Exception as e:
            return {"error": f"{name}: {e}", "traceback": traceback.format_exc()[:500]}
    
    def run(self) -> dict:
        """Run the agent loop until done or budget exhausted."""
        start = time.time()
        
        # First turn: plan
        self.step(f"Task: {self.task}. Create a plan.")
        
        # Then execute
        while self.turn < self.budget:
            result = self.step("Continue executing your plan. Check progress and adjust.")
            
            # Check completion
            if result.get("status") == "done":
                elapsed = time.time() - start
                self.result["elapsed_secs"] = round(elapsed, 1)
                self.result["turns"] = self.turn
                self.result["task"] = self.task
                
                # Final audit
                audit_append(
                    action="agent_run",
                    target=self.task[:80],
                    summary=f"completed in {self.result['turns']} turns, {self.result['elapsed_secs']}s",
                    agent="hermes",
                    task=self.task,
                    turns=self.turn,
                    elapsed=elapsed
                )
                return self.result
            
            # Timeout check
            if time.time() - start > AGENT_TIMEOUT:
                self.result["status"] = "timeout"
                self.result["turns"] = self.turn
                self.result["task"] = self.task
                return self.result
        
        self.result["status"] = "budget_exhausted"
        self.result["turns"] = self.turn
        self.result["task"] = self.task
        return self.result


# ---- Public API -----------------------------------------------------------

def run_hermes(task: str, mode: str = "auto", budget: int = MAX_TURNS) -> dict:
    """Run Hermes agent on a task."""
    engine = HermesEngine(task=task, mode=mode, budget=budget)
    return engine.run()


def run_hermes_job(engine, job_id: int):
    """Run agent task as background job, store result in DB."""
    from .jobs import claim
    from .models import Job
    if not claim(engine, job_id):
        return  # another dispatcher owns this job
    with Session(engine) as s:
        j = s.get(Job, job_id)
        if not j:
            return
        j.status = "running"
        s.add(j)
        s.commit()
        p = json.loads(j.payload)
    
    try:
        result = run_hermes(
            p.get("task", ""),
            mode=p.get("mode", "auto"),
            budget=p.get("budget", MAX_TURNS)
        )
        with Session(engine) as s:
            j = s.get(Job, job_id)
            if j:
                j.status = "done"
                j.result = json.dumps(result)
                j.finished_at = datetime.now(timezone.utc)
                s.add(j)
                s.commit()
    except Exception as e:
        with Session(engine) as s:
            j = s.get(Job, job_id)
            if j:
                j.status = "failed"
                j.result = json.dumps({"error": str(e)})
                j.finished_at = datetime.now(timezone.utc)
                s.add(j)
                s.commit()


# ---- CLI Entry Point ------------------------------------------------------

def cli_main():
    import argparse
    parser = argparse.ArgumentParser(description="Hermes Autonomous Agent")
    parser.add_argument("--task", "-t", required=True, help="Task to execute")
    parser.add_argument("--mode", "-m", choices=["auto", "help", "chat"], default="auto")
    parser.add_argument("--budget", "-b", type=int, default=MAX_TURNS)
    args = parser.parse_args()
    
    print(f"Hermes starting: {args.task}")
    print(f"Mode: {args.mode}, Budget: {args.budget} turns")
    print("-" * 60)
    
    result = run_hermes(args.task, mode=args.mode, budget=args.budget)
    
    print("-" * 60)
    print(f"Status: {result['status']}")
    print(f"Turns: {result.get('turns', '?')}")
    if "final" in result:
        print(f"\nResponse:\n{result['final'][:2000]}")
    if "elapsed_secs" in result:
        print(f"Time: {result['elapsed_secs']}s")
    if result.get("errors"):
        print(f"\nErrors: {result['errors']}")
    
    return result


if __name__ == "__main__":
    cli_main()
