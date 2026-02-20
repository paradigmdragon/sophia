# 📌 Sophia BitValidator 설계 명세 (Draft v1.0)

## 1. 목적

BitValidator는 Sophia의 Bit-Hybrid Codebook v1.0에서 생성된 16비트 값(bits)이  
의미적·구조적·조합적으로 유효한지 검증하는 독립 모듈입니다.

이 모듈은 다음 역할을 수행합니다:
- 비트 조합 유효성 검사
- 조합 충돌 차단
- Codebook v1.0 정책 준수 강제
- SonE/Forest/AI 등 상위 시스템의 무결성 보장
- 저장/인덱싱 전 치환 또는 reject 처리

---

## 2. 입력/출력 정의

### 2.1 입력 객체

BitValidator는 **단순 정수 비트 값(0~65535)**만을 입력으로 받습니다.

```python
bits: int  # 0 <= bits <= 0xFFFF
```

### 2.2 출력 객체

검증이 성공하면 `ValidBitmapResult`를 반환하고, 실패하면 `InvalidBitmapError`를 throw 합니다.

```python
class ValidBitmapResult(BaseModel):
    bits: int                   # 동일 비트 값
    type: str                  # Chunk A label (ex: "MIND")
    facet: str                 # Chunk B label (ex: "DERIVED")
    status: str                # Chunk C label (ex: "ACTIVE")
    risk_level: int            # Chunk D integer 0~15
    valid: bool = True
```

오류 시:

```python
class InvalidBitmapError(Exception):
    message: str
    bits: int
    reason: str
```

---

## 3. 검증 규칙

### 3.1 Chunk 추출

Validator는 다음 연산으로 4개 chunk를 추출합니다:

```python
type_bits   = bits & 0xF000
facet_bits  = bits & 0x0F00
status_bits = bits & 0x00F0
risk_bits   = bits & 0x000F
```

---

## 4. 유효성 매트릭스

### 4.1 Type → Facet 유효성 (Whitelist 표기)

이 매트릭스는 허용 조합만 정의하고, 나머지는 명백한 오류로 간주합니다.

```yaml
# type_facet_matrix.yaml
TYPE_FACET_ALLOWLIST:
  DOMAIN:
    - RAW
    - DERIVED
    - VERIFIED
  STATE:
    - RAW
    - DERIVED
    - VERIFIED
    - TEMP
  ACTION:
    - DERIVED
    - TEMP
    - VERIFIED
  PRINCIPLE:
    - VERIFIED
    - USER_DEF
  CONCEPT:
    - RAW
    - DERIVED
    - VERIFIED
    - USER_DEF
  OBJECT:
    - RAW
    - DERIVED
    - VERIFIED
    - TEMP
  MIND:
    - DERIVED
    - TEMP
  USER:
    - USER_DEF
    - VERIFIED
  SYSTEM:
    - DERIVED
    - VERIFIED
```

---

## 5. Status 유효성

Status는 모든 Type에 대해 기본적으로 허용되지만, 유형별 강화 규칙은 아래와 같습니다:
- `STATUS.ERROR(0x00F0) → Type PRINCIPLE에서만 허용? → NO`
- 모든 Type에서 허용.

규칙:

```python
ALLOWED_STATUS = {
    0x0010,  # WAIT
    0x0020,  # ACTIVE
    0x0030,  # DONE
    0x0040,  # HOLD
    0x00E0,  # DEPRECATED
    0x00F0,  # ERROR
}
```

---

## 6. Risk 유효성

Risk는 단순 정수 레벨 0~15를 의미하며 플래그가 아님.

정의:

```python
0x0 ≤ risk_bits ≤ 0xF
```

추가 제약:
- `risk_bits == 0xF (FATAL) → Type must not be RAW/DERIVED`
- (절대 오류 상태에서 RAW/DERIVED는 의미 없음)

---

## 7. 설계 도식

```text
┌──────────────┬────────────┬─────────────┬───────────┐
│   Chunk A    │  Chunk B   │   Chunk C   │ Chunk D   │
├──────────────┼────────────┼─────────────┼───────────┤
│ TYPE         │ FACET      │ STATUS      │ RISK      │
│ [4 bit]      │ [4 bit]    │ [4 bit]     │ [4 bit]   │
└──────────────┴────────────┴─────────────┴───────────┘

bits = TYPE + FACET + STATUS + RISK
```

---

## 8. 구현 명세 (Python 기준)

### 8.1 Enum 정의

```python
from enum import IntEnum

class TypeBits(IntEnum):
    DOMAIN   = 0x1000
    STATE    = 0x2000
    ACTION   = 0x3000
    PRINCIPLE= 0x4000
    CONCEPT  = 0x5000
    OBJECT   = 0x6000
    MIND     = 0x7000
    USER     = 0x8000
    SYSTEM   = 0x9000

class FacetBits(IntEnum):
    RAW      = 0x0100
    DERIVED  = 0x0200
    USER_DEF = 0x0300
    VERIFIED = 0x0400
    DEBATED  = 0x0500
    TEMP     = 0x0600

class StatusBits(IntEnum):
    WAIT      = 0x0010
    ACTIVE    = 0x0020
    DONE      = 0x0030
    HOLD      = 0x0040
    DEPRECATED= 0x00E0
    ERROR     = 0x00F0
```

### 8.2 BitValidator Core Function

```python
def validate_bitmap(bits: int) -> ValidBitmapResult:
    # Extract chunks
    type_bits  = bits & 0xF000
    facet_bits = bits & 0x0F00
    status_bits= bits & 0x00F0
    risk_bits  = bits & 0x000F

    # Mandatory checks
    if type_bits not in TypeBits._value2member_map_:
        raise InvalidBitmapError(bits=bits, reason="INVALID_TYPE")

    if status_bits not in StatusBits._value2member_map_:
        raise InvalidBitmapError(bits=bits, reason="INVALID_STATUS")

    if not (0 <= risk_bits <= 0xF):
        raise InvalidBitmapError(bits=bits, reason="INVALID_RISK_LEVEL")

    # Facet allowlist check
    allowed_facets = TYPE_FACET_ALLOWLIST.get(TypeBits(type_bits).name, [])
    if facet_bits not in [FacetBits[f].value for f in allowed_facets]:
        raise InvalidBitmapError(bits=bits, reason="INVALID_FACET_FOR_TYPE")

    # Passed
    return ValidBitmapResult(
        bits=bits,
        type=TypeBits(type_bits).name,
        facet=FacetBits(facet_bits).name,
        status=StatusBits(status_bits).name,
        risk_level=risk_bits,
    )
```

---

## 9. 통합 포인트

### 9.1 DB 입력/업데이트

모든 신규/수정 bit 저장 전:

```python
validated = validate_bitmap(input_bits)
# store validated.bits
```

### 9.2 검색/필터

예:

```sql
SELECT * FROM mind_items WHERE bits & 0xF000 = 0x4000
```

## 10. 테스트 스펙

### 10.1 불변 테스트 (Pass)

```python
validate_bitmap(0x4324)  # PRINCIPLE+VERIFIED+DONE+risk=4
validate_bitmap(0x2311)  # STATE+RAW+WAIT+risk=1
```

### 10.2 실패 테스트 (Raise InvalidBitmapError)

```python
validate_bitmap(0x4123)  # PRINCIPLE+RAW (INVALID_FACET_FOR_TYPE)
validate_bitmap(0x900F)  # SYSTEM+VERIFIED+ERROR+risk=F (if forbidden)
validate_bitmap(0x0000)  # INVALID_TYPE
validate_bitmap(0x10FF)  # INVALID_STATUS
validate_bitmap(0x100F)  # risk out of range? (check)
```

---

## 11. 예외 메시지 표준

| 코드 | Meaning |
|---|---|
| INVALID_TYPE | TYPE not in codebook |
| INVALID_FACET_FOR_TYPE | Facet incompatible with Type |
| INVALID_STATUS | Status not in allowed set |
| INVALID_RISK_LEVEL | Risk outside 0~15 |

---

## 12. CodeDoc (Markdown) 향후 참조용

이 문서는 그대로 `docs/bit_validator.md`로 저장하십시오.  
지금부터 Sophia의 모든 비트와 관련된 유효성 검사는 이 명세를 기준으로 진행합니다.
