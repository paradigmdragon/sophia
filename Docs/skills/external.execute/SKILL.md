---
name: external-execute
description: Sophia 정책 하에서 외부 엔진 실행을 위임하고 결과를 표준 JSON으로 회수하는 strict adapter skill.
---

# external.execute

## 제목
Sophia External Engine Adapter (`external.execute`)

## 목적
- 외부 엔진 호출 계약 고정
- 입력/출력 스키마 고정
- 실패/재시도 정책 고정
- audit/verification/security 경계 고정

## 입력
- `engine`: `"codex" | "antigravity"`
- `work_id`: `string` (필수)
- `payload`: `string` (Work Package 텍스트만 허용, 자유 프롬프트 금지)
- `expected_return_schema`: `string` (반환 JSON 스키마 ID)

## 출력
반드시 JSON:
- `work_id`: `string`
- `status`: `"DONE" | "BLOCKED" | "FAILED"`
- `changes`: `array`
- `signals`: `array`
- `summary`: `string`

## 예제
입력:
```json
{
  "engine": "codex",
  "work_id": "wp_20260215_001",
  "payload": "# Work Package ...",
  "expected_return_schema": "report_json_v1"
}
```

출력:
```json
{
  "work_id": "wp_20260215_001",
  "status": "DONE",
  "changes": ["api/work_router.py 수정"],
  "signals": [{"cluster_id":"scope_ambiguity","hit":1,"risk":0.62,"evidence":"범위 문구 모호"}],
  "summary": "요구 변경 반영 및 테스트 통과"
}
```

## 보안 조건
- 외부 엔진은 Adapter를 통해서만 실행
- WORKSPACE_ROOT 외 접근 금지
- 절대 경로 입력 거부
- 환경 변수 접근 금지
- 네트워크 호출 기본 금지(정책 플래그로만 허용)

## Verification 조건
- `verification.mode = strict` 고정
- 입력 스키마 검증 필수
- 출력 스키마 검증 필수
- `output.work_id == input.work_id` 불일치 시 실패
- JSON 외 형식 반환 시 실패

## Audit 조건
필수 필드:
- `run_id`, `work_id`, `engine`, `inputs_hash`, `outputs_hash`, `status`, `duration_ms`
필수 이벤트:
- `EXTERNAL_EXECUTE_STARTED`
- `EXTERNAL_EXECUTE_COMPLETED`
- `EXTERNAL_EXECUTE_FAILED`

## 실패 정책
- 외부 실행 실패 시 1회 재시도
- 재시도 실패 시 `BLOCKED` 반환(JSON)
- 사용자 템플릿 발화:
  "주인님, 외부 실행 엔진이 응답하지 않았습니다. 재시도하시겠습니까?"

## Sophia 통합
- WorkPackage.status 업데이트
- question_pool signal 누적
- grove 재분석 트리거
- canopy 재계산 트리거
