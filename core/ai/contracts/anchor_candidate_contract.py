from __future__ import annotations

from pydantic import BaseModel, Field


class AnchorCandidate(BaseModel):
    model_config = {"extra": "forbid"}

    term: str = Field(min_length=1, max_length=120)
    definition: str = Field(min_length=1, max_length=240)
    relations: list[str] = Field(default_factory=list, max_length=20)


class AnchorCandidateContract(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    schema_: str = Field(default="anchor_candidate.v0.1", alias="schema")
    summary_120: str = Field(min_length=1, max_length=120)
    anchors: list[AnchorCandidate] = Field(default_factory=list)
    linked_bits: list[str] = Field(default_factory=list, max_length=40)


def fallback_anchor_candidate_contract() -> dict:
    return AnchorCandidateContract(
        summary_120="unknown",
        anchors=[],
        linked_bits=[],
    ).model_dump(by_alias=True)
