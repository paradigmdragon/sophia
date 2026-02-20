import pytest

from core.engine.bitmap_validator import InvalidBitmapError, validate_bitmap
from core.engine.constants import ChunkA, ChunkB, ChunkC, ChunkD
from core.engine.schema import Base, Candidate, Event
from core.engine.workflow import WorkflowEngine
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _bits(a: int, b: int, c: int, d: int) -> int:
    return ((a & 0xF) << 12) | ((b & 0xF) << 8) | ((c & 0xF) << 4) | (d & 0xF)


def test_validate_bitmap_accepts_known_chunks():
    bits = _bits(ChunkA.PROCESS, ChunkB.HYPOTHETICAL, ChunkC.SEQUENCE, ChunkD.COMPOSITIONAL)
    result = validate_bitmap(bits)
    assert result.bits == bits
    assert result.bits_a == int(ChunkA.PROCESS)
    assert result.bits_b == int(ChunkB.HYPOTHETICAL)
    assert result.bits_c == int(ChunkC.SEQUENCE)
    assert result.bits_d == int(ChunkD.COMPOSITIONAL)


def test_validate_bitmap_accepts_unknown_zero_chunks():
    result = validate_bitmap(0x0000)
    assert result.bits == 0x0000
    assert result.bits_a == 0
    assert result.bits_b == 0
    assert result.bits_c == 0
    assert result.bits_d == 0


@pytest.mark.parametrize(
    "bits, reason",
    [
        (_bits(0xF, 0x0, 0x0, 0x0), "INVALID_CHUNK_A"),
        (_bits(0x0, 0xF, 0x0, 0x0), "INVALID_CHUNK_B"),
        (_bits(0x0, 0x0, 0xF, 0x0), "INVALID_CHUNK_C"),
        (_bits(0x0, 0x0, 0x0, 0xF), "INVALID_CHUNK_D"),
    ],
)
def test_validate_bitmap_rejects_reserved_chunks(bits: int, reason: str):
    with pytest.raises(InvalidBitmapError) as exc:
        validate_bitmap(bits)
    assert exc.value.reason == reason


def test_validate_bitmap_rejects_out_of_range():
    with pytest.raises(InvalidBitmapError) as exc:
        validate_bitmap(0x1_0000)
    assert exc.value.reason == "INVALID_RANGE"


def test_workflow_propose_rejects_invalid_bitmap_before_storage():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)

    workflow = WorkflowEngine(lambda: SessionFactory())
    episode_id = workflow.ingest({"type": "test", "uri": "memory://test"})

    with pytest.raises(ValueError, match="invalid backbone_bits"):
        workflow.propose(
            episode_id,
            [
                {
                    "backbone_bits": 0xF000,  # INVALID_CHUNK_A
                    "facets": [],
                    "note": "invalid candidate",
                    "confidence": 90,
                }
            ],
            source="test",
        )

    session = SessionFactory()
    try:
        events = session.query(Event).filter(Event.type == "BITMAP_INVALID").all()
        assert len(events) == 1
        payload = events[0].payload or {}
        assert payload.get("stage") == "propose"
        assert payload.get("reason") == "INVALID_CHUNK_A"
    finally:
        session.close()


def test_workflow_propose_invalid_bitmap_does_not_persist_candidates():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    workflow = WorkflowEngine(lambda: SessionFactory())
    episode_id = workflow.ingest({"type": "test", "uri": "memory://test"})

    valid_bits = _bits(ChunkA.PROCESS, ChunkB.HYPOTHETICAL, ChunkC.SEQUENCE, ChunkD.COMPOSITIONAL)
    with pytest.raises(ValueError, match="invalid backbone_bits"):
        workflow.propose(
            episode_id,
            [
                {"backbone_bits": valid_bits, "facets": [], "note": "valid", "confidence": 90},
                {"backbone_bits": 0xF000, "facets": [], "note": "invalid", "confidence": 90},
            ],
            source="test",
        )

    session = SessionFactory()
    try:
        count = session.query(Candidate).count()
        assert count == 0
    finally:
        session.close()


def test_workflow_adopt_rejects_invalid_legacy_bitmap_and_logs_event():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    workflow = WorkflowEngine(lambda: SessionFactory())
    episode_id = workflow.ingest({"type": "test", "uri": "memory://test"})

    session = SessionFactory()
    try:
        candidate_id = "cand_invalid_legacy"
        session.add(
            Candidate(
                candidate_id=candidate_id,
                episode_id=episode_id,
                proposed_by="legacy",
                backbone_bits=0xF000,
                facets_json=[],
                confidence=75,
                status="PENDING",
                note_thin="legacy invalid",
            )
        )
        session.commit()
    finally:
        session.close()

    with pytest.raises(ValueError, match="invalid backbone_bits for adopt"):
        workflow.adopt(episode_id, candidate_id)

    session = SessionFactory()
    try:
        events = session.query(Event).filter(Event.type == "BITMAP_INVALID").all()
        assert len(events) == 1
        payload = events[0].payload or {}
        assert payload.get("stage") == "adopt"
        assert payload.get("candidate_id") == candidate_id
        assert payload.get("reason") == "INVALID_CHUNK_A"
    finally:
        session.close()
