# SYSTEM SNAPSHOT

작성 기준: 이미 수집된 정적 분석 결과만 사용 (추가 스캔/프로세스 점검 없음)

## 1) 프로젝트 개요

최상위 목적(확인됨)
- 로컬-우선 AI 워크스페이스 지향: `README.md`
- 실제 구현 축은 2갈래:
1. Bit-hybrid 엔진(episode/candidate/backbone + heart dispatcher): `core/engine/*`, `api/server.py`
2. ASR/Refine 작업 파이프라인 + 워크스페이스 큐 처리: `core/app/*`, `workspace/*`, `apps/desktop/*`

현재 구현 범위(확인됨)
- API 서버(FastAPI) 엔드포인트: `/ingest`, `/propose`, `/adopt`, `/status`, `/dispatch`, `/set_state`, `/health` (`api/server.py`)
- CLI 엔진: ingest/propose/adopt/reject/search/status/dispatch/set_state (`core/engine/cli.py`)
- 작업 큐 러너: `workspace/tasks/*.task.json` 감시/실행 (`core/app/cli.py run`, `core/app/task/runner.py`)
- 데스크톱 UI(Tauri+React): 편집/히어링/노트/채팅/설정 라우팅 (`apps/desktop/src/App.tsx`)
- Rough-cut(영상 컷 후보 + 렌더): `core/rough_cut/*`

문서 대비 미완료 신호(확인됨)
- 구현 지시 문서에서 코드 구현 체크박스 미완료 표기:
1. `Docs/06_FINAL_IMPLEMENTATION_DIRECTIVE.md`
2. `Docs/07_BICAMERAL_ARCHITECTURE_DIRECTIVE.md`

## 2) 구조 지도

### A. 엔트리포인트
1. API 서버
- 스크립트: `start_server.sh`
- 실제 진입: `api/server.py`

2. 데스크톱 앱
- 스크립트: `start_desktop.sh`
- 프론트: `apps/desktop/src/main.tsx`
- Tauri Rust: `apps/desktop/src-tauri/src/main.rs`, `apps/desktop/src-tauri/src/lib.rs`

3. 엔진 CLI 래퍼
- 스크립트: `sophia.sh`
- 실제 진입: `core/engine/cli.py`

4. 코어 앱 CLI
- 진입: `core/app/cli.py`
- 하위 명령: `transcribe`, `run`, `chat`, `rough_cut`

### B. 모듈 지도
1. API 레이어
- `api/server.py`, `api/config.py`

2. Bit-hybrid 엔진
- 시스템 파사드: `core/system.py`
- 워크플로: `core/engine/workflow.py`
- 디스패처/하트: `core/engine/dispatcher.py`, `core/engine/heart.py`
- 스키마/상수/검색/충돌룰: `core/engine/schema.py`, `core/engine/constants.py`, `core/engine/search.py`, `core/engine/conflict_rules.py`

3. 워크스페이스 작업 파이프라인
- 파이프라인: `core/app/pipeline.py`
- ASR: `core/app/asr/whisper_engine.py`
- 정제: `core/app/refine/refiner.py`
- 태스크 모델/로더/러너: `core/app/task/models.py`, `core/app/task/loader.py`, `core/app/task/runner.py`
- 이벤트 기록: `core/app/task/event_writer.py`

4. 채팅/메모리 계층
- 매니저: `core/manager.py`
- 에피도라 규칙: `core/epidora.py`
- LLM 인터페이스: `core/llm_interface.py`
- 로거/커넥터: `core/logger.py`, `core/connector.py`

5. 데스크톱 UI 계층
- 라우팅: `apps/desktop/src/App.tsx`
- 작업 제출/이벤트 폴링: `apps/desktop/src/lib/taskManager.ts`
- 채팅 CLI 브리지: `apps/desktop/src/lib/chatService.ts`
- 노트/인박스 파일 접근: `apps/desktop/src/lib/noteService.ts`, `apps/desktop/src/lib/inboxService.ts`

### C. 런타임 흐름 추정(근거 기반)
1. 채팅 흐름
- UI(`ChatPage`) -> Tauri shell command(`run-python`) -> `python -m app.cli chat`
- `EpisodeManager.process_input`에서 로그 기록 + 시그널 + 질문 생성 + `memory/memory_manifest.json` 반영

2. ASR 작업 흐름
- UI(`HearingTab`)가 `workspace/tasks/*.task.json` 생성
- Core runner(`core/app/cli.py run --watch`)가 큐 파일 로딩/락 처리 후 `Pipeline.process_file` 실행
- 결과는 `workspace/outputs/*`, 이벤트는 `workspace/events/*`에 기록

3. 엔진/API 흐름
- API 또는 CLI로 ingest/propose/adopt/reject/search/status/dispatch 수행
- SQLite(`sophia.db`) + `heart_state.json` + `data/error_patterns.jsonl` + (일부 경로에서) `memory/memory_manifest.json` 갱신

## 3) 기능 인벤토리 (파일 매핑)

1. Episode/Candidate/Backbone 생명주기
- `core/engine/workflow.py`
- `core/engine/cli.py`
- `api/server.py`

2. Heart 메시지 큐(우선순위/컨텍스트/쿨다운/배치)
- `core/engine/dispatcher.py`
- `core/engine/heart.py`
- `verify_dispatcher.py`, `verify_batching.py`, `test_context.sh`

3. 후보 거절 패턴 로깅
- `core/engine/workflow.py` (`data/error_patterns.jsonl`)
- `test_cli.sh`

4. ASR + Refine 출력 생성
- `core/app/pipeline.py`
- `core/app/asr/whisper_engine.py`
- `core/app/refine/refiner.py`
- `core/app/common/writer.py`

5. Task 큐 기반 실행
- `core/app/task/loader.py`
- `core/app/task/runner.py`
- `core/app/cli.py run`

6. 영상 rough-cut
- `core/rough_cut/analysis.py`
- `core/rough_cut/rendering.py`
- `core/app/cli.py rough_cut`

7. 채팅 로그 및 인박스 반영
- `core/logger.py` -> `logs/chat/*.jsonl`
- `core/manager.py` + `memory/memory_manifest.json`
- `apps/desktop/src/lib/chatService.ts`, `apps/desktop/src/lib/inboxService.ts`

## 4) 설정/테스트/경로 상태

설정 파일(확인됨)
- Python: `core/requirements.txt`, `api/config.py`, `core/app/config.py`
- Desktop: `apps/desktop/package.json`, `apps/desktop/src-tauri/tauri.conf.json`, `apps/desktop/src-tauri/capabilities/default.json`
- `.env*`: 확인되지 않음(파일 미발견)

테스트/검증 자산(확인됨)
- `tests/test_system.py`
- `tests/test_lifecycle.py`
- `core/test_integration_task.py`
- `verify_dispatcher.py`, `verify_batching.py`
- `scripts/verify_phase1.py`, `scripts/verify_phase2.py`, `scripts/verify_phase3.py`
- 수동 스크립트: `test_cli.sh`, `test_dispatcher.sh`, `test_context.sh`, `test_heart.sh`

경로 관련 핵심 상태(확인됨)
- 계획 경로: `sophia_workspace/logs`, `sophia_workspace/reports`, `sophia_workspace/patches` 모두 미존재
- 기존 경로:
1. `logs/` (chat/asr)
2. `workspace/outputs/reports`
3. `workspace/outputs/*` (실제 산출물 다수)
4. `core/workspace/video/*` (rough-cut 전용)

## 5) 리스크 요약

1. 경로 하드코딩 리스크
- 절대경로가 UI/Tauri capability/명령 호출에 다수 고정됨 (`apps/desktop/src/lib/*.ts`, `apps/desktop/src-tauri/*`)

2. 워크스페이스 경로 이원화
- `workspace/*`와 `core/workspace/*`가 병행 사용됨

3. 스펙-구현 불일치 조짐
- README 링크 문서 누락: `Docs/Sophia_Workspace_Spec_v0.1.md` 없음
- 문서상 “구현 예정” 항목 존재

4. 프로세스 실상태
- 확인 필요 (프로세스 점검 명령 미승인 상태에서 중단됨)

