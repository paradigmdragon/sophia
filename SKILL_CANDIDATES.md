# SKILL CANDIDATES

작성 기준: 기존 수집 정보만 사용, 최소 스킬 단위로 재실행/검증/롤백 가능성 중심 정리

## 1) name: engine-episode-lifecycle
intent: Episode ingest -> propose -> adopt 흐름을 재현하고 DB 상태를 검증
inputs: `ref_uri`, `text`, DB 경로
steps: ingest 실행 -> candidate 생성 -> adopt -> status 확인
outputs: 콘솔 로그, `sophia.db` 레코드
verification: `PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python tests/test_system.py`
rollback: 테스트 DB 파일 삭제(`sophia_test_sys.db`) 또는 백업 복원
permissions: `read/write`

## 2) name: engine-reject-pattern-log
intent: candidate reject 시 오류 패턴이 파일 로그에 누적되는지 검증
inputs: episode_id, candidate_id
steps: propose(저신뢰) -> reject -> `data/error_patterns.jsonl` 확인
outputs: `data/error_patterns.jsonl`, 콘솔 로그
verification: `bash /Users/dragonpd/Sophia/test_cli.sh`
rollback: `sophia.db`, `data/error_patterns.jsonl` 삭제 후 복구본 재적용
permissions: `read/write`

## 3) name: heart-priority-gate-check
intent: FOCUS/IDLE 상태별 우선순위 게이트(P1 우선)를 검증
inputs: 메시지 큐 샘플(P1/P3), heart state
steps: 큐 적재 -> dispatch -> state 전환 -> 재-dispatch
outputs: 콘솔 로그, message_queue 상태
verification: `PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python /Users/dragonpd/Sophia/verify_dispatcher.py`
rollback: 테스트 DB(`sophia_test_disp.db`) 제거
permissions: `read/write`

## 4) name: heart-context-gate-check
intent: required_context 매칭에 따라 dispatch 허용/차단 여부를 검증
inputs: context 조건(`chunk_a` 등), heart state
steps: 컨텍스트 요구 메시지 생성 -> 무컨텍스트/오컨텍스트/정컨텍스트 dispatch 비교
outputs: 콘솔 로그, message_queue 상태
verification: `bash /Users/dragonpd/Sophia/test_context.sh`
rollback: `sophia.db`, `heart_state.json` 삭제 후 복원
permissions: `read/write`

## 5) name: heart-batching-summary-check
intent: 동일 episode의 P2~P4 메시지 배치 요약 로직 검증
inputs: 동일 episode 메시지 여러 건
steps: 다건 enqueue -> dispatch -> summary_content 및 SERVED 마킹 확인
outputs: 콘솔 로그, message_queue 상태
verification: `PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python /Users/dragonpd/Sophia/verify_batching.py`
rollback: 테스트 DB(`sophia_test_batch.db`) 제거
permissions: `read/write`

## 6) name: api-lifecycle-smoke
intent: API 레벨 ingest/propose/adopt/status/dispatch의 기본 수명주기 검증
inputs: API 앱 인스턴스(FastAPI TestClient), 샘플 텍스트
steps: 엔드포인트 순차 호출 및 상태 코드/응답 확인
outputs: 콘솔 로그, 테스트 DB/상태 파일
verification: `PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python /Users/dragonpd/Sophia/tests/test_lifecycle.py`
rollback: `sophia.db`, `heart_state.json` 정리 후 복구
permissions: `read/write`

## 7) name: workspace-task-runner-smoke
intent: `workspace/tasks` 큐 파일 처리 및 이벤트 기록 경로를 점검
inputs: `.task.json`, workspace 경로
steps: queued task 생성 -> runner 실행 -> status/event 파일 확인
outputs: `workspace/tasks/*.task.json`, `workspace/events/*.jsonl`
verification: `PYTHONPATH=/Users/dragonpd/Sophia/core /Users/dragonpd/Sophia/.venv/bin/python /Users/dragonpd/Sophia/core/test_integration_task.py`
rollback: 테스트 workspace 디렉터리 삭제
permissions: `read/write`

## 8) name: asr-transcribe-refine-run
intent: 단일 미디어 입력에 대해 ASR+Refine 산출물 생성을 자동화
inputs: media 파일 경로, outdir, config 경로
steps: `app.cli transcribe` 실행 -> raw/refined/log 파일 생성 확인
outputs: `*.raw.srt`, `*.txt`, `*.refined.srt`, `*.refined.txt`, `*.run.json`
verification: `PYTHONPATH=/Users/dragonpd/Sophia/core /Users/dragonpd/Sophia/.venv/bin/python -m app.cli transcribe --files <FILE> --outdir /Users/dragonpd/Sophia/workspace/outputs --config /Users/dragonpd/Sophia/sone/subtitle.asr.sone`
rollback: 생성된 출력 파일 삭제 또는 백업 복원
permissions: `read/write`, `network(확인 필요: 모델 최초 다운로드 시)`

## 9) name: rough-cut-render-cycle
intent: 영상+SRT 기반 컷 후보 분석 및 렌더 결과를 생성
inputs: video_path, optional srt_path
steps: workspace 준비 -> cut_candidates 생성 -> keep interval 계산 -> ffmpeg 렌더 -> srt remap
outputs: `core/workspace/video/<work_id>/cut_candidates.json`, `output_roughcut.mp4`, `output_roughcut.srt`
verification: `PYTHONPATH=/Users/dragonpd/Sophia/core /Users/dragonpd/Sophia/.venv/bin/python -m app.cli rough_cut <VIDEO> --srt <SRT>`
rollback: 해당 `work_id` 디렉터리 제거
permissions: `read/write`

## 10) name: manifest-phase-verification
intent: memory manifest 기반 Phase1~3 동작(생성/시그널/표현) 점검
inputs: `memory/memory_manifest.json`, 샘플 입력 텍스트
steps: verify 스크립트 실행 -> pass/fail 확인 -> 백업 자동복원
outputs: 콘솔 로그, manifest 변경(임시)
verification: `PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python /Users/dragonpd/Sophia/scripts/verify_phase1.py` + `verify_phase2.py` + `verify_phase3.py`
rollback: 스크립트 내 `.bak` 복원 경로 사용
permissions: `read/write`, `network(확인 필요: Phase3 LLM 호출 경로)`

## 11) name: desktop-hardcoded-path-audit
intent: 데스크톱 앱의 절대경로/권한 스코프 고정 지점을 점검해 이식성 리스크를 탐지
inputs: TS/Rust/tauri capability 파일
steps: 하드코딩 경로 추출 -> 권한 범위와 비교 -> 표준 경로 매핑 작성
outputs: 경로 리스크 목록, 표준화 제안 문서
verification: `rg -n "/Users/dragonpd/Sophia|core/venv/bin/python|workspace/**|logs/**|docs/**" /Users/dragonpd/Sophia/apps/desktop`
rollback: 읽기 전용 분석 스킬(롤백 불필요)
permissions: `read`

---

## 우선순위 제안 (초기)
1. `heart-priority-gate-check` (운영 안정성 핵심)
2. `workspace-task-runner-smoke` (실사용 작업 경로)
3. `desktop-hardcoded-path-audit` (이식성/배포 리스크)
4. `manifest-phase-verification` (채팅-기억 루프)

