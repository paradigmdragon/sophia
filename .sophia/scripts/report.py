import argparse
import json
import os
from datetime import datetime, timezone

LEDGER_PATH = os.path.join(os.path.dirname(__file__), "../ledger/ledger.jsonl")

def report(node_id, status, summary, evidence):
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "node_id": node_id,
        "status": status,
        "summary": summary,
        "evidence": evidence
    }
    
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    
    with open(LEDGER_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    print(f"✅ Reported: [{status}] {node_id} - {summary}")

    # Trigger compilation
    compile_script = os.path.join(os.path.dirname(__file__), "compile.py")
    if os.path.exists(compile_script):
        os.system(f"python {compile_script}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Report work status to Sophia Ledger")
    parser.add_argument("--id", required=True, help="Node ID (e.g., feat.auth.login)")
    parser.add_argument("--status", required=True, choices=["DONE", "IN_PROGRESS", "BLOCKED"], help="Status")
    parser.add_argument("--msg", required=True, dest="summary", help="Summary message")
    parser.add_argument("--ref", default="", dest="evidence", help="Evidence (commit hash, file path)")
    
    args = parser.parse_args()
    report(args.id, args.status, args.summary, args.evidence)
