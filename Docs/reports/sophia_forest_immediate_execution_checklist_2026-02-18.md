# Sophia Forest 즉시 실행 체크리스트 (2026-02-18)

기준 문서:
- `/Users/dragonpd/Sophia/Docs/reports/sophia_forest_status_identity_report_2026-02-18.md`

목표:
- Forest를 “내부 정보 출력 화면”이 아니라 “실행 관제탑”으로 고정
- 지금 당장 실행 가능한 작업만 우선순위대로 수행

---

## Priority 0 (당장)

### 1. Focus View 기본 응답 계약 추가
- 작업: `GET /forest/projects/{project}/canopy/data`에 `view=focus|overview` 분기 추가
- 파일:
  - `/Users/dragonpd/Sophia/api/forest_router.py`
  - `/Users/dragonpd/Sophia/core/forest/canopy.py`
- DoD:
  - `view=focus`에서 `current_mission` + `next_action` + `focus_lock`만 최소 노출

### 2. current_mission 1개 강제 계산
- 작업: IN_PROGRESS/READY/BLOCKED 기준 우선순위 1개를 current mission으로 계산
- 파일:
  - `/Users/dragonpd/Sophia/core/forest/canopy.py`
- DoD:
  - focus 응답에 `current_mission_id`가 항상 하나(없으면 null + reason)

### 3. next_action 1줄 생성기 추가
- 작업: current mission 기준 다음 액션 1줄 생성
- 파일:
  - `/Users/dragonpd/Sophia/core/forest/canopy.py`
  - (선호) `/Users/dragonpd/Sophia/core/services/forest_status_service.py`
- DoD:
  - focus 응답에 `next_action.text`가 비어있지 않음(없으면 명확한 이유 텍스트)

---

## Priority 1 (이번 스프린트)

### 4. WIP 서버 정책 강제 (UI 우회 차단)
- 작업: 신규 work 생성 시 WIP_LIMIT(기본 1) 검사
- 파일:
  - `/Users/dragonpd/Sophia/api/work_router.py`
- DoD:
  - limit 초과 시 409 + 정책 코드 반환

### 5. Focus Lock 정책 도입 (soft/hard)
- 작업: `focus_lock.level` 검사로 create/promote 차단
- 파일:
  - `/Users/dragonpd/Sophia/api/work_router.py`
  - `/Users/dragonpd/Sophia/api/forest_router.py`
- DoD:
  - hard lock일 때 새 작업 생성/승격 API 차단

### 6. Freeze Idea 엔티티 및 API 추가
- 작업: 아이디어 격리 저장소 + freeze/promote 엔드포인트
- 파일:
  - `/Users/dragonpd/Sophia/core/memory/schema.py`
  - `/Users/dragonpd/Sophia/api/forest_router.py`
- DoD:
  - `POST /forest/ideas/freeze` 가능
  - `POST /forest/ideas/{id}/promote`는 조건 2개 없으면 차단

### 7. Freeze 도파민 트랩 방지 마찰 1개 적용
- 작업: 하루 freeze 상한 또는 연속 freeze 쿨다운 적용
- 파일:
  - `/Users/dragonpd/Sophia/api/forest_router.py`
- DoD:
  - 연속 과다 freeze 입력이 정책적으로 제어됨

---

## Priority 2 (바로 뒤)

### 8. Journey 2줄 생성 (재진입 가이드)
- 작업: 의미 이벤트 기준 `last_footprint`, `next_step` 생성
- 파일:
  - `/Users/dragonpd/Sophia/core/forest/canopy.py`
  - `/Users/dragonpd/Sophia/api/ledger_events.py`
- DoD:
  - 공백 이후에도 focus 응답에서 2줄이 항상 표시됨

### 9. reentry_minutes 추정치 추가
- 작업: 마지막 의미 이벤트~다음 액션 확정까지 추정 시간 계산
- 파일:
  - `/Users/dragonpd/Sophia/core/forest/canopy.py`
- DoD:
  - focus metrics에 `reentry_minutes` 노출

### 10. UI를 Focus 조종석으로 고정
- 작업: 기본 화면에서 focus DTO만 사용, overview는 2단계 진입
- 파일:
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/ReportPage.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/ExplorerPanel.tsx`
  - `/Users/dragonpd/Sophia/apps/desktop/src/pages/report/DetailPanel.tsx`
- DoD:
  - 첫 화면에 “현재 미션 1개 + 다음 액션 1개”만 크게 표시
  - 전체 목록/근거는 2단계 진입에서만 확인

---

## 테스트 체크 (반드시)
- API:
  - `focus view` 응답 계약 테스트
  - WIP limit 차단 테스트
  - freeze/promote 정책 테스트
- UI:
  - 기본 focus 화면 스냅샷
  - overview 진입 가드 테스트

권장 테스트 파일:
- `/Users/dragonpd/Sophia/tests/api/test_forest_focus_view.py`
- `/Users/dragonpd/Sophia/tests/api/test_work_focus_lock.py`
- `/Users/dragonpd/Sophia/tests/api/test_forest_ideas_freeze.py`

---

## 실행 규칙
- 새 기능을 추가하기 전에, 위 10개 중 완료되지 않은 항목이 있으면 먼저 처리
- “멋진 기능”보다 “다음 액션 1개의 명확성”을 우선
- Forest 기본 화면에서 원문 evidence/내부 디버그 정보는 노출 금지
