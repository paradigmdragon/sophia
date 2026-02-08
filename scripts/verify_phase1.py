import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.manager import EpisodeManager
from core.schema import Source, SourceType, RangeKind, SourceRange

def verify():
    print("Verifying Sophia Phase 1 Implementation...")
    
    # 1. Initialize Manager
    try:
        manager = EpisodeManager()
        print("[Pass] EpisodeManager initialized.")
    except Exception as e:
        print(f"[Fail] EpisodeManager initialization failed: {e}")
        return

    # 2. Check Manifest Loading
    if manager.manifest.schema_version != "0.1":
        print(f"[Fail] Schema version mismatch: {manager.manifest.schema_version}")
        return
    print("[Pass] Manifest loaded successfully.")

    # 3. Create Episode
    test_ep_id = "ep_test_001"
    sources = [
        Source(
            type=SourceType.CHAT_LOG,
            uri="logs/chat/test.jsonl",
            range=SourceRange(kind=RangeKind.MESSAGE_ID, start="m1", end="m2")
        )
    ]
    
    try:
        ep = manager.create_episode(test_ep_id, sources)
        print(f"[Pass] Episode {ep.episode_id} created.")
    except Exception as e:
        print(f"[Fail] Episode creation failed: {e}")
        return

    # 4. Verify Persistence (Reload)
    manager2 = EpisodeManager()
    if test_ep_id not in manager2.manifest.episodes:
        print("[Fail] Persistence verification failed. Episode not found after reload.")
        return
    
    loaded_ep = manager2.manifest.episodes[test_ep_id]
    if loaded_ep.lifecycle.state != "open":
        print(f"[Fail] Episode state mismatch: {loaded_ep.lifecycle.state}")
        return
    
    print("[Pass] Persistence verified.")

    # 5. Cleanup
    del manager2.manifest.episodes[test_ep_id]
    manager2.save_manifest()
    print("[Pass] Cleanup completed.")
    
    print("\nPhase 1 Implementation Verified Automatically.")

if __name__ == "__main__":
    verify()
