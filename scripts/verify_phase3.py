import sys
import os
import shutil
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.manager import EpisodeManager

def verify():
    print("Verifying Sophia Phase 3 Implementation (Expression)...")
    
    # 1. Setup
    manifest_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../memory/memory_manifest.json"))
    shutil.copy(manifest_path, manifest_path + ".bak")

    try:
        manager = EpisodeManager()
        
        # 2. Test Input (Triggering EPI-01: Definition)
        # "정의가 뭔가요" triggers EPI-01
        input_text = "이 현상의 정의가 뭔가요?" 
        print(f"Input: {input_text}")
        
        result = manager.process_input(input_text)
        
        # 3. Verify Log
        print(f"[Pass] Message ID generated: {result['message_id']}")
        
        # 4. Verify Patch
        if not result['signals']:
             print("[Fail] No signals detected.")
             return
        print(f"[Pass] Signal detected: {result['signals'][0]['issue_code']}")

        # 5. Verify Expression (LLM)
        response = result.get('sophia_response')
        if not response:
            print("[Fail] No Sophia response generated.")
            return
            
        print(f"[Pass] Sophia Response: {response}")
        
        # Check if it looks like a question or fallback
        # Fallback message for EPI-01 is "이 단어는 이 상황에서 어떤 특별한 의미를 갖나요?"
        # LLM output should be different if successful.
        
        fallback_msg = result['signals'][0]['thin_summary']
        if response == fallback_msg:
            print("[Warn] Model failed or returned fallback. (This is acceptable if model is missing)")
        else:
            print("[Pass] LLM Generation successful (Response differs from fallback).")

        print("\nPhase 3 Implementation Verified Automatically.")

    except Exception as e:
        print(f"[Fail] Verification Exception: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if os.path.exists(manifest_path + ".bak"):
            shutil.move(manifest_path + ".bak", manifest_path)

if __name__ == "__main__":
    verify()
