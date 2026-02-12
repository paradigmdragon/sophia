from typing import List, Optional, Tuple, Dict
from core.engine.schema import Backbone, Facet, Episode
from core.engine.constants import ChunkA, ChunkC, ChunkD, FacetID, FacetValueCertainty, RuleID

def check_conflicts(episode: Episode) -> List[Dict]:
    """
    Mechanical Conflict Detection based on sophia_chunk_seed_values_v0.1.md
    
    Trigger: When an episode has multiple backbones.
    Logic: Pairwise check of ALL adopted backbones.
    """
    backbones = [b for b in episode.backbones if not b.deprecated]
    if len(backbones) < 2:
        return []

    conflicts = []
    
    # Pairwise comparison
    for i in range(len(backbones)):
        for j in range(i + 1, len(backbones)):
            b1 = backbones[i]
            b2 = backbones[j]
            
            # Rule 1: Chunk A (STATE vs PROCESS)
            # User Manual Override: v0.1.1 enforces this rule.
            val1_a = b1.bits_a
            val2_a = b2.bits_a
            if {val1_a, val2_a} == {ChunkA.STATE, ChunkA.PROCESS}:
                conflicts.append({
                    "rule_id": RuleID.A_STATE_PROCESS,
                    "backbone_pair": [b1.backbone_id, b2.backbone_id],
                    "chunk": "A",
                    "values": [val1_a, val2_a],
                    "descriptor": "STATE vs PROCESS"
                })

            # Rule 2: Chunk C (TIMELESS vs SNAPSHOT)
            # User Manual Override: v0.1.1 enforces this rule.
            val1_c = b1.bits_c
            val2_c = b2.bits_c
            if {val1_c, val2_c} == {ChunkC.TIMELESS, ChunkC.SNAPSHOT}:
                 conflicts.append({
                    "rule_id": RuleID.C_TIMELESS_SNAPSHOT,
                    "backbone_pair": [b1.backbone_id, b2.backbone_id],
                    "chunk": "C",
                    "values": [val1_c, val2_c],
                    "descriptor": "TIMELESS vs SNAPSHOT"
                })

            # Rule 3: Chunk D
            # EQUIVALENCE (0x6) vs OPPOSITIONAL (0x4)
            val1 = b1.bits_d
            val2 = b2.bits_d
            if {val1, val2} == {ChunkD.EQUIVALENCE, ChunkD.OPPOSITIONAL}:
                conflicts.append({
                    "rule_id": RuleID.D_EQUIVALENCE_OPPOSITIONAL,
                    "backbone_pair": [b1.backbone_id, b2.backbone_id],
                    "chunk": "D",
                    "values": [val1, val2],
                    "descriptor": "EQUIVALENCE vs OPPOSITIONAL"
                })

    return conflicts
