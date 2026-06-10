"""Aegis.net — Quick Start. Run: python aegis-net/start.py
Keys come from environment variables only — never from .env files.
Set ANTHROPIC_API_KEY in GitHub Secrets and Railway Variables.
"""
import sys, os
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from aegis_net.supervisor import Supervisor
from aegis_net import llm_router

def main():
    available = llm_router.detect_available_backends()
    if "anthropic" not in available:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        print("  → Add to GitHub Secrets: github.com/cloudesize67-cmd/gemini/settings/secrets/actions")
        print("  → Add to Railway Variables: railway.app → project → Variables")
        sys.exit(1)
    supervisor = Supervisor()
    print("AEGIS-NET online\n")
    result = supervisor.run_goal("Summarize what Aegis.net is in one sentence.")
    for r in result.get("results", []):
        if r.get("status") == "success":
            print(f"Smoke test: {r.get('result','')[:200]}\n")
            break
    print("System ready. Run: python -m aegis_net.main")

if __name__ == "__main__":
    main()
