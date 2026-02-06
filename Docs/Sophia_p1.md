

sophia v0.1 구현 지시서 (Subtitle ASR MVP)

0. 목표 정의

v0.1 범위(필수)
	•	사용자가 inbox/ 폴더에 mp3/mp4/m4a/wav 등을 넣고
	•	“실행(명령/버튼)”하면
	•	로컬 Whisper 계열 엔진으로 받아쓰기 수행
	•	outbox/에 *.raw.srt 생성
	•	원본 파일은 processed/로 이동
	•	실행 로그/메타는 logs/에 기록

v0.1 범위(제외)
	•	맞춤법/오탈자/스타일 교정
	•	talk/points/summary 생성
	•	서버 동기화(Manifest)
	•	SAP64 연출 액션 생성
	•	로컬 LLM(Ollama) Refiner

v0.1은 “ASR 공장”만. 나머지는 v0.2+ 모듈로 추가.

⸻

1. 아키텍처 원칙

1.1 모듈 분리(3 모듈만)
	1.	Ingress: 입력 파일 감지/안정화/큐 생성
	2.	ASR Engine: Whisper 기반 받아쓰기 → 세그먼트
	3.	Artifact Writer: SRT 저장 + 메타/로그 저장 + 파일 이동

각 모듈은 “입출력 계약”으로만 연결. 내부 구현은 교체 가능.

1.2 SonE의 역할(코드가 아니라 “계약 선언”)
	•	sophia는 실행 로직과 별개로, 워크플로우/폴더/산출물/정책을 SonE 파일로 선언한다.
	•	v0.1에서는 최소 1개 SonE 선언만 있으면 된다.

⸻

2. 프로젝트 구조(고정)

루트 폴더에 아래 구조를 고정 생성

sophia/
  inbox/
  outbox/
  processed/
  logs/
  sone/
    subtitle.asr.sone
  sophia_cli/          (또는 src/)
  README.md


⸻

3. SonE 선언 파일(필수) : sone/subtitle.asr.sone

목적
	•	v0.1에서 “무엇을 입력으로 받아 무엇을 출력해야 하는지”를 시스템이 읽을 수 있는 형태로 고정
	•	v0.2에서 Manifest/SAP64 연결 시에도 이 선언을 그대로 확장

선언에 반드시 포함할 항목
	•	workflow id / version
	•	folders: inbox/outbox/processed/logs
	•	supported input extensions
	•	output naming rule
	•	language=ko
	•	model preset (quality/fast)
	•	policy: 타임코드/인덱스 규칙, 의미 보존(후처리 대비)
	•	log schema version

중요: 표 없이 “설명형 명세”로 작성(현재 네 문서 스타일과 일치)

⸻

4. ASR 엔진 선택(결정)

기본 엔진(권장)
	•	faster-whisper + 모델 large-v3
	•	이유: Mac Silicon에서 속도/안정성 좋고 Whisper 계열 인식률 확보

대안 엔진
	•	openai-whisper CLI
	•	단점: 대체로 느릴 수 있음

v0.1은 엔진 1개만 탑재. 엔진 교체는 v0.2 플러그인으로.

⸻

5. 실행 인터페이스(필수)

최소 요구
	•	터미널에서 1줄로 실행 가능해야 한다.

예시(형태만, 구현은 에이전트가 결정)
	•	sophia run subtitle.asr
	•	또는 python -m sophia_cli asr

실행 동작(정확히 일치해야 함)
	1.	inbox/ 스캔
	2.	지원 확장자만 처리 대상 등록
	3.	파일 안정화(크기 변동 없는지 N초 확인)
	4.	ASR 실행
	5.	outbox/{stem}.raw.srt 생성
	6.	logs/{stem}.run.json 생성
	7.	처리 성공 시 원본을 processed/로 이동
	8.	실패 시 logs/{stem}.error.json 생성, 원본은 inbox에 남김(재시도 가능)

⸻

6. 산출물 계약(고정)

outbox
	•	{name}.raw.srt (필수)

logs
	•	{name}.run.json (필수)
	•	workflow_id, workflow_version
	•	engine(faster-whisper), model(large-v3), device(cpu/mps)
	•	input file hash/size/duration(가능하면)
	•	segments count
	•	started_at / finished_at / elapsed_ms
	•	status(success/fail)
	•	{name}.error.json (실패 시)
	•	error_type, message, stack(optional)
	•	failed_step(ingress/asr/write/move)

⸻

7. SRT 생성 규칙(필수)
	•	SRT 인덱스는 1부터 증가
	•	타임코드는 HH:MM:SS,mmm 형식
	•	각 cue 텍스트는 Whisper 세그먼트 텍스트를 그대로 사용(후처리 없음)
	•	공백/빈 줄만 최소 정리

⸻

8. 운영 모드(권장, v0.1에서 2개만)
	•	quality: large-v3
	•	fast: medium 또는 small

SonE 선언에서 preset으로 선택 가능하게만 해두고, v0.1 구현은 기본 quality 고정해도 됨.

⸻

9. 테스트 시나리오(필수)
	1.	짧은 mp3(30초~2분) 1개
	2.	10분 이상 mp4 1개

검증 체크:
	•	outbox에 raw.srt 생성
	•	logs에 run.json 생성
	•	processed로 원본 이동
	•	실패 시 error.json만 생성되고 inbox에 원본 유지

⸻

10. README에 반드시 들어갈 내용(최소)
	•	설치(ffmpeg, python env)
	•	실행 방법(1줄)
	•	폴더 규약(inbox/outbox/processed/logs)
	•	출력 파일 설명(raw.srt, run.json)
	•	v0.1 범위(후처리 없음) 명시

⸻

11. v0.2 확장 포인트(지금은 구현하지 말고 “훅만” 만들어두기)
	•	Refiner 모듈: IDE 에이전트/로컬 LLM/Ollama 연결
	•	Knowledge 모듈: 자막/용어/사용자 말투 데이터 축적
	•	Manifest Sync 모듈: logs/meta를 손잡고 서버에 동기화
	•	SAP64 Action 모듈: 자막 구간을 연출 액션 후보로 변환

v0.1 코드/폴더는 이 확장 포인트를 막지 않도록, “모듈 경계”만 분명히.

⸻

구현 완료 정의(Definition of Done)
	•	sone/subtitle.asr.sone 존재
	•	inbox -> outbox raw.srt -> processed 이동 -> logs run.json 정상 동작
	•	실패 시 error.json + 재시도 가능
	•	후처리(맞춤법/요약/포인트)는 v0.1에 없음

⸻
