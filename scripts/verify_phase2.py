import sys
import os
import shutil

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.manager import EpisodeManager

def verify():
    print("Verifying Sophia Phase 2 Implementation (Bicameral Resonance)...")
    
    # 1. Setup
    manifest_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../memory/memory_manifest.json"))
    # Backup manifest
    shutil.copy(manifest_path, manifest_path + ".bak")

    try:
        manager = EpisodeManager()
        
        # 2. Test Input (Triggering EPI-01)
        input_text = "이 단어의 의미는 무엇인가?"
        print(f"Input: {input_text}")
        
        result = manager.process_input(input_text)
        
        # 3. Verify Log
        print(f"[Pass] Message ID generated: {result['message_id']}")
        
        # 4. Verify Resonance (Patch Creation)
        signals = result['signals']
        if not signals:
            print("[Fail] No signals detected. Epidora failed.")
            return

        patch = signals[0]
        if patch['issue_code'] != "EPI-01":
             print(f"[Fail] Wrong issue code: {patch['issue_code']}")
             return
        
        print(f"[Pass] Signal detected: {patch['issue_code']} - {patch['thin_summary']}")
        
        # 5. Verify Persistence
        manager2 = EpisodeManager()
        saved_patch = manager2.manifest.patches.get(patch['patch_id'])
        if not saved_patch:
            print("[Fail] Patch not saved to manifest.")
            return
            
        print("[Pass] Patch persistence verified.")
        
        print("\nPhase 2 Implementation Verified Automatically.")

    except Exception as e:
        print(f"[Fail] Verification Exception: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Restore backup
        if os.path.exists(manifest_path + ".bak"):
            shutil.move(manifest_path + ".bak", manifest_path)

if __name__ == "__main__":
    verify()
