# B -> C Next Plan (Forest Control-Tower Aligned)

## 1) 현재 기준점
- Forest는 `설계-검토-상태 관제`를 담당한다.
- Canopy 기본 응답은 학습 성장 지표를 포함하지 않는다.
- 운영 핵심 데이터는 `Work / Question / SonE / Risk / Recent Events`다.

## 2) 다음 단계 후보 (우선순위)

### Priority 1: 관제 화면 단일화 (React 기준)
- 목표: 정적 HTML은 export/view 용도로 유지하고, 실제 운영 관제는 ReportPage 기준으로 통일
- 효과: 화면 이원화로 인한 해석 차이 제거
- DoD: 사용자 운영 기준 문서와 실제 화면 항목이 1:1 매칭

### Priority 2: SonE 필터 근거 표준화
- 목표: SonE 검증 결과를 `missing_slot / conflict / impact / risk_reason` 구조로 고정
- 효과: 리스크 왜 발생했는지 설명 가능
- DoD: Canopy JSON `sone_summary`에 reason 코드/근거 필드 노출

### Priority 3: 작업 루프 관찰성 강화
- 목표: report dedup/debounce/skip 사유를 관제에서 바로 확인 가능하게 표시
- 효과: “갱신 안 된 이유”를 즉시 파악
- DoD: Work report 후 Canopy에서 `reanalysis/export/sync` 실행 여부와 스킵 사유 확인 가능

## 3) 권장 실행 순서
1. 관제 화면 단일화
2. SonE 근거 표준화
3. 작업 루프 관찰성 강화

## 4) 제외 항목(현재 단계)
- 학습/성장 지표를 Forest 기본 데이터로 재주입하는 작업
- 자동 IDE 실행
- 실시간 파일 감시 기반 재분석
