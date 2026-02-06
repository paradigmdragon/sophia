from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
import uuid

class TaskConfigSnapshot(BaseModel):
    engine: Dict[str, Any] = Field(default_factory=dict)
    refine: Dict[str, Any] = Field(default_factory=dict)

class TaskInput(BaseModel):
    media: str
    script: Optional[str] = None

class TaskOutput(BaseModel):
    raw_srt: Optional[str] = None
    refined_srt: Optional[str] = None
    refined_txt: Optional[str] = None
    log: Optional[str] = None

class Task(BaseModel):
    task_id: str
    run_id: str = Field(default_factory=lambda: f"run_{uuid.uuid4().hex[:8]}")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: Literal["queued", "running", "done", "failed", "canceled"] = "queued"
    type: str = "transcription"
    requested_by: str = "user"
    tool: str = "sophia-core-v0.1.3"
    
    config_snapshot: TaskConfigSnapshot = Field(default_factory=TaskConfigSnapshot)
    input: TaskInput
    pipeline: List[str] = ["asr", "refine"]
    output: TaskOutput = Field(default_factory=TaskOutput)
    
    error: Optional[Dict[str, Any]] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class Event(BaseModel):
    ts: datetime = Field(default_factory=datetime.utcnow)
    run_id: str
    task_id: str
    type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    agent: str = "oss"

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
