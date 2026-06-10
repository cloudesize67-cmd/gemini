"""Aegis.net — Quick Start. Run: python aegis-net/start.py"""
import sys, os
from dotenv import load_dotenv
_HERE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_HERE, ".env"))
sys.path.insert(0, _HERE)

from aegis_net.supervisor import Supervisor
from aegis_net import llm_router

def main():
    available = llm_router.detect_available_backends()
    if "anthropic" not in available:
        print("ERROR: No Anthropic key found. Set ANTHROPIC_API_KEY in aegis-net/.env")
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
