# Forest SonE Reason Codes v0.1

## 목적
- SonE 검증 결과를 점수만이 아니라 `근거 코드(reason_code)`로 표준화한다.
- Canopy/Report에서 위험 판정의 이유를 추적 가능하게 한다.

## 카탈로그 버전
- `sone_reason_v0_1`

## Reason Codes
- `SONE_SCOPE_MISSING`
  - category: `missing_slot`
  - meaning: 설계 범위(scope) 누락

- `SONE_SUCCESS_CONDITION_MISSING`
  - category: `missing_slot`
  - meaning: 성공 조건(success_condition) 누락

- `SONE_DEPENDENCY_UNSPECIFIED`
  - category: `dependency`
  - meaning: 영향 대상은 존재하나 의존 관계 서술 부족

- `SONE_REQUIREMENT_CONFLICT`
  - category: `conflict`
  - meaning: 충돌/모순 키워드 기반 충돌 가능성 감지

## 적용 지점
- Grove:
  - `core/forest/grove.py`
  - signals에 `reason_code`, `category`, `reason_description`, `evidence` 포함
  - slot에 `reason_codes[]` 포함
- Canopy:
  - `core/forest/canopy.py`
  - `sone_summary.missing_slots[]` 및 `sone_summary.risk_reasons[]`에 reason 정보 노출

## 출력 계약 (요약)
- `sone_summary.validation_stage`
- `sone_summary.reason_catalog_version`
- `sone_summary.missing_slots[].reason_code`
- `sone_summary.risk_reasons[].reason_code`
