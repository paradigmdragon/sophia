from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RuleCandidate(BaseModel):
    model_config = {"extra": "forbid"}

    type: Literal["term_meaning", "default_scope", "preference", "routing"]
    key: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=240)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    confidence_model: float = Field(ge=0.0, le=1.0)


class RuleCandidateContract(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    schema_: Literal["rule_candidate.v0.1"] = Field(default="rule_candidate.v0.1", alias="schema")
    candidates: list[RuleCandidate] = Field(default_factory=list)


def fallback_rule_candidate_contract() -> dict:
    return RuleCandidateContract(candidates=[]).model_dump(by_alias=True)
