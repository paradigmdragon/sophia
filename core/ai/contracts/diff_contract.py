from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChangedPrinciple(BaseModel):
    model_config = {"extra": "forbid"}

    from_: str = Field(min_length=1, max_length=240, alias="from")
    to: str = Field(min_length=1, max_length=240)


class ClarifyQuestion(BaseModel):
    model_config = {"extra": "forbid"}

    q: str = Field(min_length=1, max_length=240)
    type: Literal["scope", "priority", "definition"]


class DiffContract(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    schema_: Literal["diff_contract.v0.1"] = Field(default="diff_contract.v0.1", alias="schema")
    diff_summary: str = Field(min_length=1, max_length=400)
    changed_principles: list[ChangedPrinciple] = Field(default_factory=list)
    affected_modules: list[str] = Field(default_factory=list, max_length=40)
    clarify: list[ClarifyQuestion] = Field(default_factory=list)


def fallback_diff_contract() -> dict:
    return DiffContract(
        diff_summary="unknown",
        changed_principles=[],
        affected_modules=[],
        clarify=[],
    ).model_dump(by_alias=True)
