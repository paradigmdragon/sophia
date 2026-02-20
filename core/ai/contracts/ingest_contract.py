from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IngestEntity(BaseModel):
    model_config = {"extra": "forbid"}

    type: Literal["person", "org", "concept", "date", "law"]
    text: str = Field(min_length=1, max_length=200)


class IngestContract(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    schema_: Literal["ingest_contract.v0.1"] = Field(default="ingest_contract.v0.1", alias="schema")
    summary_120: str = Field(min_length=1, max_length=120)
    entities: list[IngestEntity] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list, max_length=12)
    context_tag: str = Field(min_length=1, max_length=64)
    confidence_model: float = Field(ge=0.0, le=1.0)


def fallback_ingest_contract() -> dict:
    return IngestContract(
        summary_120="unknown",
        entities=[],
        tags=[],
        context_tag="chat",
        confidence_model=0.0,
    ).model_dump(by_alias=True)
