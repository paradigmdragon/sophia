# Sophia Workspace Specification v0.1

(Local-first / Agent-shared / File-driven)

## 0. 기본 원칙 (절대 불변)
1.  Sophia는 프로그램이 아니라 **Workspace**다.
2.  모든 기능은 **파일 생성·수정·이동**으로만 표현된다.
3.  OSS와 IDE 에이전트는 **동일한 Workspace를 공유**한다.
4.  권한 차이는 “어떤 파일을 수정할 수 있느냐”로만 구분한다.

---

## 1. 작업 주체 정의

### 1.1 Local LLM (GPT-OSS)
- **실행 위치**: Sophia Desktop App 내부
- **권한**:
    - ⭕ 콘텐츠 파일 생성/수정
    - ⭕ SonE 문서 생성/수정
    - ❌ 코드 수정
    - ❌ 파이프라인 로직 변경
- **성격**: 안전한 자동화 작업자

### 1.2 IDE 에이전트 (Cursor / Antigravity 등)
- **실행 위치**: 외부 IDE
- **권한**:
    - ⭕ 모든 파일 접근
    - ⭕ 코드 수정
    - ⭕ 파이프라인 추가/변경
    - ⭕ 설정 스키마 변경
- **성격**: 개발자·설계자·확장자

---

## 2. Sophia Workspace 루트 구조

```
Sophia/
├─ workspace/              # 실질 작업 공간 (핵심)
│  ├─ inbox/               # 입력 파일 (음성, 영상, 스크립트)
│  ├─ outputs/             # 결과물
│  │  ├─ subtitles/
│  │  │  ├─ raw/
│  │  │  ├─ refined/
│  │  │  ├─ points/
│  │  │  └─ summary/
│  │  ├─ text/
│  │  └─ reports/
│  ├─ sone/                # SonE 문서 저장소
│  │  ├─ generated/        # OSS가 생성한 SonE
│  │  └─ manual/           # 사람이 작성/수정한 SonE
│  ├─ tasks/               # 작업 지시 파일
│  ├─ events/              # 실행 이벤트 스트림 (JSON)
│  └─ state/               # 상태 스냅샷
│
├─ runtime/                # 실행 중 생성 파일 (자동)
│  ├─ runtime_config.json
│  └─ session.lock
│
├─ core/                   # Python Core (IDE 전용)
│
└─ apps/
   └─ desktop/             # Tauri App
```

---

## 3. OSS 권한 범위 (중요)

OSS는 다음 디렉토리만 접근 가능하다.

- `workspace/inbox/`
- `workspace/outputs/`
- `workspace/sone/generated/`
- `workspace/tasks/`
- `workspace/events/`
- `workspace/state/`

### ❌ OSS 금지 영역
- `core/`
- `apps/`
- `workspace/sone/manual/`
- `runtime/`

OSS는 SonE를 생성할 수는 있지만, **SonE 실행 규칙 자체를 바꾸지는 못한다.**

---

## 4. Task 시스템 (OSS · IDE 공통)

### 4.1 Task 파일 위치
`workspace/tasks/*.task.json`

### 4.2 Task 기본 포맷
```json
{
  "task_id": "subtitle_pipeline_001",
  "requested_by": "user | oss | ide",
  "input": {
    "media": "workspace/inbox/video.mp4",
    "script": "workspace/inbox/script.txt"
  },
  "pipeline": [
    "asr",
    "refine",
    "point_subtitle",
    "summary_subtitle",
    "sone_generate"
  ],
  "status": "pending"
}
```
- OSS는 task를 읽고 실행한다.
- IDE 에이전트는 task를 생성·수정 가능하다.

---

## 5. 자막 파이프라인 규칙 (확정)

### 5.1 기준 자막 (1번)
- **파일**: `outputs/subtitles/raw/{name}.raw.srt`
- **역할**: 모든 타임코드의 기준

### 5.2 파생 자막 규칙 (절대 변경 불가)
**✅ 핵심 원칙**: 2번·3번 자막은 **1번 자막의 타임코드를 그대로 재사용한다.**

#### 예시

**원본 (Raw)**
```srt
5
00:00:15,500 --> 00:00:20,000
(원본 대사)
```

**→ 포인트 자막 (Points)**
```srt
5
00:00:15,500 --> 00:00:20,000
[중요] 핵심 주장 요약
```

**→ 요약 자막 (Summary)**
```srt
5
00:00:15,500 --> 00:00:20,000
이 구간의 핵심 요점
```

- ⛔ **타임코드 재계산 금지**
- ⛔ **새 타임코드 생성 금지**

---

## 6. SonE 문서 생성 규칙 (OSS 허용)

### 6.1 SonE 생성 목적
- 사용자에게 보여주기 ❌
- AI 내부 점검·검증·후속 자동화용

### 6.2 생성 위치
`workspace/sone/generated/{task_id}.sone`

### 6.3 SonE 생성 범위
OSS가 생성 가능한 SonE는:
- 구조 요약
- 논리 흐름
- 모순 후보
- 반복 패턴
- 중요 이벤트 마커

**예시:**
```sone
! on subtitle.segment[5]
? contains.core_claim == true
@ internal
: mark.key_point
```

---

## 7. 이벤트 스트림 규칙

### 7.1 이벤트 파일
`workspace/events/{timestamp}.json`

### 7.2 예시
```json
{
  "event": "subtitle.generated",
  "task_id": "subtitle_pipeline_001",
  "output": "raw.srt",
  "agent": "oss",
  "timestamp": "2026-02-06T10:12:00"
}
```
IDE 에이전트는 이 이벤트를 보고 병렬 작업을 수행할 수 있다.

---

## 8. 병렬 실행 전제 (중요)
- OSS 작업 중에도 IDE 에이전트는 다음 작업을 수행할 수 있다:
    - SonE 문서 분석
    - 새 파이프라인 코드 작성
    - 설정 수정

**단, 같은 파일을 동시에 수정하지 않는다.** (충돌 회피는 인간/IDE 에이전트 책임)

---

## 9. 이 명세의 의미
Sophia는 이제:
- ❌ “자막 프로그램”
- ❌ “LLM 앱”
- ⭕ **에이전트 공용 작업 공간 (Agent Shared Workspace)**
- OSS는 **안전한 기능 수행**을 담당하고,
- IDE 에이전트는 **진화**를 담당한다.
