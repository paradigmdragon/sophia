from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.engine.schema import Episode, Backbone, Facet
from core.engine.constants import ChunkA, ChunkB, ChunkC, ChunkD

def search_episodes(
    session: Session,
    mask_a: Optional[int] = None,
    mask_b: Optional[int] = None,
    mask_c: Optional[int] = None,
    mask_d: Optional[int] = None,
    facet_filters: Optional[List[Dict[str, int]]] = None
) -> List[Episode]:
    """
    Stage 1: Backbone Mask Filter
    Stage 2: Facet Filter
    """
    
    # [Stage 1] Backbone Mask Search
    query = session.query(Episode).join(Backbone)
    
    backbone_conditions = []
    if mask_a is not None:
        # If mask is 0x3 (PROCESS), we want bits_a == 0x3
        # Supports bitwise matching if we store fuller bits, 
        # but for v0 phase, exact chunk match is primary use case.
        # Implemented as exact match for 4-bit chunks for now.
        backbone_conditions.append(Backbone.bits_a == mask_a)
    if mask_b is not None:
        backbone_conditions.append(Backbone.bits_b == mask_b)
    if mask_c is not None:
        backbone_conditions.append(Backbone.bits_c == mask_c)
    if mask_d is not None:
        backbone_conditions.append(Backbone.bits_d == mask_d)
    
    # Filter only non-deprecated backbones
    backbone_conditions.append(Backbone.deprecated == False)
    
    if backbone_conditions:
        query = query.filter(and_(*backbone_conditions))

    # [Stage 2] Facet Filter
    # Facet filter logic: AND across different facets. 
    # E.g. (Certainty=CONFIRMED) AND (Source=DOC)
    if facet_filters:
        for f in facet_filters:
            f_id = f.get('id')
            f_val = f.get('value')
            if f_id is not None and f_val is not None:
                # Subquery exist check for each facet condition
                # This ensures an episode has *this* facet
                # If multiple filters, it effectively ANDs them
                query = query.filter(
                    Episode.facets.any(
                        and_(Facet.facet_id == f_id, Facet.value == f_val)
                    )
                )

    return query.all()
