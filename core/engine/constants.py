from enum import IntEnum, unique

@unique
class ChunkA(IntEnum):
    """
    Chunk A: Existence Mode (Presence) - 4 bit
    'What is the mode of being?'
    """
    UNKNOWN = 0x0             # 미정
    STATE = 0x1               # 정적 상태 (Being)
    EVENT = 0x2               # 이산적 발생 (Happening)
    PROCESS = 0x3             # 연속적 흐름 (Becoming)
    PRINCIPLE = 0x4           # 원칙/규칙/공리 (Actionable)
    CONCEPT = 0x5             # 추상적 관념 (Referenceable)
    ARTIFACT = 0x6            # 구조물/산출물 (Made)
    RELATION_BUNDLE = 0x7     # 관계 자체가 주제인 경우
    # 0x8~0xF: RESERVED

@unique
class ChunkB(IntEnum):
    """
    Chunk B: Perspective Mode (Viewpoint) - 4 bit
    'Whose view is this?'
    """
    UNKNOWN = 0x0             # 미정
    FIRST_PERSON = 0x1        # 본인 (User)
    OBSERVED = 0x2            # 관찰 (User saw X)
    REPORTED = 0x3            # 전달 (Third-party said X)
    STRUCTURAL = 0x4          # 구조적 기술 (Subject invisible)
    HYPOTHETICAL = 0x5        # 가정/시나리오 (If X)
    EXTERNAL = 0x6            # 타자/외부 시점 (Third-party claim)
    REFLECTIVE = 0x7          # 메타 인식 (Thinking about thinking)
    # 0x8~0xF: RESERVED

@unique
class ChunkC(IntEnum):
    """
    Chunk C: Temporal Mode (Time) - 4 bit
    'What is the temporal nature?'
    """
    UNKNOWN = 0x0             # 미정
    TIMELESS = 0x1            # 시간 독립 (Universal)
    SNAPSHOT = 0x2            # 특정 시점 (Point)
    DURATION = 0x3            # 구간 (Interval)
    SEQUENCE = 0x4            # 순서 (Step)
    RECURRING = 0x5           # 반복 (Cycle)
    TRANSITIONAL = 0x6        # 전환 (Shift)
    # 0x7~0xF: RESERVED

@unique
class ChunkD(IntEnum):
    """
    Chunk D: Relation Structure (Logic) - 4 bit
    'How are targets combined?'
    """
    UNKNOWN = 0x0             # 미정
    CAUSAL = 0x1              # 인과 (Since A, B)
    COMPOSITIONAL = 0x2       # 구성 (A consists of B)
    SEQUENTIAL = 0x3          # 순차 (A then B)
    OPPOSITIONAL = 0x4        # 대립 (A vs B)
    CONDITIONAL = 0x5         # 조건 (If A then B)
    EQUIVALENCE = 0x6         # 동치 (A is B)
    ATTRIBUTE = 0x7           # 속성 (A has B)
    DEPENDENCY = 0x8          # 의존 (B depends on A)
    # 0x9~0xF: RESERVED

@unique
class FacetID(IntEnum):
    """
    Facet ID - 4 bit
    Meta-information about the backbone
    """
    CERTAINTY = 0x1           # 확신 상태
    ABSTRACTION = 0x2         # 추상화 수준
    SOURCE = 0x3              # 출처 유형
    ALIGNMENT = 0x4           # Epidora Alignment Code

@unique
class FacetValueCertainty(IntEnum):
    """Facet 0x1 Values"""
    UNKNOWN = 0x0
    PENDING = 0x1             # 후보 (Candidate)
    CONFIRMED = 0x2           # 확정 (Adopted)
    CONFLICT = 0x3            # 충돌 (Mechanical Conflict)

@unique
class FacetValueAbstraction(IntEnum):
    """Facet 0x2 Values"""
    UNKNOWN = 0x0
    AXIOM = 0x1               # 공리/원칙
    PATTERN = 0x2             # 패턴/경향
    INSTANCE = 0x3            # 구체적 사례

@unique
class FacetValueSource(IntEnum):
    """Facet 0x3 Values"""
    UNKNOWN = 0x0
    CONVERSATION = 0x1        # 대화
    DOCUMENT = 0x2            # 문서
    MEMO = 0x3                # 메모
    EXTERNAL = 0x4            # 외부 출처

# Facet 0x4 Alignment values are 0x1~0x6 mapping to EPI-01~06 directly.

@unique
class RuleID(IntEnum):
    """
    Incompatibility Rules (Mechanical)
    """
    # Chunk A Rules (None in v1.1)
    
    # Chunk C Rules (None in v1.1 due to patch)
    
    # Chunk D Rules
    D_EQUIVALENCE_OPPOSITIONAL = 0xD1 # 0x6 vs 0x4
