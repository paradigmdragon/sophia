# Sophia Forest Agent Handoff Guide

## 목적
Sophia Forest는 "코드 실행기"가 아니라, **프로젝트 방향/진행/문제 상태를 사람이 빠르게 판단하는 운영 현황판**이다.
에이전트는 Forest를 기준으로 작업 우선순위를 맞추고, 변경 이력을 남겨 다음 에이전트가 즉시 인수인계할 수 있어야 한다.

## 에이전트 기본 원칙
- 사람에게 보여줄 화면은 단순하게 유지한다.
- 내부 분석 정보(디버그용)는 필요 시에만 상세 패널/로그에 노출한다.
- 한 번에 한 가지 핵심 작업만 진행하고, 완료/실패를 Forest에 기록한다.
- UI-only 미세수정은 남발 기록하지 않고, **시스템/문제해결/기능추가** 중심으로 기록한다.

## 핵심 데이터 구역
- 좌측 `Finder Tree`: 프로젝트/모듈/작업 선택
- 좌측 `빠른 접근`: 위험/문제/계획 Top 목록
- 우측 `CURRENT FOCUS`: 현재 미션 1개 + 진행률
- 우측 `Top 3 실행`: 즉시 액션(ACK/완료/작업 생성)
- 우측 `테이블`: 카테고리/상태/진행률/리스크/업데이트 시간
- 우측 `계획서`: READY/IN_PROGRESS/DONE 단계별 작업 목록
- 우측 `명세서`: 프로젝트 기준 공식 문서 목록 + 구현 반영 상태
- 우측 `병렬작업`: owner/lane별 작업 분할 현황 (Codex/다른 IDE 병행)

## Forest에서 다루는 범위(중요)
- `scope=forest`: 소피아숲 자체 기능/운영 개선 작업
- `scope=project`: 소피아 전체 프로젝트 기능 작업
- Forest 화면에서는 두 범위를 함께 보되, **동일한 작업으로 혼동되지 않게 scope를 반드시 기록**한다.
- 예: `Bitmap 저장/검증 파이프라인`은 `core/project` 범위이며, 소피아숲 자체 기능과 구분해야 한다.

## 병렬 작업 분할 규약(owner/lane)
- 모든 roadmap 기록은 가능하면 `owner`, `lane`을 포함한다.
- 권장값:
  - Codex 작업: `owner=codex`, `lane=codex`
  - 외부 IDE 작업: `owner=cursor` 또는 `owner=antigravity`, `lane`도 동일
- 같은 기능을 병렬로 만질 때는 서로 다른 `lane`으로 분할해 충돌을 줄인다.
- 병렬 작업 판은 lane별 `ACTIVE/READY/BLOCKED/DONE` 카운트로 상태를 즉시 확인한다.

## 명세 기반 작업 규약(spec workflow)
- 공식 문서(명세/헌법/계획서)는 `Docs/`, `docs/`, `spec/` 아래에서 관리한다.
- 작업 시작 전:
  1. 명세서 선택
  2. 구현 상태 확인
  3. 분기점(추가 아이디어/수정 요청) 체크
- 작업 중 변경이 생기면:
  - `spec/review-request`로 검토 요청을 남겨 다음 에이전트가 이어서 처리할 수 있게 한다.
- 목표: "채팅 스크롤"이 아니라 "명세서 기준"으로 작업 맥락을 복원 가능하게 유지.

## 작업 시작 루틴(필수)
1. `status/sync` 실행으로 최신 상태 동기화
2. `CURRENT FOCUS`와 `Top 3 실행` 확인
3. 가장 중요한 1개 작업 선택
4. 구현/수정 수행
5. `roadmap/record`로 결과 기록
6. 다시 `status/sync` 후 다음 액션 갱신

## 기록해야 하는 작업(권장)
- `SYSTEM_CHANGE`: 구조/정책/동기화 로직 변경
- `PROBLEM_FIX`: 버그 해결, 상태 불일치 복구
- `FEATURE_ADD`: 사용자 가치가 있는 기능 추가

## 기록 예시
- title: `Top3 work actions optimistic status update`
- summary: `ACK/완료 클릭 직후 상태를 즉시 반영하고 sync parity에서 자동 정리`
- tags: `phase:4`, `phase_step:4.18`, `top3`
- files: 실제 변경 파일 절대경로 또는 repo상대경로

## 자주 쓰는 API
- `POST /forest/projects/{project}/status/sync`
- `GET /forest/projects/{project}/canopy/data`
- `POST /forest/projects/{project}/roadmap/record`
- `POST /forest/projects/{project}/roadmap/sync`
- `GET /forest/projects/{project}/spec/index`
- `GET /forest/projects/{project}/spec/read?path=...`
- `POST /forest/projects/{project}/spec/review-request`
- `POST /work/packages/{id}/ack`
- `POST /work/packages/{id}/complete`
- `POST /forest/projects/{project}/work/generate`

## 금지 사항
- Forest를 임시 메모장처럼 사용하지 않는다.
- 동일 의미의 기록을 반복 적재하지 않는다.
- 사람이 판단할 필요 없는 내부 신호를 메인 화면에 과도하게 뿌리지 않는다.
- `owner/lane/scope` 없이 대형 작업을 기록하지 않는다.
- 명세 분기점을 기록하지 않고 구현부터 진행하지 않는다.

## 인수인계 체크리스트
- [ ] 현재 미션/다음 액션이 의미 있는 문장으로 보이는가
- [ ] 문제/위험/계획 Top 목록이 실제 데이터와 일치하는가
- [ ] 방금 수행한 변경이 roadmap journal에 기록되었는가
- [ ] 병렬 lane(owner/lane) 분할이 되어 있는가
- [ ] 명세서 링크(spec_ref)와 검토 요청 상태가 최신인가
- [ ] 다음 에이전트가 이 파일만 읽고 시작 가능한가
