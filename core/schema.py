from __future__ import annotations
from enum import Enum
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, HttpUrl, validator
from datetime import datetime

# --- Enums ---

class EpisodeState(str, Enum):
    OPEN = "open"
    CLOSED = "closed"

class EpisodeClosedBy(str, Enum):
    DECISION_MADE = "decision_made"
    TIMEOUT = "timeout"
    CONTEXT_SWITCH = "context_switch"
    MANUAL_CLOSE = "manual_close"

class SourceType(str, Enum):
    CHAT_LOG = "chat_log"
    ASR_SRT = "asr_srt"
    DOC_REF = "doc_ref"
    FILE_REF = "file_ref"

class RangeKind(str, Enum):
    MESSAGE_ID = "message_id"
    LINE_RANGE = "line_range"
    TIME_RANGE = "time_range"

class DecisionType(str, Enum):
    ADOPT_PATCH = "adopt_patch"
    # System extensions can add more types here

class ReasonCode(str, Enum):
    WRONG = "WRONG"
    IRRELEVANT = "IRRELEVANT"
    TOO_MUCH = "TOO_MUCH"
    STYLE_MISMATCH = "STYLE_MISMATCH"
    LATER = "LATER"
    SUPERSEDED = "SUPERSEDED"

class PatchStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    DELETED = "deleted"

class EngineType(str, Enum):
    SOPHIA = "sophia"
    GENERAL = "general"

class PatchType(str, Enum):
    REASONING = "reasoning"
    GRAMMAR = "grammar"

# --- Models ---

class PatchOption(BaseModel):
    id: str
    semantic: str
    label: str

class Patch(BaseModel):
    patch_id: str
    target_episode_id: str # Linking to Episode instead of Anchor for now (since it's memory)
    engine: EngineType
    type: PatchType
    issue_code: str
    thin_summary: str
    status: PatchStatus
    options: Optional[List[PatchOption]] = []
    created_at: datetime
    updated_at: datetime

class SourceRange(BaseModel):
    kind: RangeKind
    start: Any  # string or int
    end: Any    # string or int

class Source(BaseModel):
    type: SourceType
    uri: str
    range: SourceRange
    hash: Optional[str] = None  # sha256:... recommended

class EpisodeRevision(BaseModel):
    rev: int
    prev_episode_ref: Optional[str] = None
    change_note_thin: Optional[str] = None

class EpisodeSignature(BaseModel):
    bitset: str = Field(..., description="Hex string starting with 0x")
    bit_length: int = 64
    mapping_version: str
    label_hint: Optional[str] = None

    @validator('bitset')
    def bitset_must_be_hex(cls, v):
        if not v.startswith('0x'):
            raise ValueError('bitset must start with 0x')
        try:
            int(v, 16)
        except ValueError:
            raise ValueError('bitset must be a valid hex string')
        return v

class EpisodeSnapshot(BaseModel):
    intent_thin: str
    outcome_thin: str
    open_questions: Optional[List[str]] = []
    key_terms: Optional[List[str]] = []

class EpisodeLifecycle(BaseModel):
    state: EpisodeState
    opened_at: datetime
    end_at: Optional[datetime] = None
    closed_by: Optional[EpisodeClosedBy] = None

class EpisodeStats(BaseModel):
    importance: int = 0
    progress: int = 0
    interaction_count: int = 0
    updated_at: datetime

class Episode(BaseModel):
    episode_id: str
    revision: EpisodeRevision
    sources: List[Source]
    signature: EpisodeSignature
    snapshot: EpisodeSnapshot
    lifecycle: EpisodeLifecycle
    stats_cache: Optional[EpisodeStats] = None

    # Constraint Check: No raw text field exists here.

class EpisodeDecision(BaseModel):
    decision_id: str
    target_episode: str
    type: str # Can be DecisionType enum value or string extension
    value: Any # string | object | null
    reason_code: Optional[str] = None # ReasonCode or string
    decided_at: datetime

class UserProfileSummary(BaseModel):
    # Flexible stricture for now
    pass

class MemoryManifest(BaseModel):
    schema_version: str = "0.1"
    current_mapping_version: str = "1.0"
    user_profile_summary: Optional[Dict[str, Any]] = {}
    episodes: Dict[str, Episode] = {}
    patches: Dict[str, Patch] = {} # Active patches (Working Memory)
    episode_decisions: List[EpisodeDecision] = []

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
