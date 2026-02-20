# Sophia Forest Phase Tracker (Living)

## 사용 규칙
- Phase 단위 목표를 먼저 확정하고, 세부 작업은 `x.1`, `x.2`로 유연하게 추가한다.
- 각 항목은 완료 시 날짜/근거(파일/테스트)를 남긴다.
- 항목 추가 시 상위 Phase 목표와 충돌하면 추가하지 않는다.

---

## Phase 1. 관제탑 정렬
상태: `IN_PROGRESS`

### 1.1 상단 관제 포커스(위험/우선작업/최신변경)
- 상태: `DONE`
- 근거:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/CanopyBoard.tsx`

### 1.2 SonE 상태 스트립(소스/검증단계/리스크 이유 수)
- 상태: `DONE`
- 근거:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`

### 1.3 관제 패널 위계 재정렬(결정속도 중심)
- 상태: `DONE`
- DoD:
  - 30초 내 “막힘/위험/다음작업” 파악 가능
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/ControlPanel.tsx`
  - 결정 레인(막힘/위험/다음 실행) 추가
  - Bitmap 패널 기본 숨김 + 필요시 표시 토글
  - ControlPanel을 빠른 실행 우선 + 고급설정 접기 구조로 재배치

### 1.4 탐색 구조 단순화(대분류/소분류/상세 드릴다운)
- 상태: `DONE`
- DoD:
  - 아이콘 기반 대분류 선택 후 소분류 목록으로 탐색 가능
  - 상세 패널에서 기록/방향성/평가를 즉시 확인 가능
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/ExplorerPanel.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`

### 1.5 Finder형 트리 + 전체맵 토글(집중형 UI)
- 상태: `DONE`
- DoD:
  - 좌측은 모듈 폴더 트리, 우측은 선택 경로 중심 정보만 노출
  - 전체맵 버튼으로 모듈/연결 요약을 즉시 확인
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/ExplorerPanel.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`

### 1.6 관제화면 단순화(내부 정보 기본 숨김)
- 상태: `DONE`
- DoD:
  - 기본 화면에서 내부 판단/근거 원문이 아닌 진행상태 중심 정보만 노출
  - 분석 도구는 접힌 패널로 이동
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`

### 1.7 좌측 빠른접근 탭 통합 + 배지 강조
- 상태: `DONE`
- DoD:
  - 상단 중복 상태 카드를 제거하고 좌측 빠른접근에 로드맵/고위험 탭 통합
  - 문제/확인 항목을 배지로 즉시 식별 가능
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/ExplorerPanel.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`

### 1.8 Focus Cockpit 기본화 + Overview 2단계 진입
- 상태: `DONE`
- DoD:
  - 기본 화면은 Focus(현재 미션 1개 + 다음 액션 1개)만 우선 노출
  - 상세 로그/전역맵은 Overview 잠금 해제 후 표시
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/ExplorerPanel.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/useReportController.ts`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/types.ts`

### 1.9 좌측 탭 재정렬(위험/상태/로드맵) + 배지 단순화
- 상태: `DONE`
- DoD:
  - 좌측 상단 중복 요약 제거
  - 빠른 접근을 위험/상태/로드맵 탭으로 통합하고 배지로 즉시 파악
  - 상세 패널은 선택 경로 중심 정보만 먼저 보여주고 고급 정보는 잠금 해제 후 노출
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/ExplorerPanel.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`

### 1.10 Focus 화면 밀도 개선(빈 영역 축소)
- 상태: `DONE`
- DoD:
  - Focus 잠금 상태에서도 우측에 실행 후보/최근 발자국/Freeze 보관함이 노출
  - 내부 디버그 정보가 아닌 실행/진행 요약 중심으로 유지
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`

### 1.11 Focus 즉시 실행 버튼(다음 액션/ACK/완료)
- 상태: `DONE`
- DoD:
  - Focus 영역에서 "다음 액션 실행"으로 실제 액션이 트리거됨
  - 선택 작업 상태에 따라 ACK/완료 버튼이 조건부 노출
  - 현재 미션 id가 있으면 우선 선택되도록 컨트롤러 보강
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/useReportController.ts`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`

### 1.12 사람 중심 요약(문제/진행/다음결정) 고정
- 상태: `DONE`
- DoD:
  - Focus 화면 상단에 `지금 문제 / 지금 만드는 것 / 다음 결정` 3줄 요약 고정
  - 기술 상세(linked_node 등)는 기본 노출에서 제거
  - 백엔드에서 human_summary를 생성해 UI 복잡도를 낮춤
- 반영:
  - `/Users/dragonpd/Sophia/core/forest/canopy.py`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/types.ts`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/ExplorerPanel.tsx`

### 1.x (유연 추가 슬롯)
- 상태: `OPEN`
- 메모:
  - 운영 중 발견되는 UI 혼선을 Phase 1 범위 내에서만 추가

---

## Phase 2. SonE 필터 정밀화
상태: `IN_PROGRESS`

### 2.1 validation_stage / risk_reasons 구조 반영
- 상태: `DONE`
- 근거:
  - `/Users/dragonpd/Sophia/core/forest/canopy.py`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/types.ts`
  - `/Users/dragonpd/Sophia/tests/api/test_forest_router.py`

### 2.2 reason code 표준 정의 및 Grove 연결
- 상태: `DONE`
- DoD:
  - reason code 문서 + Grove 출력 일치
- 반영:
  - `/Users/dragonpd/Sophia/docs/forest_sone_reason_codes_v0_1.md`
  - `/Users/dragonpd/Sophia/core/forest/sone_reason_codes.py`
  - `/Users/dragonpd/Sophia/core/forest/grove.py`
  - `/Users/dragonpd/Sophia/core/forest/canopy.py`

### 2.3 Canopy에서 reason 가독성 강화(카드형)
- 상태: `DONE`
- DoD:
  - missing_slots / risk_reasons를 카드형으로 노출해 원인 파악 시간을 단축
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/CanopyBoard.tsx`
  - SonE 검증 이유 카드(누락 슬롯/리스크 이유) 섹션 추가

### 2.x (유연 추가 슬롯)
- 상태: `OPEN`

---

## Phase 3. 운영 루프 가속
상태: `DONE`

### 3.1 report dedup/debounce 스킵 사유 노출
- 상태: `DONE`
- DoD:
  - `/work/packages/{id}/report` 응답과 이벤트에 `reanalysis_skip_reason` 노출
- 반영:
  - `/Users/dragonpd/Sophia/api/work_router.py`
  - `/Users/dragonpd/Sophia/tests/api/test_work_router.py`

### 3.2 전후 변화(diff) 중심 최근 변경 뷰
- 상태: `DONE`
- DoD:
  - Canopy 상세에 “최근 동기화 대비 전후 변화(diff)” 카드 표시
  - 상태 카운트 변화(`READY/IN_PROGRESS/DONE/BLOCKED...`)와 max risk 변화량을 함께 노출
  - 첫 동기화 시 기준 스냅샷 없음 메시지로 안전하게 처리
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/useReportController.ts`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`

### 3.3 상호작용 그래프(최소)
- 상태: `DONE`
- DoD:
  - topology 노드/엣지를 사람이 읽는 연결 관계 목록으로 표시
  - 관계 행 클릭 시 작업/질문/모듈 선택으로 즉시 점프 가능
  - 맵 기반 시각화 없이도 의존 흐름을 최소 상호작용으로 추적 가능
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`

### 3.x (유연 추가 슬롯)
- 상태: `OPEN`

---

## Phase 4. Focus/Freeze/Journey 정책 강제
상태: `IN_PROGRESS`

### 4.1 Canopy focus payload(contract) 추가
- 상태: `DONE`
- DoD:
  - `current_mission_id / next_action / focus_lock / frozen_ideas / journey / metrics`가 canopy data에 포함
- 반영:
  - `/Users/dragonpd/Sophia/core/forest/canopy.py`
  - `/Users/dragonpd/Sophia/api/forest_router.py`

### 4.2 WIP_LIMIT 서버 강제(우회 불가)
- 상태: `DONE`
- DoD:
  - WIP 한도 도달 시 work create/generate가 409(`FOCUS_LOCKED`)로 차단
- 반영:
  - `/Users/dragonpd/Sophia/core/services/focus_policy_service.py`
  - `/Users/dragonpd/Sophia/api/work_router.py`
  - `/Users/dragonpd/Sophia/api/forest_router.py`
  - `/Users/dragonpd/Sophia/tests/api/test_work_router.py`

### 4.3 Freeze Idea 최소 라이프사이클(FROZEN→PROMOTED)
- 상태: `DONE`
- DoD:
  - freeze/list/promote API 동작 + project 범위 격리 + 승격요건 2개 저장
- 반영:
  - `/Users/dragonpd/Sophia/api/forest_router.py`
  - `/Users/dragonpd/Sophia/tests/api/test_forest_router.py`

### 4.4 Focus Lock soft/hard 분리 정책
- 상태: `DONE`
- DoD:
  - soft: WIP_LIMIT 기준으로만 생성/승격 차단
  - hard: active mission 존재 시 생성/승격 즉시 차단
- 반영:
  - `/Users/dragonpd/Sophia/core/services/focus_policy_service.py`
  - `/Users/dragonpd/Sophia/core/forest/canopy.py`
  - `/Users/dragonpd/Sophia/api/work_router.py`
  - `/Users/dragonpd/Sophia/api/forest_router.py`
  - `/Users/dragonpd/Sophia/tests/api/test_work_router.py`
  - `/Users/dragonpd/Sophia/tests/api/test_forest_router.py`

### 4.5 Journey 2줄 품질 고도화
- 상태: `DONE`
- DoD:
  - 이벤트 타입별 `last_footprint`를 사람이 읽는 문장으로 변환
  - `streak_days` 계산 및 `next_step` 항상 비어있지 않도록 보장
- 반영:
  - `/Users/dragonpd/Sophia/core/forest/canopy.py`
  - `/Users/dragonpd/Sophia/tests/api/test_forest_router.py`
  - `/Users/dragonpd/Sophia/tests/api/test_canopy_phase_a.py`

### 4.6 Freeze → Work 승격 브리지 + 정책 결합 강화
- 상태: `DONE`
- DoD:
  - 아이디어 승격 시 Work Package 생성을 기본 연결
  - 생성/승격 정책 차단은 기존 Focus Lock 서버 정책을 그대로 적용
  - work_router가 chat_router 내부 함수 의존 없이 question_signal_service 사용
- 반영:
  - `/Users/dragonpd/Sophia/api/forest_router.py`
  - `/Users/dragonpd/Sophia/api/work_router.py`
  - `/Users/dragonpd/Sophia/tests/api/test_forest_router.py`

### 4.7 Focus 현재 미션 fallback(진행중 없을 때도 1개 고정)
- 상태: `DONE`
- DoD:
  - IN_PROGRESS가 없으면 READY/BLOCKED/FAILED 최우선 항목을 현재 미션으로 노출
  - Focus 화면에서 "현재 미션 없음" 빈 상태를 줄임
- 반영:
  - `/Users/dragonpd/Sophia/core/forest/canopy.py`
  - `/Users/dragonpd/Sophia/tests/api/test_canopy_phase_a.py`

### 4.8 Human/AI 관점 분리 + 로드맵 기록 API
- 상태: `DONE`
- DoD:
  - Canopy 응답에서 `human_view`(사람용 요약)와 `ai_view`(진단 계약)를 분리 제공
  - UI는 기본적으로 `human_view` 중심으로 렌더링
  - 현재 Focus 상태를 저널로 남기는 `/forest/projects/{project}/roadmap/record` API 제공
- 반영:
  - `/Users/dragonpd/Sophia/core/forest/canopy.py`
  - `/Users/dragonpd/Sophia/api/forest_router.py`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/useReportController.ts`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`
  - `/Users/dragonpd/Sophia/tests/api/test_forest_router.py`

### 4.9 Focus 실행 우선순위 Top3 카드
- 상태: `DONE`
- DoD:
  - Focus 기준으로 지금 바로 실행할 작업 Top3를 카드로 노출
  - 항목 클릭 시 해당 모듈/작업으로 즉시 점프
  - BLOCKED/FAILED/IN_PROGRESS/READY 우선순위를 서버 상태 기준으로 정렬
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`

### 4.10 Top3 전역 우선순위 정렬(선택 모듈 편향 제거)
- 상태: `DONE`
- DoD:
  - Top3가 선택 모듈이 아니라 현재 표시 가능한 전체 작업(visible scope) 기준으로 계산
  - 좌측 모듈 선택 상태와 무관하게 전역 막힘/진행 우선순위를 유지
  - 클릭 점프 동작은 기존과 동일하게 모듈/작업 동기화 유지
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/useReportController.ts`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`

### 4.11 Top3 질문 큐 보강(후보 부족 시 자동 채움)
- 상태: `DONE`
- DoD:
  - Top3 후보가 3개 미만이면 질문 큐(`READY_TO_ASK/PENDING/COLLECTING`)를 우선순위로 보강
  - 질문 후보 클릭 시 해당 cluster로 즉시 점프
  - 작업/질문 혼합 상태에서도 카드 3개를 안정적으로 유지
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`

### 4.12 Top3 sync fallback 보강(빈 상태 제거)
- 상태: `DONE`
- DoD:
  - 작업/질문 후보가 부족하면 `progress_sync.next_actions`를 fallback으로 자동 포함
  - Focus Top3 카드가 “실행 후보 없음” 상태로 비는 경우를 최소화
  - fallback 항목은 `sync 추천` 라벨로 구분
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`

### 4.13 Top3 즉시 실행 액션(ACK/완료) 연결
- 상태: `DONE`
- DoD:
  - Top3 작업 항목에서 `ACK`/`완료` 버튼으로 즉시 상태 전이를 실행
  - 클릭 시 기존 work API(`/work/packages/{id}/ack|complete`) 경로를 재사용
  - 작업이 아닌 항목(질문/sync fallback)은 선택 점프만 유지
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`

### 4.14 Top3 액션 중복실행 방지(Work Busy 상태)
- 상태: `DONE`
- DoD:
  - ACK/완료 실행 중 동일 work 항목 버튼을 잠금 처리
  - 버튼 라벨을 `처리중...`으로 바꿔 실행 상태를 즉시 표시
  - 작업 액션 busy 상태를 컨트롤러에서 단일 source-of-truth로 관리
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/useReportController.ts`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`

### 4.15 ACK/완료 실행 이력 SyncHistory 반영
- 상태: `DONE`
- DoD:
  - Top3에서 ACK/완료 실행 시 `진행중/완료/실패` 이벤트를 sync history에 즉시 기록
  - 사용자는 상세 로그 탭에서 작업 실행 흔적을 바로 추적 가능
  - 기존 메시지 업데이트 흐름(mode/message)과 중복 충돌 없이 동작
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/useReportController.ts`

### 4.16 Top3 질문 항목 즉시 작업화
- 상태: `DONE`
- DoD:
  - Top3 질문 항목에 `작업 생성` 액션을 추가
  - 클릭 시 해당 cluster 기준으로 work generate를 즉시 실행
  - 생성 성공 시 기존과 동일하게 work 선택/포커스 전환
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/useReportController.ts`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`

### 4.17 실행 직후 선택 동기화 + 최근결정 카드
- 상태: `DONE`
- DoD:
  - Top3에서 ACK/완료/작업생성 실행 시 해당 work/question을 먼저 선택 동기화
  - 상세 패널에 `최근 결정` 카드를 추가해 실행 결과를 즉시 반영
  - 서버 재동기화 전에도 사용자가 방금 실행한 액션을 포커스 화면에서 추적 가능
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`

### 4.18 ACK/완료 낙관적 상태 반영(즉시 UI 전이)
- 상태: `DONE`
- DoD:
  - ACK/완료 클릭 직후 work 상태를 낙관적으로 `IN_PROGRESS`/`DONE`으로 즉시 반영
  - canopy 동기화 데이터가 동일 상태를 반환하면 낙관 오버레이를 자동 정리
  - 실패 시 해당 work의 낙관 상태를 롤백하고 에러 이력을 유지
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/useReportController.ts`

### 4.19 낙관 상태 자동 만료(TTL) + 동기화 정리
- 상태: `DONE`
- DoD:
  - work 낙관 상태를 TTL(12초) 기반으로 자동 만료해 stale 표시 방지
  - 서버 상태와 낙관 상태가 일치하면 오버레이를 즉시 제거
  - canopy 응답 지연/누락 시에도 오버레이가 영구 고착되지 않음
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/useReportController.ts`

### 4.20 헤더/사이드바 중복 축소 + 프로젝트 하단 메뉴 분리
- 상태: `DONE`
- DoD:
  - 상단 헤더의 다중 경로/중복 출력 제거, 단일 `현재 선택` 라인으로 단순화
  - 사이드바에서 루트(`소피아숲`)와 중복되는 `forest` 모듈 항목을 제외
  - `새 프로젝트`/`자동 생성`/`소스자료 추가`를 프로젝트 폴더 하단의 독립 섹션으로 분리
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/ExplorerPanel.tsx`

### 4.x (유연 추가 슬롯)
- 상태: `OPEN`

---

## Phase 5. Forest v2 동기화 계층(Handshake)
상태: `IN_PROGRESS`

### 5.1 v2 사전검토 + 현행코드 매핑 문서화
- 상태: `DONE`
- 반영:
  - `/Users/dragonpd/Sophia/spec/sophia_forest_v2_architecture.md`
  - `/Users/dragonpd/Sophia/Docs/reports/forest_v2_preflight_review.md`

### 5.2 v2 상태머신 코어 모듈(독립 레이어)
- 상태: `DONE`
- DoD:
  - `DRAFT/ACTIVE/DONE/FROZEN/BLOCKED` 전이 규칙, WIP 제한, preflight 판단이 코드로 고정
- 반영:
  - `/Users/dragonpd/Sophia/core/forest_logic.py`
  - `/Users/dragonpd/Sophia/tests/core/test_forest_logic_v2.py`

### 5.3 `/sync/handshake/init` 어댑터 엔드포인트
- 상태: `DONE`
- DoD:
  - 기존 Forest 데이터(roadmap/work)를 읽어 handshake allow/deny를 반환
  - WIP 제한 + override 토큰 동작
- 반영:
  - `/Users/dragonpd/Sophia/api/sync_router.py`
  - `/Users/dragonpd/Sophia/api/server.py`
  - `/Users/dragonpd/Sophia/tests/api/test_sync_router.py`

### 5.4 선별 기록 정책 + roadmap sync 엔드포인트
- 상태: `DONE`
- DoD:
  - UI/문서/사소 변경은 기본 스킵
  - `SYSTEM_CHANGE/PROBLEM_FIX/FEATURE_ADD`만 기본 기록
  - 중복 fingerprint는 자동 스킵
- 반영:
  - `/Users/dragonpd/Sophia/core/services/forest_record_policy_service.py`
  - `/Users/dragonpd/Sophia/api/forest_router.py` (`POST /forest/projects/{project}/roadmap/sync`)
  - `/Users/dragonpd/Sophia/tests/api/test_forest_router.py`

### 5.5 `/sync/progress` 중간 보고 선별기록 연동
- 상태: `DONE`
- DoD:
  - sync 프로토콜에서도 동일 선별기록 정책 적용
  - UI/문서 변경은 기본 스킵, 시스템/문제해결/신규기능 중심 기록
  - 중복 fingerprint 자동 스킵
- 반영:
  - `/Users/dragonpd/Sophia/api/sync_router.py` (`POST /sync/progress`)
  - `/Users/dragonpd/Sophia/core/services/forest_roadmap_sync_service.py`
  - `/Users/dragonpd/Sophia/tests/api/test_sync_router.py`

### 5.6 `/sync/commit` 최종 상태 전이 + 선별기록 연동
- 상태: `DONE`
- DoD:
  - validation 결과로 WorkPackage `DONE/BLOCKED` 전이
  - commit 루프에서도 동일 선별기록 정책 사용
  - 중복 기록 방지 유지
- 반영:
  - `/Users/dragonpd/Sophia/api/sync_router.py` (`POST /sync/commit`)
  - `/Users/dragonpd/Sophia/tests/api/test_sync_router.py`

### 5.7 `/sync/reconcile` 현재 상태 vs 숲 저널 비교
- 상태: `DONE`
- DoD:
  - Focus 현재 상태와 roadmap baseline(최근 snapshot)을 비교
  - mismatch만 반환
  - `apply=true`일 때 mismatch 존재 시에만 `SYNC_RECONCILE` 기록
- 반영:
  - `/Users/dragonpd/Sophia/api/sync_router.py` (`POST /sync/reconcile`)
  - `/Users/dragonpd/Sophia/tests/api/test_sync_router.py`

### 5.8 sync 루프 실행 스크립트(핸드셰이크→진행→커밋→정합성)
- 상태: `DONE`
- DoD:
  - `scripts/sync_forest_loop.py` 1회 호출로 `/sync/*` 4단계를 순차 실행
  - handshake 차단 시 후속 단계 중단
  - progress/commit/reconcile 집계(`recorded_total/skipped_total`) 반환
- 반영:
  - `/Users/dragonpd/Sophia/scripts/sync_forest_loop.py`
  - `/Users/dragonpd/Sophia/Makefile` (`forest-loop`)
  - `/Users/dragonpd/Sophia/Docs/forest_status_workflow.md`
  - `/Users/dragonpd/Sophia/tests/scripts/test_sync_forest_loop.py`

### 5.9 Canopy 동기화 상태 배지(사람용 단순화)
- 상태: `DONE`
- DoD:
  - Canopy 응답에 `sync_status` 제공(`ok/warning/blocked/unknown`)
  - UI 상단에 상태 배지(라벨/step) 표시
  - 내부 payload 상세는 숨기고 사람용 메시지 중심 유지
- 반영:
  - `/Users/dragonpd/Sophia/core/forest/canopy.py`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/types.ts`
  - `/Users/dragonpd/Sophia/tests/api/test_forest_router.py`

### 5.10 sync 루프 git 자동 요약(`--from-git`)
- 상태: `DONE`
- DoD:
  - git 변경분을 버킷 단위로 자동 items 생성하여 sync 루프에 주입
  - `make forest-loop-auto`로 즉시 실행 가능
  - 기존 선별기록 정책을 그대로 적용(기록/스킵 일관성 유지)
- 반영:
  - `/Users/dragonpd/Sophia/scripts/sync_forest_loop.py`
  - `/Users/dragonpd/Sophia/tests/scripts/test_sync_forest_loop.py`
  - `/Users/dragonpd/Sophia/Makefile`
  - `/Users/dragonpd/Sophia/Docs/forest_status_workflow.md`

### 5.11 sync 라우트 자동 감지(`/sync`↔`/api/sync`)
- 상태: `DONE`
- DoD:
  - `sync_forest_loop` 기본값 `--sync-prefix auto`
  - handshake에서 `/sync` 404 시 `/api/sync` 자동 재시도
  - 선택된 prefix를 결과 payload에 포함
- 반영:
  - `/Users/dragonpd/Sophia/scripts/sync_forest_loop.py`
  - `/Users/dragonpd/Sophia/tests/scripts/test_sync_forest_loop.py`
  - `/Users/dragonpd/Sophia/Docs/forest_status_workflow.md`

### 5.12 런타임 서버 계약 검증(openapi 기반)
- 상태: `DONE`
- DoD:
  - 현재 실행 서버가 Forest sync 운용에 필요한 라우트를 노출하는지 즉시 판별
  - smoke test에서 계약 불일치 시 실패로 종료
- 반영:
  - `/Users/dragonpd/Sophia/scripts/check_server_contract.py`
  - `/Users/dragonpd/Sophia/scripts/test_smoke.sh`
  - `/Users/dragonpd/Sophia/tests/scripts/test_check_server_contract.py`
  - `/Users/dragonpd/Sophia/Makefile` (`check-server-contract`)
  - `/Users/dragonpd/Sophia/Docs/forest_status_workflow.md`

### 5.13 sync loop legacy fallback 모드
- 상태: `DONE`
- DoD:
  - sync 라우트(`/sync`/`/api/sync`)가 없을 때 legacy forest/work 라우트로 자동 전환
  - 결과 payload에 `mode: legacy|sync` 명시
  - 서버 재시작 전에도 최소한의 작업 기록/정합성 루프 유지
- 반영:
  - `/Users/dragonpd/Sophia/scripts/sync_forest_loop.py`
  - `/Users/dragonpd/Sophia/tests/scripts/test_sync_forest_loop.py`
  - `/Users/dragonpd/Sophia/Docs/forest_status_workflow.md`

### 5.14 OpenAPI 기반 legacy status-sync 자동 매핑
- 상태: `DONE`
- DoD:
  - `/sync`/`/api/sync`가 없으면 OpenAPI를 조회해 `roadmap-sync` 또는 `status-sync`로 자동 전환
  - `status-sync`만 있는 서버에서도 sync loop가 progress/commit/reconcile을 중단 없이 수행
  - 런타임 계약 검사에서 `forest/status-sync`를 유효한 sync 경로로 인정
- 반영:
  - `/Users/dragonpd/Sophia/scripts/sync_forest_loop.py`
  - `/Users/dragonpd/Sophia/scripts/check_server_contract.py`
  - `/Users/dragonpd/Sophia/tests/scripts/test_sync_forest_loop.py`
  - `/Users/dragonpd/Sophia/tests/scripts/test_check_server_contract.py`
  - `/Users/dragonpd/Sophia/Docs/forest_status_workflow.md`

### 5.15 운영 편의: smoke 재사용 + tracked-only 동기화
- 상태: `DONE`
- DoD:
  - `make test-smoke`가 8090 점유 시 기존 정상 서버를 재사용해 검증 수행
  - `sync_forest_loop --from-git` 기본값이 tracked category 중심으로 수렴
  - Canopy 헤더에 sync 경로 유형(`sync-router/status-sync/roadmap-sync`) 배지 노출
- 반영:
  - `/Users/dragonpd/Sophia/scripts/test_smoke.sh`
  - `/Users/dragonpd/Sophia/scripts/sync_forest_loop.py`
  - `/Users/dragonpd/Sophia/tests/scripts/test_sync_forest_loop.py`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`
  - `/Users/dragonpd/Sophia/Docs/forest_status_workflow.md`

### 5.16 sync 상태 계약 고정 + 기록 보기 토글
- 상태: `DONE`
- DoD:
  - backend `sync_status`에 `route_type`을 직접 제공(`sync-router/status-sync/roadmap-sync/unknown`)
  - Forest UI에서 `기록된 작업만 보기` 토글로 progress snapshot 기준 작업만 필터링
  - sync loop 실행 후 `progress_roadmap.md`에 실행 요약 블록 자동 append
- 반영:
  - `/Users/dragonpd/Sophia/core/forest/canopy.py`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/types.ts`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/useReportController.ts`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`
  - `/Users/dragonpd/Sophia/scripts/sync_forest_loop.py`
  - `/Users/dragonpd/Sophia/tests/scripts/test_sync_forest_loop.py`
  - `/Users/dragonpd/Sophia/tests/api/test_forest_router.py`
  - `/Users/dragonpd/Sophia/Docs/forest_status_workflow.md`

### 5.17 Focus 운영 가시성 강화(영속 토글 + 접기형 sync 로그)
- 상태: `DONE`
- DoD:
  - `기록된 작업만 보기` 토글 상태를 로컬 저장(재실행 후 유지)
  - 토글 ON 시 표시/숨김 작업 수를 상단 배지로 즉시 노출
  - `progress_roadmap.md`에 sync 실행 요약을 날짜별 접기 블록으로 누적
- 반영:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/useReportController.ts`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`
  - `/Users/dragonpd/Sophia/scripts/sync_forest_loop.py`
  - `/Users/dragonpd/Sophia/tests/scripts/test_sync_forest_loop.py`
  - `/Users/dragonpd/Sophia/Docs/forest_status_workflow.md`

### 5.18 병렬 lane/scope + 명세서 검토요청 워크플로우
- 상태: `DONE`
- DoD:
  - roadmap 기록/동기화에 `owner/lane/scope/review_state/spec_refs` 필드를 반영
  - Canopy 응답에 `parallel_workboard`를 추가해 lane별 작업 상태를 집계
  - DetailPanel에 `계획서/명세서/병렬작업` 메뉴를 추가
  - 명세서 검토요청 API(`/spec/review-request`)와 인덱스/읽기 API를 연결
- 반영:
  - `/Users/dragonpd/Sophia/core/services/forest_roadmap_sync_service.py`
  - `/Users/dragonpd/Sophia/core/forest/canopy.py`
  - `/Users/dragonpd/Sophia/api/forest_router.py`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/useReportController.ts`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/types.ts`
  - `/Users/dragonpd/Sophia/Docs/forest_agent_handoff.md`

### 5.x (유연 추가 슬롯)
- 상태: `OPEN`

---

## 검증 로그
- 2026-02-18:
  - Forest 핵심 테스트: `12 passed`
  - 실행:
    - `source /Users/dragonpd/Sophia/.venv/bin/activate && python -m pytest /Users/dragonpd/Sophia/tests/api/test_forest_router.py /Users/dragonpd/Sophia/tests/api/test_canopy_phase_a.py /Users/dragonpd/Sophia/tests/api/test_forest_status_sync.py /Users/dragonpd/Sophia/tests/api/test_sone_router.py`
  - Work+Forest 회귀 테스트: `16 passed`
  - 실행:
    - `source /Users/dragonpd/Sophia/.venv/bin/activate && python -m pytest /Users/dragonpd/Sophia/tests/api/test_work_router.py /Users/dragonpd/Sophia/tests/api/test_forest_router.py /Users/dragonpd/Sophia/tests/api/test_canopy_phase_a.py /Users/dragonpd/Sophia/tests/api/test_forest_status_sync.py /Users/dragonpd/Sophia/tests/api/test_sone_router.py`
  - Focus/Freeze 정책 테스트: `9 passed`
  - 실행:
    - `source /Users/dragonpd/Sophia/.venv/bin/activate && python -m pytest /Users/dragonpd/Sophia/tests/api/test_work_router.py /Users/dragonpd/Sophia/tests/api/test_forest_router.py`
  - Focus lock soft/hard 분리 테스트: `12 passed`
  - 실행:
    - `source /Users/dragonpd/Sophia/.venv/bin/activate && python -m pytest /Users/dragonpd/Sophia/tests/api/test_work_router.py /Users/dragonpd/Sophia/tests/api/test_forest_router.py`
  - Journey 고도화 회귀: `18 passed`
  - 실행:
    - `source /Users/dragonpd/Sophia/.venv/bin/activate && python -m pytest /Users/dragonpd/Sophia/tests/api/test_forest_router.py /Users/dragonpd/Sophia/tests/api/test_canopy_phase_a.py /Users/dragonpd/Sophia/tests/api/test_work_router.py`
  - Focus/Bridge/UI 반영 회귀: `18 passed`
  - 실행:
    - `source /Users/dragonpd/Sophia/.venv/bin/activate && python -m pytest /Users/dragonpd/Sophia/tests/api/test_forest_router.py /Users/dragonpd/Sophia/tests/api/test_work_router.py /Users/dragonpd/Sophia/tests/api/test_canopy_phase_a.py`
  - Focus fallback + UI 밀도 반영 회귀: `19 passed`
  - 실행:
    - `source /Users/dragonpd/Sophia/.venv/bin/activate && python -m pytest /Users/dragonpd/Sophia/tests/api/test_canopy_phase_a.py /Users/dragonpd/Sophia/tests/api/test_forest_router.py /Users/dragonpd/Sophia/tests/api/test_work_router.py`
  - Focus 실행 버튼 반영 회귀: `19 passed`
  - 실행:
    - `source /Users/dragonpd/Sophia/.venv/bin/activate && python -m pytest /Users/dragonpd/Sophia/tests/api/test_canopy_phase_a.py /Users/dragonpd/Sophia/tests/api/test_forest_router.py /Users/dragonpd/Sophia/tests/api/test_work_router.py`
  - Desktop build: `PASS`
  - 실행:
    - `cd /Users/dragonpd/Sophia/apps/desktop && npm run build`
  - 사람 중심 요약 반영 회귀: `19 passed`
  - 실행:
    - `source /Users/dragonpd/Sophia/.venv/bin/activate && python -m pytest /Users/dragonpd/Sophia/tests/api/test_canopy_phase_a.py /Users/dragonpd/Sophia/tests/api/test_forest_router.py /Users/dragonpd/Sophia/tests/api/test_work_router.py`
  - Desktop build: `PASS`
  - 실행:
    - `cd /Users/dragonpd/Sophia/apps/desktop && npm run build`
  - Canopy 회귀 테스트: `10 passed`
  - 실행:
    - `source /Users/dragonpd/Sophia/.venv/bin/activate && python -m pytest /Users/dragonpd/Sophia/tests/api/test_canopy_phase_a.py /Users/dragonpd/Sophia/tests/api/test_canopy_learning_summary_growth.py /Users/dragonpd/Sophia/tests/api/test_forest_status_sync.py`
  - Desktop build: `PASS`
  - 실행:
    - `cd /Users/dragonpd/Sophia/apps/desktop && npm run build`
