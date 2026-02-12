from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from core.system import SophiaSystem
from api.config import settings
import asyncio
from datetime import datetime

app = FastAPI(title="Sophia Bit-Hybrid Engine API", version="0.1.0")

# Initialize System (Single Instance)
system = SophiaSystem(db_path=settings.db_path)

class IngestRequest(BaseModel):
    ref_uri: str

class ProposeRequest(BaseModel):
    episode_id: str
    text: str = ""

class AdoptRequest(BaseModel):
    episode_id: str
    candidate_id: str

class DispatchRequest(BaseModel):
    context: Optional[Dict[str, Any]] = {}

class StateRequest(BaseModel):
    state: str

@app.post("/ingest")
async def ingest(req: IngestRequest):
    try:
        ep_id = system.ingest(req.ref_uri)
        return {"episode_id": ep_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/propose")
async def propose(req: ProposeRequest):
    try:
        candidate_ids = system.propose(req.episode_id, req.text)
        
        # Auto-Reply Logic for Phase 0 Demo
        # If we generated candidates, pick the top one and write to memory_manifest.json
        if candidate_ids:
            top_cand_id = candidate_ids[0]
            cand_data = system.get_candidate(top_cand_id)
            
            if cand_data and cand_data.get("note_thin"):
                import json
                import os
                from datetime import datetime
                
                MANIFEST_PATH = "memory/memory_manifest.json"
                if os.path.exists(MANIFEST_PATH):
                    try:
                        with open(MANIFEST_PATH, "r") as f:
                            manifest = json.load(f)
                        
                        patch_id = f"p_{top_cand_id[-8:]}" # Use last 8 chars of cand_id
                        now_ts = datetime.now().isoformat()
                        
                        # Determine Content based on Note (Intent)
                        intent_note = cand_data.get("note_thin", "")
                        reply_content = intent_note
                        
                        # Logic Refinement: Custom Replies & Loop Control
                        if intent_note == "Conversation":
                            reply_content = "안녕하세요, 무엇을 도와드릴까요?"
                            # Disable Meta-Question (No issue_code)
                            issue_code = "EPI-00" 
                        elif intent_note == "Acknowledgment":
                            reply_content = "네."
                            issue_code = "EPI-00"
                        else:
                            # Standard Logic (Keep existing note as thin_summary)
                            reply_content = intent_note
                            issue_code = "EPI-00" # Default 
                            
                            # If it's a specific backbone detection, maybe we assign a code?
                            # For now, keep as is.
                        
                        new_patch = {
                            "patch_id": patch_id,
                            "target_episode_id": req.episode_id,
                            "engine": "sophia",
                            "type": "reasoning",
                            "issue_code": issue_code,
                            "thin_summary": reply_content,
                            "status": "pending",
                            "options": [],
                            "created_at": now_ts,
                            "updated_at": now_ts
                        }
                        
                        if "patches" not in manifest:
                            manifest["patches"] = {}
                            
                        manifest["patches"][patch_id] = new_patch
                        
                        with open(MANIFEST_PATH, "w") as f:
                            json.dump(manifest, f, indent=2, ensure_ascii=False)
                            
                        print(f"[API] Auto-Replied to Manifest: {patch_id} -> {reply_content}")
                        
                    except Exception as e:
                        print(f"[API] Failed to write auto-reply to manifest: {e}")

        return {"candidate_ids": candidate_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/adopt")
async def adopt(req: AdoptRequest):
    try:
        b_id = system.adopt(req.episode_id, req.candidate_id)
        return {"backbone_id": b_id, "status": "adopted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def status():
    """
    Returns Heart Engine status.
    Client can poll this endpoint to get 'presence' indicator.
    """
    return system.get_heart_status()

@app.post("/dispatch")
async def dispatch(req: DispatchRequest):
    msg_dict = system.dispatch_heart(req.context)
    if msg_dict:
        return {"dispatched": True, "message": msg_dict}
    return {"dispatched": False, "message": None}

@app.post("/set_state")
async def set_state(req: StateRequest):
    system.set_heart_state(req.state)
    return {"status": "success", "state": req.state}

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
