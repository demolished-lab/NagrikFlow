"""Mini-Hermes: built-in autonomous agent for civic-pathfinder.

The agent can:
- Perceive errors, bugs, missing features from logs and user reports
- Reason about fixes using an LLM (Bynara/Ollama)
- Spawn sub-agents (parallel tasks via BackgroundTasks)
- Audit every change with before/after diff
- Self-heal: detect -> diagnose -> fix -> verify
- Help users: explain code, suggest improvements, automate updates

Run modes:
  - Agent loop: perceive -> think -> act -> audit -> verify
  - CLI chat: hermes chat --task "..."
  - REST: POST /agent/run {task, mode, budget}
  - Frontend dashboard widget
"""
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session

from .agent_tools import TOOL_SCHEMA, TOOLS
from .audit import append as audit_append
from .audit import read_last as audit_read
from .llm import complete as llm_complete

# Re-exports, not dead code: main.py serves agentmod.TOOL_SCHEMA and
# agentmod.audit_read on its routes; __all__ keeps ruff's F401 off them.
__all__ = ["TOOLS", "TOOL_SCHEMA", "audit_append", "audit_read", "llm_complete"]

# ---- Agent config ---------------------------------------------------------

MAX_TURNS = int(os.environ.get("CIVIC_AGENT_MAX_TURNS", "20"))
MAX_TOKENS_PER_CALL = int(os.environ.get("CIVIC_AGENT_MAX_TOKENS", "2000"))
AGENT_TIMEOUT_SECS = int(os.environ.get("CIVIC_AGENT_TIMEOUT", "300"))
LOG_LEVEL = os.environ.get("CIVIC_AGENT_LOG", "info")  # debug | info | warn

SYSTEM_PROMPT = """You are Mini-Hermes, the built-in autonomous agent for Civic Path Navigator.
Your job: perceive issues, diagnose root causes, fix code safely, audit everything, and report results.

You have access to these TOOLS (call them via the tool system):
- read_file(path, offset, limit): Read file with line numbers
- write_file(path, content): Write/overwrite a file
- patch_file(path, old_string, new_string, replace_all): Precise edit
- search_files(pattern, path, target, file_glob, limit): Find code/text
- run_cmd(command, cwd, timeout, env_extra): Execute shell commands
- validate_python(path): Syntax-check Python files
- list_files(path, recursive, max_depth): Directory listing
- git_status(): Check git state
- run_tests(filter_str, verbosity): Run pytest suite
- diagnose_db(): Inspect SQLite database health

Rules:
1. ALWAYS read before writing. Never edit files without seeing their current state.
2. ALWAYS validate Python files after editing (validate_python).
3. ALWAYS run tests after any code change (run_tests).
4. ALWAYS audit every action: audit_append(action, target, summary, diff_before, diff_after).
5. If a test fails, diagnose first, then fix, then re-run. Never ship broken code.
6. Prefer minimal, surgical changes over rewrites.
7. If you cannot fix something safely, report the issue with context and stop.
8. For user-facing messages, be helpful and plain-spoken. No jargon.

Current project context:
- Backend: FastAPI at C:\\Users\\Raja\\civic-pathfinder\\backend\\app\\
- Frontend: React+TS at C:\\Users\\Raja\\civic-pathfinder\\frontend\\src\\
- DB: SQLite at C:\\Users\\Raja\\civic-pathfinder\\backend\\civic.db
- Tests: pytest at backend/tests/ (currently 29 passing)
- Pending items from PENDING.md need attention.

When given a task:
1. Perceive: understand what needs to be done
2. Diagnose: gather context (read files, search code, check tests)
3. Plan: decide the minimal set of changes
4. Act: make changes one at a time, validating each
5. Verify: run tests, check for regressions
6. Report: summarize what changed, what's verified, what's left
"""

TOOL_CALL_RE = re.compile(r'<tool_call>\s*(\w+)\s*\(([^)]*)\)\s*</tool_call>', re.DOTALL)


# ---- Tool executor --------------------------------------------------------

def _exec_tool(name: str, args_str: str) -> dict:
    """Parse args and execute a registered tool. Returns result dict."""
    fn = TOOLS.get(name)
    if not fn:
        return {"error": f"unknown tool: {name}"}
    try:
        # Parse JSON args or simple key=value
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


# ---- Main agent loop ------------------------------------------------------

class AgentLoop:
    def __init__(self, task: str, mode: str = "auto", budget: int = MAX_TURNS):
        self.task = task
        self.mode = mode  # auto | help | chat
        self.budget = budget
        self.turn = 0
        self.history: list[dict] = []
        self.result: dict = {"status": "pending", "turns": 0, "actions": [], "final": ""}

    def step(self, user_msg: str) -> dict:
        """One turn: send to LLM, parse tool calls, execute, collect result."""
        self.turn += 1
        if self.turn > self.budget:
            self.result["status"] = "budget_exceeded"
            return self.result

        # Build conversation
        msgs = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *self.history,
            {"role": "user", "content": user_msg},
        ]

        # Call LLM
        prompt = "\n".join(f"{m['role']}: {m['content']}" for m in msgs)
        try:
            response, via = llm_complete(prompt, role="extract")
        except Exception as e:
            response = f"[LLM error: {e}]"
            via = "none"

        self.history.append({"role": "assistant", "content": response})

        # Parse tool calls
        tool_calls = TOOL_CALL_RE.findall(response)
        if not tool_calls:
            # No tool call - this is the final answer
            self.result["status"] = "done"
            self.result["turns"] = self.turn
            self.result["final"] = response.strip()
            self.result["via"] = via
            return self.result

        # Execute tools
        tool_results = []
        for name, args in tool_calls:
            result = _exec_tool(name, args)
            tool_results.append({"tool": name, "result": result})
            # Log action
            audit_append(
                action="tool_call",
                target=name,
                summary=args[:200],
                agent="mini-hermes",
                turn=self.turn,
                success=result.get("ok", result.get("error") is None),
            )
            # Append tool result to history
            result_str = json.dumps(result, ensure_ascii=False)[:2000]
            self.history.append({
                "role": "user",
                "content": f"<tool_result>\nTool: {name}\nArgs: {args}\nResult:\n{result_str}\n</tool_result>"
            })

        return self.result


def run_agent(task: str, mode: str = "auto", budget: int = MAX_TURNS) -> dict:
    """Run the full agent loop until done or budget exhausted."""
    loop = AgentLoop(task=task, mode=mode, budget=budget)
    
    start = time.time()
    while loop.turn < loop.budget:
        result = loop.step(task if loop.turn == 0 else "Continue. Execute your plan.")
        
        # Check if done
        if result.get("status") == "done":
            elapsed = time.time() - start
            result["elapsed_secs"] = round(elapsed, 1)
            result["turns"] = loop.turn
            result["task"] = task
            
            # Final audit entry
            audit_append(
                action="agent_run",
                target=task[:80],
                summary=f"completed in {result['turns']} turns, {result['elapsed_secs']}s",
                agent="mini-hermes",
                task=task,
                turns=loop.turn,
                elapsed=elapsed,
            )
            return result
        
        # Timeout check
        if time.time() - start > AGENT_TIMEOUT_SECS:
            loop.result["status"] = "timeout"
            loop.result["turns"] = loop.turn
            loop.result["task"] = task
            return loop.result
    
    loop.result["status"] = "budget_exhausted"
    loop.result["turns"] = loop.turn
    loop.result["task"] = task
    return loop.result


# ---- CLI entry point -----------------------------------------------------

def cli_main():
    import argparse
    parser = argparse.ArgumentParser(description="Mini-Hermes agent")
    parser.add_argument("--task", "-t", required=True, help="Task to execute")
    parser.add_argument("--mode", "-m", choices=["auto", "help", "chat"], default="auto")
    parser.add_argument("--budget", "-b", type=int, default=MAX_TURNS)
    args = parser.parse_args()
    
    print(f"Mini-Hermes starting: {args.task}")
    print(f"Mode: {args.mode}, Budget: {args.budget} turns")
    print("-" * 60)
    
    result = run_agent(args.task, mode=args.mode, budget=args.budget)
    
    print("-" * 60)
    print(f"Status: {result['status']}")
    print(f"Turns: {result.get('turns', '?')}")
    if "final" in result:
        print(f"\nResponse:\n{result['final'][:2000]}")
    if "elapsed_secs" in result:
        print(f"Time: {result['elapsed_secs']}s")
    
    return result


if __name__ == "__main__":
    cli_main()


def run_agent_job(engine, job_id: int):
    """Run an agent task as a background job, storing result in DB."""
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
        result = run_agent(p.get("task", ""), mode=p.get("mode", "auto"),
                           budget=p.get("budget", MAX_TURNS))
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
