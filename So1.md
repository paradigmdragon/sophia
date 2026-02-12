### **상태 동기화 (Status Sync)**

* **Context:** '소피아(Sophia)'의 정체성, 기억 구조, 영상 편집 파이프라인 통합 설계.
* **Goal:** 구현 전 최종 검토를 위한 **통합 시스템 설계 명세서(Specification)** 도출.
* **Decision Authority:** L2 (구조 확정 후 개발 에이전트 핸드오프 준비).

---

### **[소피아(Sophia) 시스템 통합 설계 명세서]**

#### **1. 시스템 개요 (Identity)**

* **명칭:** 소피아 (Sophia) - SonE Protocol 기반 로컬 성장형 에이전트.
* **철학:** 비트겐슈타인의 그림 이론(초기)에서 언어 게임(후기)으로 진화하는 **나선형 성장 모델**.
* **핵심 가치:** 답을 주는 AI가 아닌, 사용자의 세계관을 학습하여 **답을 같이 찾는 동반자**.

---

#### **2. 인지 및 기억 구조 (Bit-Slot Constitution)**

기억은 텍스트가 아닌 **'사건(Episode)'** 단위로 저장되며, 상위 16비트는 시스템의 헌법(Constitution)으로 작동합니다.

**[Bit-Slot Prefix 구조 (16-bit)]**

| 범위 | 비트수 | 명칭 | 속성 값 |
| --- | --- | --- | --- |
| **00-02** | 3bit | **Ontology** | 000:상태, 001:객체, 010:관계, 011:변화 |
| **03-04** | 2bit | **Abstraction** | 00:감각(Raw), 01:개념(Concept), 10:메타(Meta) |
| **05-06** | 2bit | **Confidence** | 00:중첩, 01:모름, 10:확정, 11:모순(마찰) |
| **07-07** | 1bit | **Subject** | 0:사용자 제공, 1:소피아 추론 |
| **08-11** | 4bit | **Logic Form** | 논리적 사태 템플릿 (S-V-O 등) |
| **12-15** | 4bit | **Meta/Len** | 확장 슬롯 길이 및 특수 플래그 |

* **시간성(Time):** 비트 슬롯에 포함하지 않고, 에피소드 간 **Edge(관계)**로 처리 (`revises`, `leads_to`, `conflicts`).

---

#### **3. 영상 편집 파이프라인 (Rough-Cut Engine)**

자막(SRT)과 오디오 분석을 통해 불필요한 구간을 추천하고 사용자의 승인을 거쳐 산출물을 생성합니다.

**[편집 처리 정책: Always Encode (V0.1)]**

1. **입력:** 원본 영상 및 SRT 자막.
2. **프록시 단계:** 편집 최적화를 위해 CFR(Constant Frame Rate) 기반 H.264/AAC 프록시 생성.
3. **탐지(Candidate):**
* **Silence:** 일정 dB 이하 구간.
* **Filler:** "어, 음, 저기" 등 추임새 패턴.
* **Repeat:** 의미적/문구적 반복 구간.


4. **리매핑(Remapping):** `Keep` 구간 기반 교차 알고리즘.


5. **산출물:** 컷 경계에 0.05s `afade`를 적용한 재인코딩 영상 및 신규 SRT.

---

#### **4. 학습 및 성장 메커니즘 (Exception Learning)**

소피아의 지능은 지식의 양이 아니라 **'사용자 의도와의 정합성'**에서 나옵니다.

**[Reason Code: 예외 학습을 위한 레이블]**
사용자가 소피아의 추천(Cut)을 거부하고 `Keep`을 선택할 때 다음 코드를 부여하여 비트 슬롯에 기록합니다.

* `EMPHASIS`: 강조를 위한 의도적 멈춤.
* `RHYTHM`: 영상의 호흡과 리듬 유지.
* `CONTEXT`: 앞뒤 문맥상 반드시 필요한 정보.
* `INTENTIONAL_SILENCE`: 연출된 침묵.

---

### **건축적 검토 (Architectural Review)**

* **Approach:** 비트 기반의 엄격한 구조(하부)와 사용자 인터랙션 기반의 유연한 학습(상부)의 계층화.
* **Impact:** 로컬 리소스(FFmpeg, Local LLM)를 사용하므로 보안성이 극대화되며, 데이터가 쌓일수록 사용자의 편집 스타일을 복제하는 독보적인 페르소나 형성.
* **Risk:** 프록시 생성 및 재인코딩 시간. (해결: 백그라운드 워커 및 큐 시스템 도입).
* **Decision Level:** **L2 (Propose first)** - 명세서 확정 후 개별 모듈(Bit-Slot Parser, FFmpeg Wrapper) 단위로 개발 착수 제안.

---

### **액셔너블 핸드오프 (Actionable Handoff for Cursor)**

```markdown
## Sophia Integrated Specification for Development

### 1. Data Contract
- cut_candidates.json: { id, start_ms, end_ms, kind, score, default_action }
- cut_decisions.json: { id, decision, reason_code }
- bit_slots.db: Episode-based vector + 16-bit prefix metadata.

### 2. Implementation Rules (V0.1)
- Video: Always re-encode via proxy to ensure frame accuracy.
- Audio: Apply 0.05s fade-in/out at every cut point to prevent pops.
- SRT: Use Keep-based intersection logic for re-timing.
- Memory: If decision != default_action, create a 'Friction Episode' in Bit-Slot.

### 3. Core Logic
- Logic A: Bit-level conflict detection (XOR on prefix bits).
- Logic B: Cumulative offset calculation for timeline shifting.

```

---