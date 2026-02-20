from __future__ import annotations

import os
import re
import time
from collections import Counter

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field


APP_VERSION = "0.1.0"
TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣_:-]+")


class BridgeRunRequest(BaseModel):
    task: str = "ingest"
    contract_schema: str = "ingest_contract.v0.1"
    input: dict = Field(default_factory=dict)
    timeout_ms: int = 3000


def _normalize_text(value: str) -> str:
    return " ".join((value or "").split())


def _top_tokens(text: str, *, limit: int = 5) -> list[str]:
    words = [item.lower() for item in TOKEN_RE.findall(text or "") if len(item) >= 2]
    counts = Counter(words)
    return [token for token, _ in counts.most_common(limit)]


def _build_ingest_contract(text: str) -> dict:
    compact = _normalize_text(text)
    lowered = compact.lower()
    if "법" in compact or "law" in lowered:
        context_tag = "legal"
    elif "spec" in lowered or "설계" in compact or "doc" in lowered:
        context_tag = "doc"
    elif "work" in lowered or "작업" in compact or "todo" in lowered:
        context_tag = "work"
    else:
        context_tag = "chat"
    return {
        "schema": "ingest_contract.v0.1",
        "summary_120": compact[:120] or "unknown",
        "entities": [],
        "tags": _top_tokens(compact, limit=5),
        "context_tag": context_tag,
        "confidence_model": 0.81,
    }


app = FastAPI(title="Sophia Foundation Bridge", version=APP_VERSION)


@app.get("/bridge/health")
async def bridge_health():
    return {
        "status": "ok",
        "provider": "foundation",
        "available": True,
        "version": APP_VERSION,
    }


@app.post("/bridge/run")
async def bridge_run(payload: BridgeRunRequest):
    started = time.perf_counter()
    task = str(payload.task or "").strip().lower()
    if task != "ingest" or payload.contract_schema != "ingest_contract.v0.1":
        return {
            "ok": False,
            "error_code": "BRIDGE_SCHEMA_MISMATCH",
            "message": "unsupported task or schema for bridge v0.1",
        }

    text = str((payload.input or {}).get("text") or "")
    if "__BRIDGE_TIMEOUT__" in text:
        sleep_s = max(0.0, (float(payload.timeout_ms) / 1000.0) + 0.5)
        time.sleep(sleep_s)
        return {
            "ok": False,
            "error_code": "BRIDGE_TIMEOUT",
            "message": "model timeout",
        }

    if not text.strip():
        return {
            "ok": False,
            "error_code": "BRIDGE_SCHEMA_MISMATCH",
            "message": "empty input text",
        }

    contract = _build_ingest_contract(text)
    latency_ms = int((time.perf_counter() - started) * 1000)
    return {
        "ok": True,
        "contract": contract,
        "meta": {
            "provider": "foundation",
            "latency_ms": latency_ms,
        },
    }


if __name__ == "__main__":
    host = os.getenv("FOUNDATION_BRIDGE_HOST", "127.0.0.1")
    port = int(os.getenv("FOUNDATION_BRIDGE_PORT", "8765"))
    uvicorn.run(app, host=host, port=port, log_level="info")
