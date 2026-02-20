import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from core.system import SophiaSystem
from api.config import settings
from api.memory_router import router as memory_router
from api.sone_router import router as sone_router
from api.ai_router import router as ai_router
from api.work_router import router as work_router
from api.forest_router import router as forest_router
from api.mind_router import router as mind_router
from api.sync_router import router as sync_router
from api.inactivity_watch_service import InactivityWatcherConfig, InactivityWatcherService
from core.engine.scheduler import get_scheduler
from datetime import datetime
from fastapi.responses import RedirectResponse


app = FastAPI(title="Sophia Bit-Hybrid Engine API", version="0.1.0")


@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# Desktop(WebView) -> local API calls can fail with opaque "Load failed" without CORS.
# Keep this permissive for local-first development/runtime.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize System (Single Instance)
system = SophiaSystem(db_path=settings.db_path)
scheduler = get_scheduler(settings.db_path, poll_interval_seconds=5)
inactivity_watcher_service = InactivityWatcherService(
    db_path=settings.db_path,
    config=InactivityWatcherConfig(
        enabled=bool(settings.enable_watchers),
        threshold_days=int(settings.watcher_threshold_days),
        cooldown_days=int(settings.watcher_cooldown_days),
        daily_limit=int(settings.watcher_daily_limit),
    ),
)


def register_watcher_jobs(target_scheduler=None) -> bool:
    if not settings.enable_watchers:
        return False
    scheduler_obj = target_scheduler or scheduler
    scheduler_obj.register_periodic_job(
        name="inactivity_watcher",
        callback=inactivity_watcher_service.run_once,
        interval_seconds=max(1, int(settings.watcher_interval_seconds)),
        startup_delay_seconds=max(0, int(settings.watcher_startup_delay_seconds)),
    )
    return True

app.include_router(memory_router)
app.include_router(sone_router)
app.include_router(ai_router)
app.include_router(work_router)
app.include_router(forest_router)
app.include_router(mind_router)
app.include_router(sync_router)
from api.chat_router import router as chat_router
app.include_router(chat_router)

from fastapi.staticfiles import StaticFiles
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent # Resolve to Sophia/
from core.engine.constants import FOREST_ROOT
DASHBOARD_ROOT = BASE_DIR / FOREST_ROOT / "project"
DEFAULT_DASHBOARD_PATH = DASHBOARD_ROOT / "sophia" / "dashboard"

print(f"[API] Server File: {__file__}")
print(f"[API] Base Dir: {BASE_DIR}")
print(f"[API] Dashboard Root: {DASHBOARD_ROOT}")
print(f"[API] Default Dashboard Path: {DEFAULT_DASHBOARD_PATH}")
print(f"[API] Default Index Exists? {(DEFAULT_DASHBOARD_PATH / 'index.html').exists()}")

if not DASHBOARD_ROOT.exists():
    print(f"[API] Creating Dashboard root at {DASHBOARD_ROOT}")
    DASHBOARD_ROOT.mkdir(parents=True, exist_ok=True)

# Force mount to surface errors
import sys
sys.stderr.write(f"[API] Mounting dashboard from {DASHBOARD_ROOT}\n")

@app.get("/dashboard")
@app.get("/dashboard/")
async def dashboard_default():
    return RedirectResponse(url="/dashboard/sophia/dashboard/")

app.mount("/dashboard", StaticFiles(directory=str(DASHBOARD_ROOT), html=True), name="dashboard")

@app.get("/debug/dashboard")
async def debug_dashboard():
    return {
        "root_path": str(DASHBOARD_ROOT),
        "root_exists": DASHBOARD_ROOT.exists(),
        "default_path": str(DEFAULT_DASHBOARD_PATH),
        "default_exists": DEFAULT_DASHBOARD_PATH.exists(),
        "default_index_exists": (DEFAULT_DASHBOARD_PATH / "index.html").exists(),
        "projects": [f.name for f in DASHBOARD_ROOT.glob("*") if f.is_dir()] if DASHBOARD_ROOT.exists() else []
    }



@app.on_event("startup")
async def startup_event():
    register_watcher_jobs()
    scheduler.start_background()


@app.on_event("shutdown")
async def shutdown_event():
    scheduler.stop_background()

class IngestRequest(BaseModel):
    ref_uri: str

class ProposeRequest(BaseModel):
    episode_id: str
    text: str = ""

class AdoptRequest(BaseModel):
    episode_id: str
    candidate_id: str


class RejectRequest(BaseModel):
    episode_id: str
    candidate_id: str
    reason: str | None = None

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
    except ValueError as e:
        message = str(e)
        if "invalid backbone_bits" in message:
            reason = "INVALID_BITMAP"
            match = re.search(r"reason=([A-Z_]+)", message)
            if match:
                reason = match.group(1)
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "BITMAP_INVALID",
                    "reason": reason,
                    "message": message,
                },
            )
        raise HTTPException(status_code=400, detail={"code": "PROPOSE_INVALID", "message": message})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class MoveRequest(BaseModel):
    old_path: str
    new_path: str

@app.post("/fs/move")
async def fs_move(req: MoveRequest):
    success = system.move_file(req.old_path, req.new_path)
    if not success:
        raise HTTPException(status_code=400, detail="Move failed")
    return {"status": "ok", "old": req.old_path, "new": req.new_path}

@app.get("/graph/data")
async def graph_data():
    return system.get_graph_data()

@app.post("/adopt")
async def adopt(req: AdoptRequest):
    try:
        candidate = system.get_candidate(req.candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidate not found")
        was_adopted = str(candidate.get("status", "")).upper() == "ADOPTED"
        b_id = system.adopt(req.episode_id, req.candidate_id)
        return {
            "backbone_id": b_id,
            "status": "already_adopted" if was_adopted else "adopted",
            "idempotent": bool(was_adopted),
        }
    except HTTPException:
        raise
    except ValueError as e:
        message = str(e)
        if "EPISODE MISMATCH" in message.upper():
            raise HTTPException(
                status_code=409,
                detail={"code": "CANDIDATE_EPISODE_MISMATCH", "message": message},
            )
        if "REJECTED" in message.upper():
            raise HTTPException(
                status_code=409,
                detail={"code": "CANDIDATE_ALREADY_REJECTED", "message": message},
            )
        if "ADOPTED" in message.upper():
            raise HTTPException(
                status_code=409,
                detail={"code": "CANDIDATE_ALREADY_ADOPTED", "message": message},
            )
        raise HTTPException(status_code=400, detail={"code": "ADOPT_INVALID", "message": message})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reject")
async def reject(req: RejectRequest):
    try:
        candidate = system.get_candidate(req.candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidate not found")
        was_rejected = str(candidate.get("status", "")).upper() == "REJECTED"
        reason = str(req.reason or "").strip()
        changed = bool(system.reject(req.episode_id, req.candidate_id, reason=reason or None))
        return {
            "status": "already_rejected" if (was_rejected or not changed) else "rejected",
            "candidate_id": req.candidate_id,
            "reason": reason or None,
            "idempotent": bool(was_rejected or not changed),
        }
    except HTTPException:
        raise
    except ValueError as e:
        message = str(e)
        if "EPISODE MISMATCH" in message.upper():
            raise HTTPException(
                status_code=409,
                detail={"code": "CANDIDATE_EPISODE_MISMATCH", "message": message},
            )
        if "ADOPTED" in message.upper():
            raise HTTPException(
                status_code=409,
                detail={"code": "CANDIDATE_ALREADY_ADOPTED", "message": message},
            )
        raise HTTPException(status_code=400, detail={"code": "REJECT_INVALID", "message": message})
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
