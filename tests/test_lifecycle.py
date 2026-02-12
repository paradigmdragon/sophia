import sys
import os
import os
from fastapi.testclient import TestClient

# Add project root to path
# Assuming we run this from project root, or adding explicit path
sys.path.append(os.getcwd())

from api.server import app

client = TestClient(app)

def test_lifecycle():
    print("\n=== Starting Lifecycle Integration Test ===")
    
    # 1. Ingest
    print("\n[1] Ingesting...")
    res = client.post("/ingest", json={"ref_uri": "api_test_lifecycle"})
    assert res.status_code == 200, f"Ingest failed: {res.text}"
    ep_id = res.json()["episode_id"]
    print(f" -> Episode ID: {ep_id}")
    
    # 2. Propose (Trigger High Confidence Candidate)
    print("\n[2] Proposing 'plan' (High Confidence)...")
    res = client.post("/propose", json={"episode_id": ep_id, "text": "This is a plan."})
    assert res.status_code == 200, f"Propose failed: {res.text}"
    cand_ids = res.json()["candidate_ids"]
    assert len(cand_ids) > 0
    c_id = cand_ids[0]
    print(f" -> Candidate ID: {c_id}")
    
    # 3. Adopt
    print("\n[3] Adopting...")
    res = client.post("/adopt", json={"episode_id": ep_id, "candidate_id": c_id})
    assert res.status_code == 200, f"Adopt failed: {res.text}"
    print(" -> Adopted successfully")
    
    # 4. Status (Check Queue)
    print("\n[4] Checking Status...")
    res = client.get("/status")
    assert res.status_code == 200
    data = res.json()
    print(f" -> Status: {data['state']}")
    print(f" -> Queue: {data['queue_counts']}")
    
    # 5. Set State to IDLE
    print("\n[5] Setting State to IDLE...")
    res = client.post("/set_state", json={"state": "IDLE"})
    assert res.status_code == 200
    
    # 6. Dispatch
    print("\n[6] Dispatching...")
    res = client.post("/dispatch", json={"context": {}})
    assert res.status_code == 200
    data = res.json()
    if data["dispatched"]:
        print(f" -> Dispatched: {data['message']['content']}")
    else:
        print(" -> No message dispatched (Expected if queue empty)")
    
    print("\nSUCCESS: Lifecycle Test Passed")

if __name__ == "__main__":
    test_lifecycle()
