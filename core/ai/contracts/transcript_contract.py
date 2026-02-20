from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TranscriptActionItem(BaseModel):
    model_config = {"extra": "forbid"}

    owner: str = Field(min_length=1, max_length=120)
    task: str = Field(min_length=1, max_length=240)
    due: str = Field(min_length=1, max_length=64)


class TranscriptDecisionItem(BaseModel):
    model_config = {"extra": "forbid"}

    statement: str = Field(min_length=1, max_length=240)
    evidence: str = Field(min_length=1, max_length=240)


class TranscriptOpenQuestion(BaseModel):
    model_config = {"extra": "forbid"}

    q: str = Field(min_length=1, max_length=240)
    type: Literal["meaning", "scope", "priority", "fact"]


class TranscriptContract(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    schema_: Literal["transcript_contract.v0.1"] = Field(default="transcript_contract.v0.1", alias="schema")
    summary: str = Field(min_length=1, max_length=400)
    action_items: list[TranscriptActionItem] = Field(default_factory=list)
    decisions: list[TranscriptDecisionItem] = Field(default_factory=list)
    open_questions: list[TranscriptOpenQuestion] = Field(default_factory=list)


def fallback_transcript_contract() -> dict:
    return TranscriptContract(
        summary="unknown",
        action_items=[],
        decisions=[],
        open_questions=[],
    ).model_dump(by_alias=True)
