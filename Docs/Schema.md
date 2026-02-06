

manifest.json v0.1 (FINAL)

1) 전체 형태

{
  "schema_version": "0.1",
  "document": {
    "id": "doc_20260203_001",
    "type": "manuscript",
    "genre": "essay",
    "title": "",
    "created_at": "2026-02-03T00:00:00Z",
    "updated_at": "2026-02-03T00:00:00Z"
  },
  "anchors": {
    "para_a8f3c9": {
      "kind": "paragraph",
      "hash": "a8f3c9",
      "fingerprint": "a3f9c2e8b7d4...full_sha256",
      "preview": "사람은 본질적으로 이기적이다"
    }
  },
  "patches": {
    "p_000001": {
      "patch_id": "p_000001",
      "target_anchor": "para_a8f3c9",
      "engine": "sophia",
      "type": "reasoning",
      "issue_code": "EPI-01",
      "thin_summary": "정의 없이 개념 사용",
      "status": "pending",
      "options": [
        { "id": "opt_1", "semantic": "keep_essential", "label": "본질 유지" },
        { "id": "opt_2", "semantic": "make_conditional", "label": "조건부로 완화" },
        { "id": "opt_3", "semantic": "add_definition", "label": "정의 문장 추가" }
      ],
      "diff": null,
      "created_at": "2026-02-03T00:00:00Z",
      "updated_at": "2026-02-03T00:00:00Z"
    }
  },
  "decisions": [
    {
      "decision_id": "d_000001",
      "patch_id": "p_000001",
      "target_anchor": "para_a8f3c9",
      "decision": "pending",
      "selected_option_id": null,
      "reason_code": "LATER",
      "decided_at": "2026-02-03T00:00:00Z"
    }
  ],
  "preferences": {
    "issues": {
      "EPI-01": {
        "applied": 0,
        "pending": 1,
        "deleted": 0,
        "last_decision": "pending",
        "cooldown_until": null,
        "cooldown_scope": "per_anchor"
      }
    },
    "engines": {
      "sophia": {
        "applied": 0,
        "pending": 1,
        "deleted": 0
      },
      "general": {
        "applied": 0,
        "pending": 0,
        "deleted": 0
      }
    }
  },
  "context_export": {
    "para_a8f3c9": {
      "patch_id": "p_000001",
      "engine": "sophia",
      "type": "reasoning",
      "issue_code": "EPI-01",
      "status": "pending",
      "summary": "[EPI-01] 정의 관련 질문 보류"
    }
  }
}


⸻

2) 필드 규격 (스키마 계약)

2.1 document
	•	id (string, required) : 문서 고유 ID
	•	type (string, required) : manuscript | script | plan | novel | research
	•	genre (string, optional) : 톤/필터 가공용(예: essay, legal, devdoc)
	•	title (string, optional)
	•	created_at / updated_at (ISO string, required)

⸻

2.2 anchors

문단/블록의 안정적 참조를 위한 사전.
	•	key: para_{hash} (string)
	•	value:
	•	kind: "paragraph" 고정(v0.1)
	•	hash: 짧은 해시(6~12 chars)
	•	fingerprint: full sha256 (required, 충돌 판정/재매칭용)
	•	preview: 문단 앞부분 1줄(디버깅/표시용)

v0.1 규칙: 문단 단위만 지원
(팀/프로젝트 확장 시 block/scene 등 kind 추가)

⸻

2.3 patches

현재 살아있는 패치 저장소
(과거 이력은 decisions에만 남긴다)

status는 decisions의 최신 기록을 반영한 캐시 값이며,
진실의 원천(Source of Truth)은 decisions이다.

필수 필드:
	•	patch_id (string)
	•	target_anchor (string, anchors 키 참조)
	•	engine (enum): sophia | general
	•	type (enum): reasoning | grammar
	•	issue_code (string, required)
	•	Sophia: EPI-01~EPI-06 권장
	•	General: GRM-* 형태 권장(예: GRM-SPELL, GRM-STYLE)
	•	thin_summary (string, required)
	•	status (enum): applied | pending | deleted
	•	options (array, optional)
	•	Sophia는 보통 포함
	•	General은 보통 비움
	•	diff (object|null)
	•	Sophia: null
	•	General: diff 구조 사용
	•	created_at / updated_at (ISO string)

diff 구조 (General 전용, v0.1)

"diff": {
  "format": "unified",
  "hunks": [
    {
      "old": "원문 일부",
      "new": "수정안 일부",
      "apply_mode": "first_match"
    }
  ]
}


⸻

2.4 decisions

사용자의 모든 선택 이벤트 누적 로그
(반영/보류/삭제 전부 기록)

필수 필드:
	•	decision_id (string)
	•	patch_id (string)
	•	target_anchor (string)
	•	decision (enum): applied | pending | deleted
	•	selected_option_id (string|null)
	•	reason_code (enum|string|null)
	•	삭제/보류 시 입력 권장
	•	decided_at (ISO string)

reason_code 최소 세트 (v0.1)
	•	WRONG
	•	IRRELEVANT
	•	TOO_MUCH
	•	STYLE_MISMATCH
	•	LATER
	•	SUPERSEDED

⸻

2.5 preferences

LLM이 읽는 요약 성향(Thin Personalization Layer)
	•	issues: issue_code별 카운트/쿨다운
	•	engines: 엔진별 카운트

issues.{issue_code} 구조:
	•	applied / pending / deleted (int)
	•	last_decision (enum|string|null)
	•	cooldown_until (ISO string|null)
	•	cooldown_scope (enum): "global" | "per_anchor"

v0.1 기본값
cooldown_scope = "per_anchor"

v0.1 규칙: preferences는 “파생 데이터”
재생성 가능해야 하므로 단순 집계 중심

⸻

2.6 context_export

다음 AI 검토에 넘기는 문단별 얇은 컨텍스트
	•	key: anchor id
	•	value:
	•	patch_id
	•	engine
	•	type
	•	issue_code
	•	status
	•	summary

v0.1 규칙
	•	문단당 1개
	•	pending 우선
	•	cooldown 적용 시 제외 가능

⸻

3) v0.1 운영 규칙 (필수)
	1.	문단당 최신 pending 1개 원칙
	•	새 패치 생성 시 기존 pending은 inactive로 만들지 않고
    patches에서 교체 + decisions에 기록
    (기존 pending은 decision=deleted, reason_code=SUPERSEDED로 종료 기록)
(v0.1에 inactive 상태는 두지 않음)
	2.	patches는 “현재 상태”, decisions는 “전체 이력”
	3.	context_export는 항상 얇게
	•	patches/decisions 전체를 LLM에 넘기지 않는다
	4.	patches.status는 반드시 decisions 중 해당 patch_id의 가장 최신 decision과 일치해야 한다.
	5.	schema_version 변경 시
	•	anchors.hash / fingerprint는 재계산 가능
	•	decisions는 절대 삭제하지 않는다
	•	patches는 재생성 가능 영역으로 간주한다








1. 핵심 질문 재정의

A의 목표는 하나다.

문단이 수정·삽입·삭제·이동되어도 “같은 문단”을 최대한 같은 anchor로 추적하고
패치/결정/성향 누적이 깨지지 않게 만드는 것

즉, 안정성 > 완벽성이다.

⸻

2. 구조 분석 (구조/효율/적용성/리스크)

구조

anchor는 v0.1에서 paragraph 단위로만 간다.
anchor는 “문단 자체” + “주변 문맥”을 함께 지문으로 만든다.
	•	문단 텍스트만 해시 → 문단을 조금만 고쳐도 ID가 바뀜
	•	위치(순번)만 사용 → 삽입/삭제에 취약
	•	해결: 자기 + 주변(이전/다음) 기반 fingerprint

효율성
	•	생성/매칭은 로컬에서 O(n)~O(n log n) 수준으로 처리 가능해야 함
	•	LLM 호출 없이 deterministic 해야 함

적용성
	•	Markdown 원고모드에서 바로 적용
	•	나중에 block/scene 단위로 확장 가능

리스크
	•	동일한 문단이 반복될 때 충돌
	•	문단이 크게 수정되면 추적 실패
	•	문단 분할/병합 시 기존 패치가 어디로 갈지 애매

→ v0.1은 “최대한 추적 + 실패 시 안전하게 새로 생성” 원칙

⸻

3. Anchor 생성 규칙 v0.1 (결정)

3.1 문단 분리 규칙
	•	기본: 빈 줄(연속 개행 2개 이상) 기준 문단 분리
	•	예외: 코드블록(````), 인용(>), 리스트는 “연속 블록”으로 묶고 그 블록 전체를 한 문단으로 취급
(원고모드가 “기본 마크다운”이라도, 이 정도는 필수)

3.2 정규화(normalize) 규칙

문단 fingerprint 계산 전 텍스트를 정규화한다.
(정규화가 있어야 사소한 편집에 덜 흔들림)
	•	앞뒤 공백 trim
	•	연속 공백 2개 이상 → 1개로 축소
	•	줄바꿈은 유지하되, fingerprint 계산에는 \n을 공백으로 치환
	•	문장부호/기호 제거는 하지 않음 (의미 손실/충돌 위험)

3.3 지문(fingerprint) 구성

각 문단에 대해 아래 3개 조각을 만든다.
	•	self_sig: 문단 자체에서 앞부분 일부 + 뒷부분 일부
	•	prev_sig: 이전 문단의 앞부분 일부
	•	next_sig: 다음 문단의 앞부분 일부

권장 길이(기준치):
	•	self_head: 64자
	•	self_tail: 64자
	•	prev_head: 32자
	•	next_head: 32자

“앞+뒤”를 쓰는 이유:
문단 앞만 바꾸는 편집에 덜 흔들리게

3.4 해시 입력 문자열(정규식)

fingerprint string:

F = "v0.1|P|" + prev_head + "||" + self_head + "||" + self_tail + "||" + next_head

해시:
	•	hash = SHA-256(F) → hex
	•	v0.1 저장용 short = hash[0:6] (충돌 감안해 6~8 권장)

anchor id:
	•	para_{short}

manifest에 저장하는 anchor 값:
	•	kind: “paragraph”
	•	hash: short
	•	fingerprint: full hash (권장: 추후 충돌 판정용)
	•	preview: 사람이 볼 1줄(정규화 전 원문 기준 40~80자)

v0.1 스키마에 fingerprint 필드가 없었는데,
anchors 값에 추가하는 것은 호환 깨지지 않는다.
(anchors는 확장 가능 영역)

⸻

4. Anchor 매칭(업데이트) 규칙 v0.1

문서가 수정되면 문단이 재분리되고 새 anchor 후보들이 생긴다.
여기서 기존 anchor를 재사용할지 결정한다.

4.1 1차 매칭: exact fingerprint
	•	새 fingerprint가 기존 anchors의 fingerprint와 동일하면 같은 anchor로 매칭

4.2 2차 매칭: self 유사도 기반

exact가 없으면 아래 점수로 후보를 찾는다.

score 구성(0~100):
	•	self_head 유사도 40
	•	self_tail 유사도 40
	•	prev_head 유사도 10
	•	next_head 유사도 10

유사도 계산은 구현 편의상:
	•	간단: 공통 substring 비율 / 혹은 토큰 Jaccard
	•	v0.1은 정확도보다 안정성: “임계치”만 잘 잡으면 됨

임계치:
	•	score ≥ 80 → 동일 문단으로 간주, 기존 anchor 재사용
	•	그 미만 → 새 anchor 생성

4.3 문단 분할/병합 처리(안전 규칙)
	•	분할: 기존 문단이 둘로 갈라짐
→ 기존 anchor는 앞쪽 문단에 우선 매칭, 뒤쪽은 새 anchor
	•	병합: 두 문단이 하나로 합쳐짐
→ 앞쪽 anchor를 우선 유지, 뒤쪽 anchor는 “소멸” (패치는 decisions에 남기고 patches에서는 정리)

v0.1에서는 “패치 이관”을 자동으로 하지 않는다.
(이관은 오판 리스크가 커서 v0.2+에서 다루는 게 안전)

⸻

5. Pending 패치 반복 방지에 필요한 추가 규칙

Anchor가 어느 정도 안정화되더라도, 완벽하지 않다.
그래서 반복 지적 방지를 위해 추가 안전장치를 둔다.

5.1 cooldown 키

preferences의 cooldown은 issue_code만이 아니라 issue_code + anchor_hash 조합을 지원한다.
	•	같은 문단에 같은 지적을 무한 반복하는 현상 방지
	•	anchor가 바뀌어도 “대충 같은 문단”이면 유사도 매칭으로 이어짐

v0.1에서는 단순히:
	•	pending이 있는 문단은 Sophia/General 분석을 스킵
이 규칙이 1차 방어선

⸻

6. 액션 아이템 (즉시 구현 문장)
	1.	Markdown 문서를 문단 단위로 분리(빈 줄 기준 + 코드/인용/리스트 블록 예외)
	2.	각 문단에 대해 normalize 후 prev/self/next 시그니처 생성
	3.	fingerprint = sha256("v0.1|P|...") 계산
	4.	기존 anchors와 매칭: exact → 유사도(≥80) → 새 생성
	5.	anchor 갱신 후, patches의 target_anchor를 새 anchor로 재결합
	6.	매칭 실패 문단은 새 anchor로 생성하고, 기존 패치는 손대지 않음(안전)






A-1. Anchor 생성/매칭 테스트 케이스 목록 (v0.1)

공통 전제
	•	문단 분리: 빈 줄 기준
	•	anchor fingerprint = prev + self(head/tail) + next
	•	매칭 규칙: exact → 유사도 ≥ 80 → 실패 시 신규

⸻

1. 기본 안정성

TC-A01: 변경 없음
	•	입력: 문서 재저장
	•	기대: 모든 anchor 동일
	•	리스크: 없음 (baseline)

TC-A02: 문단 내부 맞춤법 수정
	•	“사람은 본질적으로 이기적이다” → “사람은 본질적으로 이기적이다.”
	•	기대: 같은 anchor 유지
	•	포인트: normalize + head/tail 유지

⸻

2. 경미한 수정

TC-A03: 문단 앞부분 1~2문장 수정
	•	첫 문장만 변경, 뒷부분 유지
	•	기대: 동일 anchor
	•	포인트: self_tail이 유지되므로 score ≥ 80

TC-A04: 문단 뒷부분 수정
	•	마지막 문장 수정
	•	기대: 동일 anchor
	•	포인트: self_head 유지

⸻

3. 위치 변화

TC-A05: 문단 위에 새 문단 삽입
	•	기존 문단 위치 +1
	•	기대: 기존 anchor 유지
	•	포인트: prev/next 변화에도 self 유지

TC-A06: 문단 아래 새 문단 삽입
	•	기대: 기존 anchor 유지

⸻

4. 삭제

TC-A07: 문단 삭제
	•	anchor가 참조하던 문단 제거
	•	기대
	•	anchors: 해당 anchor 제거
	•	patches: target_anchor 없음 → 자동 비활성
	•	decisions: 기록 유지
	•	포인트: 데이터 손실 없음

⸻

5. 분할 / 병합 (위험 구간)

TC-A08: 문단 분할 (1 → 2)
	•	긴 문단을 두 개로 나눔
	•	기대
	•	앞 문단: 기존 anchor 유지
	•	뒤 문단: 새 anchor 생성
	•	의도: 패치 이관 자동 금지(v0.1)

TC-A09: 문단 병합 (2 → 1)
	•	두 문단 합침
	•	기대
	•	앞 문단 anchor 유지
	•	뒤 문단 anchor 소멸
	•	패치 처리
	•	소멸 anchor의 patches → 유지하되 active 아님

⸻

6. 반복/중복 텍스트

TC-A10: 동일 문단 텍스트 2곳 존재
	•	같은 문단이 다른 위치에 복사됨
	•	기대
	•	prev/next 포함 fingerprint로 서로 다른 anchor
	•	리스크: 완전 동일 + 동일 주변 → 충돌 가능 (v0.1 허용)

⸻

7. 대규모 수정

TC-A11: 문단 70% 이상 재작성
	•	의미적으로 다른 문단
	•	기대: 새 anchor 생성
	•	포인트: score < 80

⸻

8. Pending 패치 보호

TC-A12: pending 패치가 있는 문단 소폭 수정
	•	pending 유지 상태에서 문단 수정
	•	기대
	•	anchor 유지
	•	pending 패치 유지
	•	재분석 스킵

⸻

9. 경계 블록

TC-A13: 코드 블록 내부 수정
	•	




	•	기대
	•	코드블록 전체가 하나의 anchor
	•	내부 수정에도 anchor 유지

TC-A14: 리스트 항목 추가
	•	리스트에 항목 1개 추가
	•	기대
	•	리스트 블록 anchor 유지

⸻

10. 실패 허용 케이스 (의도적)

TC-A15: 문단 내용 거의 동일 + 위치/주변 완전 변경
	•	기대: 새 anchor
	•	원칙: 오탐보다 분리 우선

⸻

A 요약 원칙 (테스트 기준)
	•	유지 실패는 허용, 오매칭은 최소화
	•	pending 보호 > anchor 완벽 일치
	•	v0.1은 “사람이 이해 가능한 안정성”이 기준

⸻

B. General diff 포맷 고정 (v0.1)

이제 Grammar / Style 패치의 출력 계약을 고정한다.

⸻

B-1. 목표 재정의
	•	사람이 한눈에 수정 내용을 이해
	•	SonE가 기계적으로 적용 가능
	•	LLM이 다음 패치 생성 시 참고 가능
	•	git diff와 유사하지만 단순화

⸻

B-2. General diff 구조 (FINAL)

diff 최상위

"diff": {
  "format": "unified",
  "hunks": [
    {
      "old": "사람은 본질적으로 이기적이다",
      "new": "사람은 본질적으로 이기적이다."
    }
  ]
}


⸻

B-3. hunk 규칙

필수 규칙
	•	old / new는 문자열
	•	문단 일부만 포함 가능 (전체 문단 금지 아님)
	•	줄 단위가 아닌 의미 단위 우선

허용 케이스
	•	맞춤법
	•	문장 다듬기
	•	중복 제거
	•	문장 순서 소폭 변경

금지 케이스 (General에서)
	•	주장 강화/약화
	•	의미 해석 변경
	•	선택지가 필요한 수정
→ 이런 건 Sophia로 보냄

⸻

B-4. 다중 hunk 허용

"diff": {
  "format": "unified",
  "hunks": [
    {
      "old": "이것은 매우 중요하다",
      "new": "이것은 중요하다"
    },
    {
      "old": "그리고 우리는 알아야 한다",
      "new": "그리고 우리는 이를 알아야 한다"
    }
  ]
}


⸻

B-5. UI 표현 규칙
	•	old → 빨간 취소선
	•	new → 초록 강조
	•	hunk 단위로 개별 드래그 선택 가능

⸻

B-6. 적용 규칙 (SonE)
	•	사용자가
	•	반영: 해당 hunk만 적용
	•	보류: diff는 적용 안 함, context_export에 요약만 남김
	•	삭제: diff 무시 + preferences 누적

⸻

B-7. Thin Context 요약 규칙 (General)

General 패치가 pending일 경우, 다음 AI에게는:

{
  "engine": "general",
  "status": "pending",
  "summary": "문장 간결화 제안 보류"
}

	•	diff 전문은 절대 넘기지 않음

⸻

B-8. 실패/안전 규칙
	•	diff 적용 실패 시:
	•	문단 전체 롤백
	•	patch status = pending 유지
	•	diff 적용 중 anchor mismatch 발생 시:
	•	적용 중단
	•	사용자 알림

⸻



⸻

C. Sophia Raw Signal JSON Schema v0.1 (FINAL)

0) 설계 목적 (고정 원칙)
	•	진위 판정 금지
	•	수정안 생성 금지
	•	외부 지식 참조 금지
	•	질문 + 선택지의 뼈대만 생성
	•	반드시 원문 인용(Evidence) 포함

Sophia의 출력은 항상 건조한 Raw Signal이며,
사용자 친화적 표현은 LLM Refinement Layer의 책임이다.

⸻

1) 최상위 구조

{
  "engine": "sophia",
  "schema_version": "0.1",
  "signals": []
}


⸻

2) Signal 단위 구조 (핵심)

{
  "signal_id": "sig_000001",
  "target_anchor": "para_a8f3c9",
  "issue_code": "EPI-01",
  "severity": "medium",
  "confidence": 0.72,
  "evidence": {
    "excerpt": "사람은 본질적으로 이기적이다",
    "range": { "start": 0, "end": 17 }
  },
  "question": {
    "type": "definition_check",
    "prompt": "이 문단에서 사용된 핵심 개념은 정의된 상태인가?"
  },
  "options": [
    { "id": "opt_1", "semantic": "keep_essential" },
    { "id": "opt_2", "semantic": "make_conditional" },
    { "id": "opt_3", "semantic": "add_definition" }
  ],
  "thin_summary": "정의 없이 개념 사용 가능성",
  "created_at": "2026-02-03T01:10:00Z"
}


⸻

3) 필드 규격 정의

3.1 공통 메타
	•	signal_id (string, required)
	•	target_anchor (string, required)
	•	issue_code (enum, required)
	•	created_at (ISO string, required)

⸻

3.2 issue_code (v0.1 고정)

코드	오류명	의미
EPI-01	Language Fixation	정의 없이 개념 고정
EPI-02	Temporal Mix	시점 혼합
EPI-03	Level Collapse	층위 붕괴
EPI-04	Process Discretization	연속 이산화
EPI-05	Frame Precedence	틀 선행
EPI-06	Agent Erasure	주체 은폐

v0.1에서는 반드시 1 signal = 1 issue_code

⸻

3.3 severity

"severity": "low | medium | high"

	•	low: 스타일/해석 여지
	•	medium: 구조적 질문 필요
	•	high: 사고 비약 가능성 큼

UI 강조용일 뿐, 판단 근거 아님

⸻

3.4 confidence (0~1)
	•	구조 패턴 매칭 신뢰도
	•	사용자에게 직접 노출 금지
	•	UI 강조, 문구 톤, 패치 자동 적용 판단에 사용 금지
	•	SonE 필터/정렬용

⸻

3.5 evidence (필수)

"evidence": {
  "excerpt": "문제 가능성이 있는 원문 일부",
  "range": { "start": 0, "end": 17 }
}

강제 규칙
	•	evidence 없으면 signal 무효
	•	excerpt는 반드시 원문에 존재해야 함

⸻

3.6 question (핵심 역할)

"question": {
  "type": "definition_check",
  "prompt": "이 문단에서 사용된 핵심 개념은 정의된 상태인가?"
}

	•	type은 구조 질문의 분류
	•	prompt는 중립적, 판정 없는 문장

question.type v0.1 세트

type	설명
definition_check	정의 유무
scope_check	주어/범위 점검
temporal_check	시점 일관성
level_check	사례↔일반 층위
process_check	과정 생략 여부
frame_check	프레임 선행 여부


⸻

3.7 options (Semantic Options)

"options": [
  { "id": "opt_1", "semantic": "keep_essential" },
  { "id": "opt_2", "semantic": "make_conditional" },
  { "id": "opt_3", "semantic": "add_definition" }
]

중요
	•	options는 의미 태그만 제공
	•	문장/톤/표현은 LLM이 생성
	•	option 개수는 2~4개 권장

⸻

3.8 thin_summary
	•	20자 내외
	•	context_export용
	•	예: "정의 누락 가능성"

⸻

4) 다중 Signal 허용 규칙

"signals": [ signal, signal, ... ]

	•	v0.1에서는 문단당 최대 1개만 허용
	•	여러 issue 감지 시:
	•	severity × confidence로 상위 1개만 출력

⸻

5) 출력 금지 규칙 (강제)

Sophia는 절대 아래를 출력하지 않는다
	•	❌ “이 문장은 틀렸다”
	•	❌ 수정 문장
	•	❌ 외부 사실/지식
	•	❌ 결론/판정
	•	❌ 사용자 성향 고려

⸻

6) SonE → LLM 가공 연결 포인트

Sophia Output
→ SonE (preferences / cooldown / 필터)
→ LLM Refinement Prompt에 주입:

{
  "raw_signal": { ... },
  "user_preferences": { ... },
  "project_context": { ... }
}


⸻

7) v0.1 완료 기준 체크리스트
	•	진위 판정 없음
	•	질문만 존재
	•	evidence 강제
	•	SonE/LLM/UI 분리
	•	manifest / patches / decisions와 정합

⸻

