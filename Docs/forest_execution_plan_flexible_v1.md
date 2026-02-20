# Sophia Forest 실행 마스터플랜 (Flexible Phase SSOT v1)

## 0. 문서 목적
- 이 문서는 Forest 구현의 **Phase 중심 기준점(1/2/3)** 이다.
- 세부 작업은 `1.1 / 1.2 / 2.1 ...` 형태로 유연하게 추가한다.
- 어떤 작업을 하더라도 본 문서의 원칙과 Gate를 통과해야 한다.

## 1. North Star (원점)
- Forest는 `설계-검토-상태 관제` 시스템이다.
- SonE는 검증용 IR 캐시다(원문 저장소가 아님).
- Forest가 보여줘야 하는 것:
  - 무엇이 진행 중인가
  - 무엇이 막혀 있는가
  - 무엇이 위험한가
  - 다음 실행 우선순위가 무엇인가
- Forest가 기본으로 다루지 않는 것:
  - 사용자 학습 성장 지표(별도 뷰)
  - 자동 IDE 실행

## 2. 실행 프레임: Phase / Subphase

### Phase 1. 관제탑 정렬 (Control Tower Alignment)
목표:
- 1화면에서 현재 상태를 빠르게 판단할 수 있게 만든다.

범위:
- UI 정보 위계 고정
- Forest 경계(관제 vs 학습) 고정
- 기본 DoD/테스트 기준 고정

DoD:
- Canopy 데이터 기본 계약 유지:
  - `module_overview`, `roadmap`, `sone_summary`, `question_queue`, `recent_events`
- `learning_summary`는 Forest 기본 응답에 없음
- 관제 화면에서 “위험 질문/병목 작업/최신 변경” 즉시 확인 가능

Subphase 슬롯:
- 1.1 상단 KPI 및 관제 포커스 정리
- 1.2 모듈/로드맵/질문/이벤트 패널 재배치
- 1.3 관제 용어/색상/상태 라벨 통일
- 1.x (유연) 운영 중 발견된 UI 혼선 제거

---

### Phase 2. SonE 필터 정밀화 (Validation Hardening)
목표:
- SonE 결과를 “점수”가 아니라 “근거 있는 검증 결과”로 노출한다.

범위:
- 누락 슬롯/충돌/영향/리스크 근거(reason) 표준화
- Canopy에서 근거를 바로 읽을 수 있게 구조화

DoD:
- `sone_summary`에 최소 포함:
  - `missing_slot_count`, `impact_count`, `risk_cluster_count`, `max_risk_score`
  - `validation_stage`, `risk_reasons[]`
- 리스크는 “왜 그런지”를 reason으로 설명 가능

Subphase 슬롯:
- 2.1 SonE reason code 표준 정의
- 2.2 Grove 분석 결과를 reason 구조로 변환
- 2.3 Canopy 카드에서 reason 가독성 개선
- 2.x (유연) 규칙 튜닝 및 오탐/누락 보정

---

### Phase 3. 운영 루프 가속 (Operational Acceleration)
목표:
- 보고/재분석/갱신 루프를 안정화하고, 운영 중 의사결정 시간을 줄인다.

범위:
- work report -> grove -> canopy -> status sync 루프 관찰성 강화
- dedup/debounce 스킵 사유 가시화
- 추후 확장(그래프 상호작용) 준비

DoD:
- 같은 보고 재전송 시 중복 실행 없이 스킵 사유 확인 가능
- Canopy에서 루프 실행 상태(reanalysis/export/sync) 추적 가능
- 운영 문서 기준으로 재현 가능한 점검 절차 존재

Subphase 슬롯:
- 3.1 루프 상태/스킵 사유 표기
- 3.2 최근 변경 diff/전후 비교 강화
- 3.3 상호작용 그래프(최소) 도입
- 3.x (유연) 성능/운영 메트릭 확장

## 3. 유연 확장 규칙 (1.1 / 1.2 추가 방법)
- 신규 세부 작업은 반드시 아래 5줄로 추가:
  1) 목적 (무엇을 바꾸는가)
  2) 범위 (어디까지인가)
  3) 비범위 (무엇은 안 하는가)
  4) DoD (성공 판정)
  5) 검증 (테스트/수동 확인)
- 상위 Phase 목표와 충돌하면 추가 금지.
- 긴급 패치라도 Phase 번호를 부여해서 추적한다. (예: `2.4-hotfix`)

## 4. 원점 복귀 프로토콜 (Drift Reset)
아래 중 2개 이상 발생 시 즉시 원점 복귀:
- Forest 화면이 학습/실험 데이터로 과밀화됨
- SonE 결과가 근거 없이 점수만 노출됨
- 동일 지표를 HTML/React가 다르게 해석함
- 운영자가 “다음 우선순위”를 화면에서 바로 판단하지 못함

복귀 절차:
1. 본 문서 1장(원칙/범위) 재확인
2. Phase DoD 기준으로 현재 구현 갭 재평가
3. 1.x/2.x 미세 확장 중단 후 상위 Phase 필수 항목부터 재정렬

## 5. 실행 순서 (현재 권장)
1. Phase 1 마감 (관제탑 정보 위계 확정)
2. Phase 2 착수 (SonE reason 표준화)
3. Phase 3 착수 (운영 루프 관찰성)

## 6. 이번 사이클 기준점 (as-is)
- Forest 핵심 API 테스트 세트 통과
- SonE summary에 `validation_stage`, `risk_reasons` 반영 시작
- 관제 포커스(최고 위험 질문/최우선 작업/최신 변경) UI 반영 시작
