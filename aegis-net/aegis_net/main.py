"""Interactive CLI for AEGIS-NET. Run: python -m aegis_net.main"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from aegis_net.supervisor import Supervisor

def main():
    sup = Supervisor()
    print("Commands: <goal text> | status | consolidate | quit\n")
    while True:
        try:
            cmd = input("AEGIS > ").strip()
            if not cmd: continue
            if cmd.lower() in ("quit","exit","q"): break
            if cmd.lower() == "status":
                import json
                print(json.dumps(sup.swarm_status(), indent=2))
            elif cmd.lower() == "consolidate":
                print(sup.consolidate())
            else:
                result = sup.run_goal(cmd)
                for r in result["results"]:
                    if r.get("status") == "success":
                        print(f"\n{r.get('result','')[:500]}\n")
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()
