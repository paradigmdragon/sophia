# Sophia Forest 구현상태 · 구조 · 정체성 리포트 (2026-02-18)

## 1) 리포트 목적
- 현재 소피아숲(Forest)의 **실제 구현 상태**를 코드 기준으로 정리한다.
- Forest의 **정체성(관제 시스템)**이 현재 구현과 얼마나 일치하는지 평가한다.
- 기능/구조의 강점과 한계, 리스크를 비판적으로 제시한다.
- 다음 수정 우선순위를 명확히 제안한다.

---

## 2) 현재 구현 상태 (사실 기준)

### 2.1 백엔드 API 상태
Forest 라우터는 현재 아래 핵심 엔드포인트를 제공한다.
- `POST /forest/projects/init`
- `POST /forest/projects/{project_name}/grove/analyze`
- `POST /forest/projects/{project_name}/grove/analyze/path`
- `POST /forest/projects/{project_name}/work/generate`
- `POST /forest/projects/{project_name}/roots/export`
- `GET /forest/projects/{project_name}/canopy/data`
- `POST /forest/projects/{project_name}/canopy/export`
- `POST /forest/projects/{project_name}/status/sync`

### 2.2 데이터 생성/집계 흐름
- Grove 분석 결과를 SonE 캐시(`analysis/last_delta.sone.json`, `risk_snapshot.json`, `dependency_graph.json`)로 기록.
- Canopy는 DB(WorkPackage, QuestionPool) + Forest ledger + SonE 캐시를 합쳐 관제용 데이터 생성.
- 상태 요약(`READY/IN_PROGRESS/DONE/BLOCKED/FAILED/UNVERIFIED`), 모듈 개요, 로드맵 ETA, 질문 큐, 최근 이벤트를 제공.

### 2.3 프론트(UI) 상태
현재 UI는 다음 원칙으로 재정렬된 상태.
- 상단: 최소 헤더 + 스냅샷 정보
- 좌측: Finder형 트리(모듈→작업/질문)
- 우측: 선택 경로 상세(핵심 정보, 코멘트/방향성/평가, 관련 기록)
- 분석 도구(ControlPanel)는 기본 숨김(버튼으로 열기)

### 2.4 검증 상태
최근 Forest API/워크플로우 회귀 테스트는 통과 상태로 유지됨.
- `tests/api/test_forest_router.py`
- `tests/api/test_canopy_phase_a.py`
- `tests/api/test_forest_status_sync.py`
- `tests/api/test_sone_router.py`
- `tests/api/test_work_router.py`

---

## 3) 구조 요약

### 3.1 논리 구조
- **Grove**: 문서 분석/검토(입력 → SonE IR 캐시 생성)
- **Canopy**: 상태판(프로젝트 진행/리스크/질문/이벤트 가시화)
- **Roots**: 기록 내보내기/보관(ledger, status export)

### 3.2 현재 아키텍처 특성
- 장점:
  - 관제 데이터가 API로 표준화되어 있어 UI 교체가 쉬움.
  - SonE reason code를 표준화해서 리스크 설명 일관성이 올라감.
  - Work report → 재분석 → canopy export 루프가 기본적으로 닫혀 있음.
- 약점:
  - `forest_router.py`, `work_router.py`에 책임이 과도하게 집중됨.
  - 이벤트/노트/채팅 메시지/재분석 로직이 한 함수에 결합되어 유지보수 난이도 상승.

---

## 4) 정체성 평가 (핵심)

### 4.1 의도된 정체성
Forest는 “설계-검토-상태 관제 시스템”이어야 하며,
사용자에게는 **방향/진행/문제 지점**을 보여주는 UI여야 한다.

### 4.2 현재 일치도 평가
- **부분 일치(약 70%)**
  - 일치: Grove/Canopy/Roots 축 자체는 살아 있음.
  - 불일치: 일부 내부 운영정보가 여전히 관제 화면으로 새어 나오는 경향이 있고,
    사용자 관점에서 불필요한 기술 디테일이 간헐적으로 노출됨.

### 4.3 결론
정체성은 무너진 상태는 아니지만,
아직 “운영자 콘솔” 습성이 남아 있어 “사용자 관제탑” 완성도는 부족하다.

---

## 5) 기능 평가 (현 시점)

### 5.1 잘 동작하는 기능
- 문서 기반 Grove 분석 실행
- SonE reason 표준 코드 생성/노출
- Work package 생성 및 report 반영
- report dedup/debounce 및 스킵 사유 노출
- Canopy 데이터/HTML export

### 5.2 품질이 낮은 기능 (개선 필요)
- UI 정보 계층화 완성도 부족
  - “핵심 요약”과 “내부 근거”가 명확히 분리되지 않은 구간 존재
- 연결 맵 표현 단순도
  - 현재는 텍스트 중심이라 관계 전개가 직관적으로 부족
- 라우터 결합도
  - API 레벨에서 도메인 오케스트레이션이 과대

---

## 6) 비판적 평가 (의견)

### 6.1 가장 큰 문제
**문제가 없는 데이터도 동일한 밀도로 보여주려는 습관**이 남아 있음.
이건 관제 UX를 무겁게 만들고, 사용자의 의사결정 속도를 떨어뜨린다.

### 6.2 구조적 리스크
- Work report 처리 함수가 너무 많은 부작용(재분석, 메시지, 노트, 이벤트, 동기화)을 담당.
- 테스트 통과와 별개로, 코드 복잡도 증가가 다음 기능 확장 시 회귀 위험을 키움.

### 6.3 전략적 리스크
- Forest는 “숲”을 보여줘야 하는데,
  구현자가 필요로 하는 로그/근거까지 기본 레이어에 남기면 다시 산으로 갈 수 있음.
- 이 상태로 기능을 더 얹으면 UI는 다시 과밀화될 가능성이 높다.

---

## 7) 고려사항 (설계 원칙)

1. 기본 화면은 항상 3가지 질문에만 답해야 함.
- 지금 어디가 문제인가?
- 지금 어디가 진행중인가?
- 지금 어디가 정상/완료인가?

2. 내부 근거는 2차 레이어로 강제 분리.
- 기본: 요약/배지/경로
- 상세: reason/evidence/log

3. 구조상 분리가 필요한 영역.
- report orchestration service 분리
- canopy view model service 분리
- notification/message writer 분리

4. “가시화 > 데이터량” 원칙 유지.
- 데이터 추가보다 탐색 구조(계층/탭/배지/토글) 우선

---

## 8) 권장 로드맵 (현실적)

### Phase A (즉시)
- 좌측 트리의 배지/탭 UX 고정
- 우측 상세를 “핵심/고급” 2층으로 더 엄격히 분리
- 기본 화면에서 원문 evidence 직접 노출 금지

### Phase B (단기)
- Work report 처리 로직을 서비스 계층으로 분리
- Canopy 데이터 조합 로직의 책임 경량화
- UI용 summary DTO와 내부 디버그 DTO를 분리

### Phase C (중기)
- 전체맵(간략 mind-map) 시각화 강화
- 모듈 단위 타임라인/변경 이력 drilldown
- 사용자가 “다음 액션 1개”를 즉시 실행할 수 있는 실행버튼 고정

---

## 9) 최종 판단
- Forest는 이미 “쓸 수 있는 상태”이지만, 아직 “잘 쓰이는 상태”는 아니다.
- 지금 가장 중요한 일은 기능 추가가 아니라,
  **정체성(관제탑) 기준으로 정보 노출 레이어를 강하게 통제**하는 것이다.
- 이 통제가 끝나면 이후 SonE 확장/워크플로우 확장의 효율이 급격히 올라간다.

