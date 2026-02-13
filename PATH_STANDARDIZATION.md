# PATH STANDARDIZATION

작성 기준: 이미 확보한 경로 정보만 사용 (추가 탐색 없음)

## 1) 현재 경로 상태

계획 경로(현재 미존재)
- `/Users/dragonpd/Sophia/sophia_workspace`
- `/Users/dragonpd/Sophia/sophia_workspace/logs`
- `/Users/dragonpd/Sophia/sophia_workspace/reports`
- `/Users/dragonpd/Sophia/sophia_workspace/patches`

기존 사용 경로(확인됨)
1. 로그
- `/Users/dragonpd/Sophia/logs/chat`
- `/Users/dragonpd/Sophia/logs/asr`

2. 출력/리포트
- `/Users/dragonpd/Sophia/workspace/outputs/*`
- `/Users/dragonpd/Sophia/workspace/outputs/reports` (디렉터리 존재, 파일은 확인되지 않음)

3. 작업 큐
- `/Users/dragonpd/Sophia/workspace/tasks`
- `/Users/dragonpd/Sophia/workspace/events`

4. 메모리/패치
- `/Users/dragonpd/Sophia/memory/memory_manifest.json` (`patches` 포함)

5. rough-cut 전용
- `/Users/dragonpd/Sophia/core/workspace/video/*`

## 2) 충돌/중복 평가

### A. `logs` 중복 가능성
- 신규 `sophia_workspace/logs` 도입 시, 기존 `/Users/dragonpd/Sophia/logs/*`와 이중화 위험
- 현재 코드 다수는 기존 `/Users/dragonpd/Sophia/logs/*`를 직접 참조

### B. `reports` 중복 가능성
- 신규 `sophia_workspace/reports` vs 기존 `/Users/dragonpd/Sophia/workspace/outputs/reports`
- 현재 런타임은 실제 산출물을 주로 `workspace/outputs` 루트에 기록

### C. `patches` 위치 불일치
- 신규 `sophia_workspace/patches` 계획 vs 현행 `memory/memory_manifest.json` 내 `patches` 구조
- 파일 시스템 패치 디렉터리와 manifest 기반 패치가 병행될 경우 소스오브트루스 혼선 가능

### D. 워크스페이스 이원화
- `workspace/*`와 `core/workspace/*`가 병행 사용되어 운영/백업 단위 분산

## 3) 표준 경로 제안 (권장안)

권장 원칙
1. 운영 데이터는 하나의 루트에서 관리
2. 소스오브트루스는 명확히 1개만 유지
3. 코드 하드코딩 경로는 점진적으로 설정 기반으로 치환

권장 표준 맵
1. Runtime Queue/Artifacts
- canonical: `/Users/dragonpd/Sophia/workspace/*` 유지

2. Logs
- canonical: `/Users/dragonpd/Sophia/sophia_workspace/logs`
- transition: 기존 `/Users/dragonpd/Sophia/logs`는 호환 레이어(읽기 전용 또는 동기화 대상)로 단계적 축소

3. Reports
- canonical: `/Users/dragonpd/Sophia/sophia_workspace/reports`
- transition: `workspace/outputs/reports` -> canonical로 집계 export

4. Patches
- canonical storage: `/Users/dragonpd/Sophia/memory/memory_manifest.json` 유지
- optional export path: `/Users/dragonpd/Sophia/sophia_workspace/patches` (manifest 스냅샷/리포트 전용)

5. Rough-cut
- canonical 후보: `/Users/dragonpd/Sophia/workspace/video/*`
- 현행 `core/workspace/video/*`는 legacy로 분류

## 4) 단계별 표준화 계획 (변경 제안, 미적용)

Phase 1: 선언/문서화
1. 표준 경로 사전 확정 (logs/reports/patches)
2. 소스오브트루스 정의서 작성 (manifest vs 파일 export)

Phase 2: 읽기 경로 다중 허용
1. 신규 경로 우선 조회, 기존 경로 fallback
2. UI/Runner에서 경로 해석 규칙 통일

Phase 3: 쓰기 경로 단일화
1. 신규 canonical 경로로만 쓰기
2. 기존 경로는 마이그레이션 후 읽기 전용

## 5) 즉시 적용 가능한 운영 가드레일

1. `sophia_workspace/patches`를 “운영 패치 저장소”로 쓰지 말고 export/리포트 전용으로 한정
2. 로그 수집/모니터링은 단기적으로 `/Users/dragonpd/Sophia/logs/*`를 기준으로 유지
3. `workspace/outputs/reports`와 신규 `sophia_workspace/reports`를 동시에 활성화하지 말고, 집계 방향(원본/미러) 먼저 결정

## 6) 확인 필요

1. 실제 프로세스 기준 현재 활성 쓰기 경로 우선순위 (실행 상태 점검 미완료)
2. `sophia_workspace` 생성 시점과 생성 주체(수동/런타임)
3. `patches`를 파일 디렉터리로 병행 운용할지 여부(manifest 단일화 vs 이중화)

