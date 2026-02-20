from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.engine.constants import ChunkA, ChunkB, ChunkC, ChunkD
from core.engine.schema import Backbone, Base, Candidate, Event
from core.engine.workflow import WorkflowEngine


def _bits(a: int, b: int, c: int, d: int) -> int:
    return ((a & 0xF) << 12) | ((b & 0xF) << 8) | ((c & 0xF) << 4) | (d & 0xF)


def _build_workflow():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    return WorkflowEngine(lambda: session_factory()), session_factory


def test_adopt_is_idempotent_for_already_adopted_candidate():
    workflow, session_factory = _build_workflow()
    episode_id = workflow.ingest({"type": "test", "uri": "memory://idempotent-adopt"})
    bits = _bits(ChunkA.PROCESS, ChunkB.HYPOTHETICAL, ChunkC.SEQUENCE, ChunkD.COMPOSITIONAL)
    [candidate_id] = workflow.propose(
        episode_id,
        [{"backbone_bits": bits, "facets": [], "note": "", "confidence": 80}],
        source="test",
    )

    first_backbone_id = workflow.adopt(episode_id, candidate_id)
    second_backbone_id = workflow.adopt(episode_id, candidate_id)
    assert second_backbone_id == first_backbone_id

    session = session_factory()
    try:
        adopt_events = session.query(Event).filter(Event.type == "ADOPT").all()
        backbones = session.query(Backbone).all()
        candidate = session.query(Candidate).filter_by(candidate_id=candidate_id).one()
        assert len(adopt_events) == 1
        assert len(backbones) == 1
        assert str(candidate.status).upper() == "ADOPTED"
    finally:
        session.close()


def test_reject_is_idempotent_and_reason_is_recorded_once():
    workflow, session_factory = _build_workflow()
    episode_id = workflow.ingest({"type": "test", "uri": "memory://idempotent-reject"})
    bits = _bits(ChunkA.PROCESS, ChunkB.HYPOTHETICAL, ChunkC.SEQUENCE, ChunkD.COMPOSITIONAL)
    [candidate_id] = workflow.propose(
        episode_id,
        [{"backbone_bits": bits, "facets": [], "note": "", "confidence": 70}],
        source="test",
    )

    changed_first = workflow.reject(episode_id, candidate_id, reason="manual_reject_ui")
    changed_second = workflow.reject(episode_id, candidate_id, reason="manual_reject_ui")
    assert changed_first is True
    assert changed_second is False

    session = session_factory()
    try:
        reject_events = session.query(Event).filter(Event.type == "REJECT").all()
        assert len(reject_events) == 1
        payload = reject_events[0].payload or {}
        assert payload.get("candidate_id") == candidate_id
        assert payload.get("reason") == "manual_reject_ui"
    finally:
        session.close()


def test_invalid_transition_adopt_after_reject_and_reject_after_adopt():
    workflow, _session_factory = _build_workflow()
    episode_id = workflow.ingest({"type": "test", "uri": "memory://invalid-transition"})
    bits = _bits(ChunkA.PROCESS, ChunkB.HYPOTHETICAL, ChunkC.SEQUENCE, ChunkD.COMPOSITIONAL)
    [candidate_reject_first] = workflow.propose(
        episode_id,
        [{"backbone_bits": bits, "facets": [], "note": "", "confidence": 60}],
        source="test",
    )
    workflow.reject(episode_id, candidate_reject_first, reason="manual_reject_ui")

    [candidate_adopt_first] = workflow.propose(
        episode_id,
        [{"backbone_bits": bits, "facets": [], "note": "", "confidence": 60}],
        source="test",
    )
    workflow.adopt(episode_id, candidate_adopt_first)

    try:
        workflow.adopt(episode_id, candidate_reject_first)
        assert False, "adopt must fail for rejected candidate"
    except ValueError as exc:
        assert "REJECTED" in str(exc).upper()

    try:
        workflow.reject(episode_id, candidate_adopt_first)
        assert False, "reject must fail for adopted candidate"
    except ValueError as exc:
        assert "ADOPTED" in str(exc).upper()


def test_adopt_reject_block_cross_episode_candidate_mismatch():
    workflow, session_factory = _build_workflow()
    episode_a = workflow.ingest({"type": "test", "uri": "memory://episode-a"})
    episode_b = workflow.ingest({"type": "test", "uri": "memory://episode-b"})
    bits = _bits(ChunkA.PROCESS, ChunkB.HYPOTHETICAL, ChunkC.SEQUENCE, ChunkD.COMPOSITIONAL)
    [candidate_id] = workflow.propose(
        episode_a,
        [{"backbone_bits": bits, "facets": [], "note": "", "confidence": 60}],
        source="test",
    )

    try:
        workflow.adopt(episode_b, candidate_id)
        assert False, "adopt must fail for episode mismatch"
    except ValueError as exc:
        assert "EPISODE MISMATCH" in str(exc).upper()

    try:
        workflow.reject(episode_b, candidate_id, reason="manual_reject_ui")
        assert False, "reject must fail for episode mismatch"
    except ValueError as exc:
        assert "EPISODE MISMATCH" in str(exc).upper()

    session = session_factory()
    try:
        candidate = session.query(Candidate).filter_by(candidate_id=candidate_id).one()
        assert str(candidate.status).upper() == "PENDING"

        adopt_events = session.query(Event).filter(Event.type == "ADOPT").all()
        reject_events = session.query(Event).filter(Event.type == "REJECT").all()
        assert len(adopt_events) == 0
        assert len(reject_events) == 0
    finally:
        session.close()
