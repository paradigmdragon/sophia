import sys
import os
# Add project root to path
sys.path.append(os.getcwd())

from core.system import SophiaSystem

def test_system_logic():
    print("\n=== Starting System Logic Test (No API) ===")
    
    # Initialize System with file DB to avoid sharing issues or just use a test db file
    # In-memory might be tricky if connections are not shared properly in my implementation
    # defined in WorkflowEngine (it takes a factory).
    # SophiaSystem uses sessionmaker bound to an engine.
    # SQLite in-memory with multiple connections (threads) can be tricky but here it is single thread.
    
    DB_PATH = "sqlite:///sophia_test_sys.db"
    if os.path.exists("sophia_test_sys.db"):
        os.remove("sophia_test_sys.db")
    if os.path.exists("heart_state.json"):
        os.remove("heart_state.json")

    system = SophiaSystem(db_path=DB_PATH)
    
    # 1. Ingest
    print("\n[1] Ingesting...")
    ep_id = system.ingest("sys_test_001")
    assert ep_id is not None
    print(f" -> Episode ID: {ep_id}")
    
    # 2. Propose
    print("\n[2] Proposing...")
    c_ids = system.propose(ep_id, "This is a plan.")
    assert len(c_ids) > 0
    c_id = c_ids[0]
    print(f" -> Candidate ID: {c_id}")
    
    # 3. Adopt
    print("\n[3] Adopting...")
    b_id = system.adopt(ep_id, c_id)
    assert b_id is not None
    print(f" -> Backbone ID: {b_id}")
    
    # 4. Status
    print("\n[4] Checking Status...")
    status = system.get_heart_status()
    print(f" -> State: {status['state']}")
    assert status['state'] == "FOCUS" # Default
    
    # 5. Dispatch (Empty)
    print("\n[5] Dispatching...")
    msg = system.dispatch_heart()
    if msg:
        print(f" -> Dispatched: {msg['content']}")
    else:
        print(" -> No message (Expected)")

    print("\nSUCCESS: System Logic Verified")

if __name__ == "__main__":
    test_system_logic()
