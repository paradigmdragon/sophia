# Sophia Forest Canopy 재구성 계획 v1

## 목표
- Forest를 `설계-검토-상태 관제` 전용으로 고정
- SonE 검증 결과를 기준으로 `무엇을 했고 / 무엇이 남았는지 / 무엇이 위험한지`를 한 화면에서 파악
- 입력 경로를 단순화: 업로드 파일 또는 에디터 저장 MD를 바로 Grove 분석으로 연결

## SSOT 원칙
- Forest는 실시간 시스템 모니터가 아니라 프로젝트 현황판
- SonE는 분석 IR 캐시(사람에게는 요약/경고/영향 범위만 노출)
- 학습/성장 지표는 Forest 기본 데이터에서 제외

## 정보 구조
1. **Module Overview**
- 채팅, 소피아 노트, 에디터, 자막 편집, 소피아 숲
- 모듈별 진행률/중요도/BLOCKED/Q 개수

2. **Roadmap / Progress**
- IN_PROGRESS / PENDING·BLOCKED / DONE(RECENT)
- 작업별 우선순위 점수와 마지막 갱신 시각

3. **SonE Validation Summary**
- source_doc, missing_slots, impact_targets, risk_cluster_count, max_risk

4. **Dependency / Execution Map**
- Module -> Work -> Question 연결 맵(Mermaid)

5. **Question Queue / Recent Change Log**
- 리스크 클러스터 표
- 이벤트 타임라인 표

## 입력 플로우
- `POST /forest/projects/{project}/grove/analyze` : 업로드 파일 텍스트 분석
- `POST /forest/projects/{project}/grove/analyze/path` : 저장된 MD/TXT 경로 분석
- `POST /forest/projects/{project}/canopy/export` : HTML 현황판 갱신

## 완료 기준
- Canopy 응답에서 module_overview/roadmap/sone_summary/topology 제공
- Dashboard HTML에서 위 5개 블록 확인 가능
- 에디터 파일 경로 기반 SonE 분석 가능
- Forest API 테스트 통과
