# Sophia Forest 구현상태 검토 리포트 (2026-02-17)

## 1) 검토 목적
- 소피아숲이 `설계-검토-상태 관제` 관점에서 시각적으로 진행사항 파악이 쉬운지 점검
- SonE가 실제로 `검증 필터`로 작동하는지 코드 기준으로 확인
- 현재 상태에서 바로 실행 가능한 로드맵 제시

## 2) 근거 범위
- API/코어:
  - `/Users/dragonpd/Sophia/api/forest_router.py`
  - `/Users/dragonpd/Sophia/core/forest/grove.py`
  - `/Users/dragonpd/Sophia/core/forest/canopy.py`
  - `/Users/dragonpd/Sophia/core/services/forest_status_service.py`
- Desktop 관제 UI:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/ControlPanel.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/CanopyBoard.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`
- 테스트 실행:
  - `source /Users/dragonpd/Sophia/.venv/bin/activate && python -m pytest /Users/dragonpd/Sophia/tests/api/test_forest_router.py /Users/dragonpd/Sophia/tests/api/test_canopy_phase_a.py /Users/dragonpd/Sophia/tests/api/test_forest_status_sync.py /Users/dragonpd/Sophia/tests/api/test_sone_router.py`
  - 결과: `12 passed`

## 3) 총평 (Executive Verdict)
- **판정: 부분 충족 (PARTIAL PASS)**
- 강점:
  - Forest API 루프(분석→질문/작업→상태/Canopy)는 실제 동작한다.
  - 모듈 단위(채팅/노트/에디터/자막/숲) 상태 관제 구조가 코드에 반영되어 있다.
  - Canopy 데이터에는 로드맵/질문큐/리스크/SonE 요약/최근 이벤트가 포함된다.
- 핵심 미흡:
  - SonE 필터가 아직 규칙기반 휴리스틱 중심이라 “정밀 검증기”로는 약하다.
  - 관제 UI가 `정적 HTML Canopy`와 `Desktop ReportPage`로 이원화되어 운영 일관성이 떨어진다.
  - 문서/이력 일부가 과거 방향(learning_summary 중심)과 혼재해 경계가 흐려질 위험이 있다.

## 4) 관제탑(시각 파악성) 구현 평가

### 4.1 현재 구현된 것 (충족)
- 모듈별 Overview, 중요도, 진행률, 병목(BLOCKED/FAILED), 질문 수 제공
- 로드맵 버킷(IN_PROGRESS / PENDING·BLOCKED / DONE RECENT) 제공
- 질문 큐/최근 이벤트/연결 맵(Topology) 제공
- 상태 동기화(`POST /forest/projects/{project}/status/sync`)와 스냅샷 파일 생성

### 4.2 현재 부족한 것 (미충족/부분충족)
- 그래프 상호작용성 부족:
  - Desktop는 연결선을 텍스트 리스트로 노출(가시성 제한)
  - HTML은 Mermaid 렌더링 있으나 관제 UX와 분리됨
- “변경 전/후” 관점이 약함:
  - 무엇이 언제 바뀌었는지 diff 중심 뷰가 부족
- 관제 정보와 부가 영역 혼재:
  - Bitmap Health와 핵심 Forest 관제가 같은 레벨로 배치되어 초점 분산
- UI 소스 이원화:
  - `/dashboard/.../index.html` + React ReportPage 이중 관리로 유지보수 비용 상승

### 4.3 결론
- **“현황은 볼 수 있으나, 빠르게 결정하기 좋은 관제탑” 수준까지는 아직 미달**
- 우선순위는 기능 추가보다 `단일 관제 화면의 정보 구조 정리`가 맞다.

## 5) SonE 검증 필터 구현 평가

### 5.1 현재 구현된 필터 동작
- Grove 분석 시 SonE IR 캐시 생성:
  - `analysis/last_delta.sone.json`
  - `analysis/dependency_graph.json`
  - `analysis/risk_snapshot.json`
- 슬롯 생성/신호 추출:
  - `success_condition` 누락
  - `scope` 누락
  - `dependency/conflict` 키워드 기반 위험 신호
- 위험 신호는 question pool 업데이트 및 Canopy 리스크 클러스터로 반영됨

### 5.2 현재 한계
- 다문서 교차검증/정합성 추론 부재
- 문서 구조 파싱(섹션/표/명세 슬롯)보다 키워드 기반 의존이 큼
- 위험 점수 근거가 규칙 설명과 함께 표준화되어 있지 않음(가시 추적성 약함)
- `/sone` 라우터는 현재 스케줄러 명령 API 성격이라 “SonE 검증 API”와 개념이 분리되어 있음

### 5.3 결론
- **SonE는 “기초 필터”로는 동작하지만, 목표한 검증 필터(정교한 구조 검증기)로는 아직 1단계**

## 6) 정체성 경계 점검
- 긍정:
  - Canopy 데이터에서 `learning_summary` 제외 테스트가 존재하여 Forest 경계 복구가 진행됨
- 리스크:
  - 과거 학습지표 중심 문서(`next_plan_B_to_C`)가 남아 있어 팀 판단을 다시 흔들 수 있음
  - 프로젝트 디렉토리에 `blueprint/reports/state` 같은 legacy 경로가 공존해 Forest SSOT 인지가 분산될 수 있음

## 7) 실행 로드맵 (현실 우선)

### R0 (즉시, 2~3일): 경계/표준 정리
- Forest SSOT 문서 1장으로 고정:
  - 관제 범위(Work/Question/SonE/Risk/Event)와 비범위(학습 성장지표) 명시
- 문서 드리프트 정리:
  - `next_plan_B_to_C` 등 과거 학습지표 중심 텍스트를 현 정책으로 갱신
- UI 단일화 방향 결정:
  - “React ReportPage를 메인 관제 UI”로 고정하고 정적 HTML은 export/view 용도로 제한

### R1 (단기, 1주): 관제탑 UX 개선
- Desktop ReportPage 중심으로 다음 4개만 우선:
  - 상단: 전체 상태 + 최대 리스크 + 오늘 변경 수
  - 중앙: 모듈 로드맵(완료/진행/막힘) 고정
  - 우측: 질문큐 우선순위 카드
  - 하단: 최근 변경 로그(필터+diff 강조)
- 연결맵은 React 상호작용 그래프로 최소 전환(노드 클릭→DetailPanel 동기화)

### R2 (단기, 1~2주): SonE 필터 정밀화
- SonE 검증 규칙을 명시적 룰셋으로 분리:
  - required slot 검사
  - 충돌 규칙
  - 증거 링크(ref) 강제
- 출력 표준:
  - `missing_slot`, `conflict`, `impact`, `risk_reason`을 구조화해 Canopy에 직접 노출

### R3 (중기): 운영 루프 안정화
- work report → grove 재분석 → canopy 갱신 → status sync 루프는 유지
- dedup/debounce 지표를 관제에 노출해 “왜 갱신이 스킵됐는지” 설명 가능하게 개선

## 8) 최종 판단
- 소피아숲은 이미 “형태”는 갖췄고, API/테스트 기준으로 동작도 한다.
- 지금 가장 중요한 것은 새 기능 확장이 아니라:
  1. **관제 UI 단일화**
  2. **SonE 필터 근거 표준화**
  3. **문서/정책 경계 고정**
- 이 3가지를 먼저 완료하면, 이후 로드맵(작업 추적/연결성/질문 생성)의 품질이 급격히 안정된다.
