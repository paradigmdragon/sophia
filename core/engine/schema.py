from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    ForeignKey,
    JSON,
    DateTime,
    create_engine,
    Index
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

class Episode(Base):
    __tablename__ = 'episodes'

    episode_id = Column(String, primary_key=True)
    status = Column(String, default='UNDECIDED')  # UNDECIDED, DECIDED
    log_ref = Column(JSON, nullable=False)        # {type, uri, range}
    created_at = Column(DateTime, default=func.now())

    # Relationships
    backbones = relationship("Backbone", back_populates="episode")
    facets = relationship("Facet", back_populates="episode")
    candidates = relationship("Candidate", back_populates="episode")
    events = relationship("Event", back_populates="episode")

class Backbone(Base):
    __tablename__ = 'backbones'

    backbone_id = Column(String, primary_key=True)
    episode_id = Column(String, ForeignKey('episodes.episode_id'), nullable=False)
    
    # 16-bit breakdown for efficient masking
    bits_a = Column(Integer, nullable=False) # Chunk A (4-bit)
    bits_b = Column(Integer, nullable=False) # Chunk B (4-bit)
    bits_c = Column(Integer, nullable=False) # Chunk C (4-bit)
    bits_d = Column(Integer, nullable=False) # Chunk D (4-bit)
    
    # Combined for easy retrieval
    combined_bits = Column(Integer, nullable=False) # 16-bit value

    role = Column(String, nullable=False)     # PRIMARY, ALTERNATIVE
    origin = Column(String, default="ADOPT")  # ADOPT
    resolution = Column(Integer, default=16)  # 16
    deprecated = Column(Boolean, default=False)
    adopted_at = Column(DateTime, default=func.now())

    episode = relationship("Episode", back_populates="backbones")

    # Indices for Bitmask Search (Stage 1)
    __table_args__ = (
        Index('idx_backbone_a', 'bits_a'),
        Index('idx_backbone_b', 'bits_b'),
        Index('idx_backbone_c', 'bits_c'),
        Index('idx_backbone_d', 'bits_d'),
        Index('idx_episode_role', 'episode_id', 'role'),
    )

class Facet(Base):
    __tablename__ = 'facets'

    facet_uuid = Column(String, primary_key=True) # UUID for unique row
    episode_id = Column(String, ForeignKey('episodes.episode_id'), nullable=False)
    
    facet_id = Column(Integer, nullable=False) # 4-bit (0x1~0xF)
    value = Column(Integer, nullable=False)    # 4-bit (0x0~0xF)

    episode = relationship("Episode", back_populates="facets")

    # Indices for Facet Filter (Stage 2)
    __table_args__ = (
        Index('idx_facet_lookup', 'facet_id', 'value'),
    )

class Candidate(Base):
    __tablename__ = 'candidates'

    candidate_id = Column(String, primary_key=True)
    episode_id = Column(String, ForeignKey('episodes.episode_id'), nullable=False)
    
    proposed_by = Column(String, nullable=False) # encoder, user
    backbone_bits = Column(Integer, nullable=False)
    facets_json = Column(JSON, nullable=False)   # List of {id, val}
    confidence = Column(Integer, default=0)
    status = Column(String, default='PENDING')   # PENDING, ADOPTED, REJECTED
    proposed_at = Column(DateTime, default=func.now())
    note_thin = Column(String, nullable=True)

    episode = relationship("Episode", back_populates="candidates")

    __table_args__ = (
        Index('idx_candidate_episode_status', 'episode_id', 'status'),
        Index('idx_candidate_proposed_at', 'proposed_at'),
    )

class Event(Base):
    """
    Append-only Event Log
    """
    __tablename__ = 'events'

    event_id = Column(String, primary_key=True)
    episode_id = Column(String, ForeignKey('episodes.episode_id'), nullable=True)
    
    type = Column(String, nullable=False) # INGEST, PROPOSE, ADOPT, REJECT, DEPRECATE, CONFLICT_MARK
    payload = Column(JSON, nullable=False)
    at = Column(DateTime, default=func.now())

    episode = relationship("Episode", back_populates="events")

    __table_args__ = (
        Index('idx_event_type_at', 'type', 'at'),
        Index('idx_event_episode_type_at', 'episode_id', 'type', 'at'),
    )

class MessageQueue(Base):
    __tablename__ = 'message_queue'
    message_id = Column(String, primary_key=True)
    episode_id = Column(String, ForeignKey('episodes.episode_id'), nullable=True) # Optional context
    priority = Column(String, nullable=False) # P1, P2, P3, P4
    type = Column(String, nullable=False) # ASK, CONFIRM, NOTICE, EXPORT_REQUEST
    sone_intent = Column(String, nullable=False) # e.g. "conflict_check", "low_confidence"
    content = Column(String, nullable=False) # Human readable message or template code
    required_context = Column(JSON, nullable=True) # {session_state: "...", must_match_chunk: ...}
    status = Column(String, default='PENDING') # PENDING, SERVED, DISMISSED, HOLD
    created_at = Column(DateTime, default=func.now())

    # Indices for Dispatcher
    __table_args__ = (
        Index('idx_mq_priority_status', 'priority', 'status'),
        Index('idx_mq_created_at', 'created_at'),
    )

def init_db(db_path: str = 'sqlite:///sophia.db'):
    engine = create_engine(db_path)
    Base.metadata.create_all(engine)
    return engine
