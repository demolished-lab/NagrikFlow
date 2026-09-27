# Production Security Checklist
# Run this script to verify all security requirements are met

import os
import sys
from pathlib import Path


def check_secret_length(secret: str) -> tuple[bool, str]:
    """Check if APP_SECRET meets minimum length requirement."""
    if len(secret) < 32:
        return False, f"APP_SECRET too short: {len(secret)} chars (need 32+)"
    return True, f"APP_SECRET OK ({len(secret)} chars)"


def check_env_exists() -> tuple[bool, str]:
    """Verify .env file exists."""
    env_path = Path(__file__).resolve().parent / "backend" / ".env"
    if not env_path.exists():
        return False, ".env file not found"
    return True, ".env file exists"


def check_critical_vars() -> list[tuple[str, str]]:
    """Check for critical environment variables. Status: ok | warn | fail."""
    required = ["APP_SECRET", "DATABASE_URL"]
    optional = ["TELEGRAM_BOT_TOKEN", "DIGILOCKER_CLIENT_ID", "BYNARA_API_KEY"]

    results = []
    env_path = Path(__file__).resolve().parent / "backend" / ".env"

    if not env_path.exists():
        return [("fail", ".env file not found")]

    env_vars = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env_vars[key.strip()] = value.strip()

    def placeholder(v: str) -> bool:
        return not v or v.lower().startswith(("your-", "change-me", "changeme"))

    for var in required:
        if var not in env_vars:
            results.append(("fail", f"Missing required variable: {var}"))
        elif placeholder(env_vars[var]):
            results.append(("fail", f"{var} not configured (placeholder value)"))
        else:
            results.append(("ok", f"{var} configured"))

    for var in optional:
        if var not in env_vars:
            results.append(("warn", f"{var} not set (optional)"))
        elif placeholder(env_vars[var]):
            results.append(("warn", f"{var} present but EMPTY — related features disabled"))
        else:
            results.append(("ok", f"{var} configured"))

    if env_vars.get("DATABASE_URL", "").startswith("sqlite"):
        results.append(("warn", "DATABASE_URL is SQLite — use Postgres for production"))
    if env_vars.get("DIGILOCKER_ENV", "sandbox") != "production":
        results.append(("warn", "DIGILOCKER_ENV is sandbox — no real DigiLocker identity import"))

    return results


def check_dependencies() -> list[tuple[bool, str]]:
    """Verify required Python packages are installed."""
    try:
        import fastapi
        import sqlmodel
        import jwt
        import httpx
        return [
            (True, f"fastapi {fastapi.__version__}"),
            (True, f"sqlmodel {sqlmodel.__version__}"),
            (True, f"PyJWT {jwt.__version__}"),
            (True, f"httpx {httpx.__version__}"),
        ]
    except ImportError as e:
        return [(False, f"Missing dependency: {e}")]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    print("=" * 60)
    print("Civic Path Navigator - Production Security Check")
    print("=" * 60)
    
    issues = []
    warnings = []
    
    # Check .env
    ok, msg = check_env_exists()
    print(f"\n[{'✓' if ok else '✗'}] {msg}")
    if not ok:
        issues.append(msg)

    # Check secret length
    env_path = Path(__file__).resolve().parent / "backend" / ".env"
    if env_path.exists():
        env_vars = {}
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    env_vars[key.strip()] = value.strip()

        if "APP_SECRET" in env_vars:
            ok, msg = check_secret_length(env_vars["APP_SECRET"])
            print(f"[{'✓' if ok else '✗'}] {msg}")
            if not ok:
                issues.append(msg)

    # Check critical vars
    print("\n--- Critical Variables ---")
    marks = {"ok": "✓", "warn": "⚠", "fail": "✗"}
    for status, msg in check_critical_vars():
        print(f"[{marks[status]}] {msg}")
        if status == "fail":
            issues.append(msg)
        elif status == "warn":
            warnings.append(msg)
    
    # Check dependencies
    print("\n--- Dependencies ---")
    for ok, msg in check_dependencies():
        print(f"[{'✓' if ok else '✗'}] {msg}")
        if not ok:
            issues.append(msg)
    
    # Summary
    print("\n" + "=" * 60)
    if issues:
        print(f"❌ SECURITY CHECK FAILED: {len(issues)} issue(s), {len(warnings)} warning(s)")
        print("\nPlease fix the above issues before deploying to production.")
        sys.exit(1)
    elif warnings:
        print(f"⚠️  SECURITY CHECK PASSED WITH {len(warnings)} WARNING(S)")
        print("\nRequired checks pass, but review warnings before production/government use.")
        sys.exit(0)
    else:
        print("✅ SECURITY CHECK PASSED")
        print("\nAll critical security requirements are met.")
        print("You are ready for production deployment.")
        sys.exit(0)


if __name__ == "__main__":
    main()
