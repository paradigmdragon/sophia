from __future__ import annotations

from core.ai.contracts.anchor_candidate_contract import (
    AnchorCandidateContract,
    fallback_anchor_candidate_contract,
)
from core.ai.contracts.diff_contract import DiffContract, fallback_diff_contract
from core.ai.contracts.ingest_contract import IngestContract, fallback_ingest_contract
from core.ai.contracts.rule_candidate_contract import (
    RuleCandidateContract,
    fallback_rule_candidate_contract,
)
from core.ai.contracts.transcript_contract import (
    TranscriptContract,
    fallback_transcript_contract,
)


CONTRACT_MODELS = {
    "ingest": IngestContract,
    "transcript": TranscriptContract,
    "diff": DiffContract,
    "rules": RuleCandidateContract,
    "anchor": AnchorCandidateContract,
}

FALLBACK_BUILDERS = {
    "ingest": fallback_ingest_contract,
    "transcript": fallback_transcript_contract,
    "diff": fallback_diff_contract,
    "rules": fallback_rule_candidate_contract,
    "anchor": fallback_anchor_candidate_contract,
}

