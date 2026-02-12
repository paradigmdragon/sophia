
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.engine.schema import Base, Episode, Backbone, Facet, Candidate, Event
from core.engine.constants import ChunkA, ChunkB, ChunkC, ChunkD, FacetID, FacetValueCertainty, FacetValueSource, RuleID
from core.engine.search import search_episodes
from core.engine.workflow import WorkflowEngine
from core.engine.encoder import CandidateEncoder

# Standalone execution support
if __name__ == "__main__":
    def db_session():
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        return session

    def test_create_episode_with_backbone(db_session):
        print("Testing Create Episode...")
        # 1. Create Episode
        ep = Episode(episode_id="ep_001", log_ref={"type": "memo", "uri": "memo1.md"})
        db_session.add(ep)
        
        # 2. Add Backbone (Process, Hypothetical, Sequence, Elemental)
        # A=3, B=5, C=4, D=2 (Compositional/Elemental map to 0x2)
        bb = Backbone(
            backbone_id="bb_001",
            episode_id="ep_001",
            bits_a=ChunkA.PROCESS,
            bits_b=ChunkB.HYPOTHETICAL,
            bits_c=ChunkC.SEQUENCE,
            bits_d=ChunkD.COMPOSITIONAL,
            combined_bits=(ChunkA.PROCESS << 12) | (ChunkB.HYPOTHETICAL << 8) | (ChunkC.SEQUENCE << 4) | (ChunkD.COMPOSITIONAL),
            role="PRIMARY"
        )
        db_session.add(bb)
        
        # 3. Add Facet (Certainty=PENDING)
        facet = Facet(
            facet_uuid="f_001",
            episode_id="ep_001",
            facet_id=FacetID.CERTAINTY,
            value=FacetValueCertainty.PENDING
        )
        db_session.add(facet)
        db_session.commit()
        
        assert db_session.query(Episode).count() == 1
        assert db_session.query(Backbone).count() == 1
        print("PASS")

    def test_search_backbone_mask(db_session):
        print("Testing Backbone Mask Search...")
        # Target: A=PROCESS (0x3)
        ep1 = Episode(episode_id="ep_target", log_ref={})
        bb1 = Backbone(
            backbone_id="bb_t", episode_id="ep_target",
            bits_a=ChunkA.PROCESS, bits_b=0, bits_c=0, bits_d=0, combined_bits=0x3000, role="PRIMARY"
        )
        
        # Noise: A=STATE (0x1)
        ep2 = Episode(episode_id="ep_noise", log_ref={})
        bb2 = Backbone(
            backbone_id="bb_n", episode_id="ep_noise",
            bits_a=ChunkA.STATE, bits_b=0, bits_c=0, bits_d=0, combined_bits=0x1000, role="PRIMARY"
        )
        
        db_session.add_all([ep1, bb1, ep2, bb2])
        db_session.commit()
        
        # Search Mask A=PROCESS
        results = search_episodes(db_session, mask_a=ChunkA.PROCESS)
        assert len(results) == 1
        assert results[0].episode_id == "ep_target"
        print("PASS")

    def test_search_facet_filter(db_session):
        print("Testing Facet Filter Search...")
        # Target: Confirmed
        ep1 = Episode(episode_id="ep_conf", log_ref={})
        bb1 = Backbone(backbone_id="bb_c", episode_id="ep_conf", bits_a=0, bits_b=0, bits_c=0, bits_d=0, combined_bits=0, role="PRIMARY")
        f1 = Facet(facet_uuid="f1", episode_id="ep_conf", facet_id=FacetID.CERTAINTY, value=FacetValueCertainty.CONFIRMED)
        
        # Noise: Pending
        ep2 = Episode(episode_id="ep_pend", log_ref={})
        bb2 = Backbone(backbone_id="bb_p", episode_id="ep_pend", bits_a=0, bits_b=0, bits_c=0, bits_d=0, combined_bits=0, role="PRIMARY")
        f2 = Facet(facet_uuid="f2", episode_id="ep_pend", facet_id=FacetID.CERTAINTY, value=FacetValueCertainty.PENDING)
        
        db_session.add_all([ep1, bb1, f1, ep2, bb2, f2])
        db_session.commit()
        
        # Filter: Certainty=CONFIRMED
        results = search_episodes(db_session, facet_filters=[{'id': FacetID.CERTAINTY, 'value': FacetValueCertainty.CONFIRMED}])
        assert len(results) == 1
        assert results[0].episode_id == "ep_conf"
        print("PASS")

    def test_mixed_search(db_session):
        print("Testing Mixed Search...")
        # Target: A=EVENT + Source=DOC
        ep1 = Episode(episode_id="ep_mix", log_ref={})
        bb1 = Backbone(backbone_id="bb_m", episode_id="ep_mix", bits_a=ChunkA.EVENT, bits_b=0, bits_c=0, bits_d=0, combined_bits=0x2000, role="PRIMARY")
        f1 = Facet(facet_uuid="f_src", episode_id="ep_mix", facet_id=FacetID.SOURCE, value=FacetValueSource.DOCUMENT)
        
        db_session.add_all([ep1, bb1, f1])
        db_session.commit()
        
        # Match
        results = search_episodes(
            db_session, 
            mask_a=ChunkA.EVENT, 
            facet_filters=[{'id': FacetID.SOURCE, 'value': FacetValueSource.DOCUMENT}]
        )
        assert len(results) == 1
        
        # Mismatch Mask
        results_fail_mask = search_episodes(
            db_session, 
            mask_a=ChunkA.STATE, 
            facet_filters=[{'id': FacetID.SOURCE, 'value': FacetValueSource.DOCUMENT}]
        )
        assert len(results_fail_mask) == 0

        # Mismatch Facet
        results_fail_facet = search_episodes(
            db_session, 
            mask_a=ChunkA.EVENT, 
            facet_filters=[{'id': FacetID.SOURCE, 'value': FacetValueSource.CONVERSATION}]
        )
        assert len(results_fail_facet) == 0
        print("PASS")

    # Run tests manually
    s = db_session()
    test_create_episode_with_backbone(s)
    s.close()
    
    s = db_session()
    test_search_backbone_mask(s)
    s.close()

    s = db_session()
    test_search_facet_filter(s)
    s.close()

    s = db_session()
    test_mixed_search(s)
    s.close()

    def test_workflow_cycle(db_session):
        print("Testing Workflow Cycle (Ingest -> Propose -> Adopt -> Conflict)...")
        workflow = WorkflowEngine(lambda: db_session)
        encoder = CandidateEncoder()
        
        # 1. Ingest
        ep_id = workflow.ingest({"type": "chat", "uri": "chat_001"})
        assert ep_id.startswith("ep_")
        print(f"  Ingested: {ep_id}")
        
        # 2. Propose (via Encoder)
        text = "This is a project plan for Sophia."
        candidates_data = encoder.generate_candidates(text)
        c_ids = workflow.propose(ep_id, candidates_data)
        assert len(c_ids) >= 1
        print(f"  Proposed {len(c_ids)} candidates: {c_ids}")
        
        # 3. Adopt (Primary)
        # Verify status before adopt
        s = db_session
        ep = s.query(Episode).filter_by(episode_id=ep_id).first()
        assert ep.status == 'UNDECIDED'
        
        bb_id_1 = workflow.adopt(ep_id, c_ids[0])
        print(f"  Adopted Primary: {bb_id_1}")
        
        # Verify status after adopt
        ep = s.query(Episode).filter_by(episode_id=ep_id).first()
        assert ep.status == 'DECIDED'
        bb1 = s.query(Backbone).filter_by(backbone_id=bb_id_1).first()
        assert bb1.role == 'PRIMARY'
        
        # 4. Propose & Adopt Alternative (Conflict Check)
        # Create a conflicting candidate (D=OPPOSITIONAL vs D=EQUIVALENCE)
        # Assume bb1 has D=COMPOSITIONAL (0x2). Let's force a conflict pair.
        # Actually encoder for "plan" gave D=COMPOSITIONAL (0x2).
        # Rule D_EQUIVALENCE_OPPOSITIONAL check 0x6 vs 0x4.
        
        # Let's verify Conflict Trigger:
        # We need two backbones with encoded D=0x6 (EQUIV) and D=0x4 (OPPOS).
        
        # Inject custom candidates for conflict test
        conflicting_candidates = [
            {
                "backbone_bits": (ChunkD.EQUIVALENCE), 
                "facets": [{"id": FacetID.CERTAINTY, "value": FacetValueCertainty.PENDING}],
                "note": "Force Equivalence"
            },
            {
                "backbone_bits": (ChunkD.OPPOSITIONAL), 
                "facets": [{"id": FacetID.CERTAINTY, "value": FacetValueCertainty.PENDING}],
                "note": "Force Opposition"
            }
        ]
        
        c_ids_conflict = workflow.propose(ep_id, conflicting_candidates, source="human_test")
        
        # Adopt EQUIV (Alternative 1)
        workflow.adopt(ep_id, c_ids_conflict[0])
        
        # Adopt OPPOS (Alternative 2) -> Should trigger conflict with Alt 1
        workflow.adopt(ep_id, c_ids_conflict[1])
        
        # Check for Conflict Event
        events = s.query(Event).filter_by(episode_id=ep_id, type="CONFLICT_MARK").all()
        assert len(events) > 0
        print(f"  Conflict Detected! Event payload: {events[-1].payload}")
        
        # Check Facet Update
        facet = s.query(Facet).filter_by(episode_id=ep_id, facet_id=FacetID.CERTAINTY).first()
        assert facet.value == FacetValueCertainty.CONFLICT
        print("  Facet updated to CONFLICT usage.")
        
        print("PASS")

    # Run Workflow Test
    s_factory = db_session 
    # Use a fresh session wrapper for the workflow test to simulate app behavior
    # But here db_session is a function returning a new session bound to in-memory engine
    # We need to share the engine state.
    
    # Fix: db_session in main block creates a NEW memory db each time.
    # We need a persistent engine for the test sequence.
    
    engine_persistent = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine_persistent)
    SessionPersistent = sessionmaker(bind=engine_persistent)
    
    def get_persistent_session():
        return SessionPersistent()
        
    test_workflow_cycle(get_persistent_session())



def test_create_episode_with_backbone(db_session):
    # 1. Create Episode
    ep = Episode(episode_id="ep_001", log_ref={"type": "memo", "uri": "memo1.md"})
    db_session.add(ep)
    
    # 2. Add Backbone (Process, Hypothetical, Sequence, Elemental)
    # A=3, B=5, C=4, D=2 (Compositional/Elemental map to 0x2)
    bb = Backbone(
        backbone_id="bb_001",
        episode_id="ep_001",
        bits_a=ChunkA.PROCESS,
        bits_b=ChunkB.HYPOTHETICAL,
        bits_c=ChunkC.SEQUENCE,
        bits_d=ChunkD.COMPOSITIONAL,
        combined_bits=(ChunkA.PROCESS << 12) | (ChunkB.HYPOTHETICAL << 8) | (ChunkC.SEQUENCE << 4) | (ChunkD.COMPOSITIONAL),
        role="PRIMARY"
    )
    db_session.add(bb)
    
    # 3. Add Facet (Certainty=PENDING)
    facet = Facet(
        facet_uuid="f_001",
        episode_id="ep_001",
        facet_id=FacetID.CERTAINTY,
        value=FacetValueCertainty.PENDING
    )
    db_session.add(facet)
    db_session.commit()
    
    assert db_session.query(Episode).count() == 1
    assert db_session.query(Backbone).count() == 1

def test_search_backbone_mask(db_session):
    # Target: A=PROCESS (0x3)
    ep1 = Episode(episode_id="ep_target", log_ref={})
    bb1 = Backbone(
        backbone_id="bb_t", episode_id="ep_target",
        bits_a=ChunkA.PROCESS, bits_b=0, bits_c=0, bits_d=0, combined_bits=0x3000, role="PRIMARY"
    )
    
    # Noise: A=STATE (0x1)
    ep2 = Episode(episode_id="ep_noise", log_ref={})
    bb2 = Backbone(
        backbone_id="bb_n", episode_id="ep_noise",
        bits_a=ChunkA.STATE, bits_b=0, bits_c=0, bits_d=0, combined_bits=0x1000, role="PRIMARY"
    )
    
    db_session.add_all([ep1, bb1, ep2, bb2])
    db_session.commit()
    
    # Search Mask A=PROCESS
    results = search_episodes(db_session, mask_a=ChunkA.PROCESS)
    assert len(results) == 1
    assert results[0].episode_id == "ep_target"

def test_search_facet_filter(db_session):
    # Target: Confirmed
    ep1 = Episode(episode_id="ep_conf", log_ref={})
    bb1 = Backbone(backbone_id="bb_c", episode_id="ep_conf", bits_a=0, bits_b=0, bits_c=0, bits_d=0, combined_bits=0, role="PRIMARY")
    f1 = Facet(facet_uuid="f1", episode_id="ep_conf", facet_id=FacetID.CERTAINTY, value=FacetValueCertainty.CONFIRMED)
    
    # Noise: Pending
    ep2 = Episode(episode_id="ep_pend", log_ref={})
    bb2 = Backbone(backbone_id="bb_p", episode_id="ep_pend", bits_a=0, bits_b=0, bits_c=0, bits_d=0, combined_bits=0, role="PRIMARY")
    f2 = Facet(facet_uuid="f2", episode_id="ep_pend", facet_id=FacetID.CERTAINTY, value=FacetValueCertainty.PENDING)
    
    db_session.add_all([ep1, bb1, f1, ep2, bb2, f2])
    db_session.commit()
    
    # Filter: Certainty=CONFIRMED
    results = search_episodes(db_session, facet_filters=[{'id': FacetID.CERTAINTY, 'value': FacetValueCertainty.CONFIRMED}])
    assert len(results) == 1
    assert results[0].episode_id == "ep_conf"

def test_mixed_search(db_session):
    # Target: A=EVENT + Source=DOC
    ep1 = Episode(episode_id="ep_mix", log_ref={})
    bb1 = Backbone(backbone_id="bb_m", episode_id="ep_mix", bits_a=ChunkA.EVENT, bits_b=0, bits_c=0, bits_d=0, combined_bits=0x2000, role="PRIMARY")
    f1 = Facet(facet_uuid="f_src", episode_id="ep_mix", facet_id=FacetID.SOURCE, value=FacetValueSource.DOCUMENT)
    
    db_session.add_all([ep1, bb1, f1])
    db_session.commit()
    
    # Match
    results = search_episodes(
        db_session, 
        mask_a=ChunkA.EVENT, 
        facet_filters=[{'id': FacetID.SOURCE, 'value': FacetValueSource.DOCUMENT}]
    )
    assert len(results) == 1
    
    # Mismatch Mask
    results_fail_mask = search_episodes(
        db_session, 
        mask_a=ChunkA.STATE, 
        facet_filters=[{'id': FacetID.SOURCE, 'value': FacetValueSource.DOCUMENT}]
    )
    assert len(results_fail_mask) == 0

    # Mismatch Facet
    results_fail_facet = search_episodes(
        db_session, 
        mask_a=ChunkA.EVENT, 
        facet_filters=[{'id': FacetID.SOURCE, 'value': FacetValueSource.CONVERSATION}]
    )
    assert len(results_fail_facet) == 0
