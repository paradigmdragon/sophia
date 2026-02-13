import subprocess
import os
import sys
from datetime import datetime, timezone

# Ensure we can import sophia_kernel from root
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

from sophia_kernel.executor.executor import execute_skill

def get_last_commit():
    try:
        msg = subprocess.check_output(
            ["git", "log", "-1", "--pretty=%B"],
            text=True
        ).strip()

        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True
        ).strip()

        return sha, msg
    except Exception as e:
        print(f"Error getting git info: {e}")
        return None, None


def main():
    sha, msg = get_last_commit()
    if not sha:
        return

    # Map to Note Schema for consistency across 'actions' namespace
    data = {
        "namespace": "actions",
        "data": {
            "title": f"Git Commit: {sha[:7]}",
            "body": msg,
            "tags": ["git", "commit", "auto-ingest"],
            "refs": {
                "commit": sha,
                "ts": datetime.now(timezone.utc).isoformat()
            },
            "v": "git_v1"
        }
    }

    try:
        print(f" [Sophia] Ingesting commit {sha[:7]}...")
        execute_skill("memory.append", "0.1.0", data)
        print(" [Sophia] Ingest successful.")
    except Exception as e:
        print(f" [Sophia] Ingest failed: {e}")


if __name__ == "__main__":
    main()
