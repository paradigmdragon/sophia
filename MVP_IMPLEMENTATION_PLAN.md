# Sophia Phase-0 MVP 구현 계획

## 범위 고정 (Phase-0)
- 우선 구현: `Registry + Executor + Verifier + Audit`
- Planner 제약: `단일 스킬 실행`만 지원
- Rollback 제약: `snapshot_restore`만 지원 (copy-backup)
- 기본 검증 모드: `advisory`
- 강제 strict 조건: capability에 `fs.write` 또는 `manifest.write` 포함 시 `strict`

## 제안 디렉터리
- `/Users/dragonpd/Sophia/sophia_kernel/schema`
- `/Users/dragonpd/Sophia/sophia_kernel/registry`
- `/Users/dragonpd/Sophia/sophia_kernel/executor`
- `/Users/dragonpd/Sophia/sophia_kernel/verifier`
- `/Users/dragonpd/Sophia/sophia_kernel/audit`
- `/Users/dragonpd/Sophia/sophia_kernel/planner`
- `/Users/dragonpd/Sophia/tests`

## 단계별 구현 순서

1. 스키마 고정
- 생성 파일:
  - `/Users/dragonpd/Sophia/sophia_kernel/schema/skill_manifest_schema_v0_1.json`
  - `/Users/dragonpd/Sophia/sophia_kernel/schema/audit_ledger_record_v0_1.json`
- 구현 내용:
  - 매니페스트 최소 필드 검증
  - 감사 레코드 필수 필드 검증
  - `fs.write`, `manifest.write` 포함 시 verification mode strict 강제 규칙 반영
- 검증 명령:
  - `python -m pytest /Users/dragonpd/Sophia/tests/schema/test_skill_manifest_schema_v0_1.py`
  - `python -m pytest /Users/dragonpd/Sophia/tests/schema/test_audit_ledger_record_v0_1.py`

2. Registry 구현
- 생성 파일:
  - `/Users/dragonpd/Sophia/sophia_kernel/registry/registry.py`
  - `/Users/dragonpd/Sophia/sophia_kernel/registry/models.py`
- 구현 내용:
  - manifest 등록/조회 (`register`, `get`)
  - 중복 `skill_id + version` 거부
  - schema validation 통과한 manifest만 저장
- 검증 명령:
  - `python -m pytest /Users/dragonpd/Sophia/tests/registry/test_registry.py`

3. Verifier 구현 (정책 우선)
- 생성 파일:
  - `/Users/dragonpd/Sophia/sophia_kernel/verifier/verifier.py`
  - `/Users/dragonpd/Sophia/sophia_kernel/verifier/policy.py`
- 구현 내용:
  - 기본 `advisory` 평가
  - capability 기반 strict 승격 (`fs.write`, `manifest.write`)
  - hook 반환 계약: `pass`, `violations`, `severity`, `evidence`
- 검증 명령:
  - `python -m pytest /Users/dragonpd/Sophia/tests/verifier/test_policy_mode.py`
  - `python -m pytest /Users/dragonpd/Sophia/tests/verifier/test_hook_contract.py`

4. Executor 구현 (단일 스킬 + copy-backup 롤백)
- 생성 파일:
  - `/Users/dragonpd/Sophia/sophia_kernel/executor/executor.py`
  - `/Users/dragonpd/Sophia/sophia_kernel/executor/snapshot.py`
- 구현 내용:
  - 단일 skill 실행 상태 전이: `queued -> running -> verified -> committed|failed|rolled_back`
  - 실행 전 copy-backup 생성
  - 실패 시 `snapshot_restore`만 수행
- 검증 명령:
  - `python -m pytest /Users/dragonpd/Sophia/tests/executor/test_single_run.py`
  - `python -m pytest /Users/dragonpd/Sophia/tests/executor/test_snapshot_restore.py`

5. Audit Ledger 구현 (append-only JSONL)
- 생성 파일:
  - `/Users/dragonpd/Sophia/sophia_kernel/audit/ledger.py`
  - `/Users/dragonpd/Sophia/.sophia/audit/ledger_v0_1.jsonl`
- 구현 내용:
  - run마다 1 line append
  - 필수 필드: `run_id`, `skill_id`, `inputs_hash`, `outputs_hash`, `diff_refs`, `status`, `timestamps`
  - 상태 변경마다 timestamp 업데이트 후 최종 line 기록
- 검증 명령:
  - `python -m pytest /Users/dragonpd/Sophia/tests/audit/test_append_only.py`
  - `python -m pytest /Users/dragonpd/Sophia/tests/audit/test_required_fields.py`

6. Planner 최소 구현 (single skill only)
- 생성 파일:
  - `/Users/dragonpd/Sophia/sophia_kernel/planner/planner.py`
- 구현 내용:
  - 입력 요청에서 하나의 `skill_id`만 허용
  - dependency 해석 없음
  - Registry 조회 후 Executor 호출만 담당
- 검증 명령:
  - `python -m pytest /Users/dragonpd/Sophia/tests/planner/test_single_skill_only.py`

7. E2E 통합 점검
- 생성 파일:
  - `/Users/dragonpd/Sophia/tests/e2e/test_phase0_mvp_flow.py`
- 구현 내용:
  - register -> execute -> verify -> audit -> rollback(실패 케이스) 경로 확인
  - strict/advisory 분기 확인
- 검증 명령:
  - `python -m pytest /Users/dragonpd/Sophia/tests/e2e/test_phase0_mvp_flow.py`
  - `python -m pytest /Users/dragonpd/Sophia/tests -q`

## 완료 기준 (Definition of Done)
- Registry/Executor/Verifier/Audit 4개 모듈 동작
- Planner는 단일 스킬 실행만 통과
- Rollback은 copy-backup 기반 `snapshot_restore`만 수행
- `fs.write` 또는 `manifest.write` capability를 가진 스킬은 실행 전 검증 모드가 strict로 강제됨
- audit ledger가 run 단위 JSONL append-only를 만족
