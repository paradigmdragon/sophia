# Sophia Forest Status Workflow v0.1

## 목적
작업 후 현재 구현 상태를 즉시 정리하고 Sophia Forest에 반영한다.

## 표준 실행 순서
1. 작업/테스트 수행
2. `make forest-sync` 실행
3. Forest 현황 확인
   - API: `/forest/projects/sophia/canopy/data`
   - 파일: `/Users/dragonpd/Sophia/forest/project/sophia/status/progress_snapshot.json`
   - 파일: `/Users/dragonpd/Sophia/forest/project/sophia/status/progress_roadmap.md`

## 자동 반영되는 내용
- Work/Question/Risk/SonE 기반 진행 요약
- 최근 완료/진행/대기 작업
- 다음 실행 항목(P0/P1/P2)
- Forest ledger 이벤트 `STATUS_SYNCED`

## 선택: 제한적 자동 동기화(work report 기준)
- 기본값: 비활성(`SOPHIA_FOREST_AUTO_SYNC=false`)
- 활성화 시점: `work report`가 `DONE/BLOCKED/FAILED`로 처리될 때
- 안전장치:
  - 기존 report dedup(`work_id + report_hash`) 적용
  - 기존 debounce(2초) 적용
  - 중복/디바운스 보고에서는 자동 동기화 스킵

## API 기반 동기화(서버 실행 중)
- `POST /forest/projects/sophia/status/sync`
- 기본적으로 Canopy export까지 함께 수행한다.

## 런타임 서버 계약 점검(권장)
- 실행:
  - `make check-server-contract`
  - 또는 `./scripts/check_server_contract.py --base-url http://127.0.0.1:8090`
- 확인 항목:
  - `/health`
  - `/chat/messages`
  - `/forest/projects/{project_name}/canopy/data`
  - sync 실행 경로(다음 중 하나):
    - `/sync/*`
    - `/api/sync/*`
    - `/forest/projects/{project_name}/status/sync`
    - `/forest/projects/{project_name}/roadmap/sync`

## 선택적 기록 동기화(권장)
- `POST /forest/projects/sophia/roadmap/sync`
- 목적: "기록할 가치가 있는 변경"만 저널 반영
- 기본 기록 범주:
  - `SYSTEM_CHANGE`
  - `PROBLEM_FIX`
  - `FEATURE_ADD`
- 기본 스킵 범주:
  - `UI_CHANGE`
  - `DOC_CHANGE`
  - `CHORE`
- 중복 방지:
  - title/summary/files 기반 fingerprint 중복은 자동 스킵
- 강제 기록:
  - `force_record=true`로 예외 기록 가능

## 수동 스냅샷 기록(필요할 때만)
- `POST /forest/projects/sophia/roadmap/record`
- 동작:
  - 분류/중복 정책을 동일하게 적용
  - 중복 또는 비기록 범주면 `recorded=0, skipped=1`로 반환
  - 권장: 의미 있는 시점(시스템/문제해결/신규기능)에서만 실행

## 에이전트 중간 보고 동기화(sync 루프)
- `POST /sync/progress`
- 목적: 작업 도중 중간 산출을 Forest 저널에 선별 반영
- 동일 정책 적용:
  - 기본 기록: `SYSTEM_CHANGE/PROBLEM_FIX/FEATURE_ADD`
  - 기본 스킵: `UI_CHANGE/DOC_CHANGE/CHORE`
  - fingerprint 중복은 자동 스킵

## 에이전트 최종 커밋 동기화(sync 루프)
- `POST /sync/commit`
- 목적: 최종 검증 결과를 반영하여 미션 상태를 `DONE/BLOCKED`로 전이
- 입력:
  - `mission_id`
  - `validation.tests_passed`, `validation.l2_passed`
  - (선택) `items` 기록 후보
- 동작:
  - WorkPackage 상태 전이
  - 동일 선별기록 정책으로 roadmap 저널 반영

## 수동 정합성 체크(sync 루프)
- `POST /sync/reconcile`
- 목적: 현재 Focus 상태와 roadmap 저널 기준 상태를 비교해 차이만 계산
- 기본 비교:
  - 현재 미션 ID
  - 남은 작업 수
- 결과:
- mismatch 목록 반환
- `apply=true` 이고 mismatch가 있을 때만 `SYNC_RECONCILE` 항목을 선별 기록

## 일괄 실행 루프(권장)
- `./scripts/sync_forest_loop.py --project sophia --intent "<이번 작업 의도>"`
- 동작:
  1. `/sync/handshake/init`
  2. `/sync/progress`
  3. (옵션) `/sync/commit`
  4. `/sync/reconcile`
- 기본 모드:
  - commit 미실행(중간 점검용)
  - progress + reconcile까지만 수행
- commit 포함 예시:
  - `./scripts/sync_forest_loop.py --project sophia --intent "work package finish" --mission-id wp_xxx --items-file /tmp/sync_items.json --commit --tests-passed --l2-passed --proof "pytest green"`
- prefix 기본값은 `auto`:
  - `/sync` 먼저 시도 후 404면 `/api/sync`로 자동 재시도
- 수동 지정이 필요하면:
  - `./scripts/sync_forest_loop.py --project sophia --intent "sync" --sync-prefix /api/sync`
- Makefile 단축:
  - `make forest-loop`
  - `make forest-loop-auto` (현재 git 변경분을 자동 요약해 items 생성)

### git 자동 수집 모드(권장)
- 기본: `--from-git` 사용 시 `git status --porcelain` 기반으로 변경 파일을 버킷(api/core/ui/docs...) 단위로 묶어 items 자동 생성
- 기본: `--git-tracked-only` 활성화로 `SYSTEM_CHANGE/PROBLEM_FIX/FEATURE_ADD` 범주만 자동 주입(UI/docs/chore는 제외)
- 기본: sync 실행 후 `progress_roadmap.md` 하단에 날짜별 `Sync Log` 접기 블록(`<details>`) 자동 추가
- 예시:
  - `./scripts/sync_forest_loop.py --project sophia --intent "sync 개선 반영" --from-git`
- UI/docs도 포함하려면:
  - `./scripts/sync_forest_loop.py --project sophia --intent "full git sync" --from-git --no-git-tracked-only`
- 요약 append를 끄려면:
  - `./scripts/sync_forest_loop.py --project sophia --intent "sync" --no-append-roadmap-summary`
- 제한:
  - `--git-max-files` (기본 60)
  - `--git-max-items` (기본 8)
- 참고:
  - UI/docs 버킷은 선별 정책에서 기본 스킵될 수 있음(기록 정책 일관성 유지)

### sync 라우트 미노출 서버 자동 대응
- `sync_forest_loop`는 기본적으로 sync API를 사용:
  - `/sync/*` → 404 시 `/api/sync/*` 자동 재시도
- 두 경로가 모두 없으면 OpenAPI를 조회해 legacy 모드로 자동 전환:
  - `roadmap` 경로가 있으면:
    - progress/commit: `POST /forest/projects/{project}/roadmap/sync`
    - reconcile: `POST /forest/projects/{project}/roadmap/record` (없으면 status/sync로 대체)
  - `status/sync`만 있으면:
    - progress/reconcile: `POST /forest/projects/{project}/status/sync?view=focus&export_canopy=false|true`
    - commit 대체: `POST /work/packages/{id}/complete` 또는 `POST /work/packages/{id}/report` 후 `status/sync`

### 기록 대상 작업 분류(운영 기준)
- `SYSTEM_CHANGE`: 아키텍처/정책/프로토콜 변경
- `PROBLEM_FIX`: 버그/장애/정합성 문제 해결
- `FEATURE_ADD`: 신규 기능 추가
- 기본 비기록:
  - `UI_CHANGE`
  - `DOC_CHANGE`
  - `CHORE`

### items 파일 예시(`/tmp/sync_items.json`)
```json
[
  {
    "title": "sync commit routing stabilization",
    "summary": "sync commit 상태 전이와 기록 정책 정합성 수정",
    "files": ["api/sync_router.py", "tests/api/test_sync_router.py"],
    "tags": ["sync", "fix"],
    "category": "PROBLEM_FIX"
  }
]
```

## CLI 기반 동기화(서버 없이 가능)
- `./scripts/sync_forest_status.py --project sophia --export-canopy`

## 운영 권장
- 기능 단위 작업 완료 시 1회 실행
- 하루 종료 전 1회 실행
- 대규모 변경 후에는 실행 직후 Canopy에서 `progress_sync.status == "synced"` 확인
- Canopy 상단 배지에서 `sync_status.label`을 확인:
  - `정상`: 최근 sync 단계가 정상 완료
  - `동기화필요/불일치/검증실패`: 다음 액션 실행 전 재정합 필요
  - `차단`: handshake 정책에 의해 진행 차단
