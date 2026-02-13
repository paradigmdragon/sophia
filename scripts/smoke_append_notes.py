from sophia_kernel.notes.note_writer import append_note

SAMPLE_DATA = [
  {
    "namespace": "notes",
    "title": "커널 진행 로그",
    "body": "Registry/Executor/Verifier/Audit + read/write + memory.append까지 Phase-1 도달.",
    "tags": ["kernel", "phase1"],
    "refs": {"date": "2026-02-13"}
  },
  {
    "namespace": "ideas",
    "title": "노트 자동 분류 후보",
    "body": "notes/ideas/decisions/actions 4분류를 기반으로, 추후 스키마 고정 전에 실제 로그 패턴을 수집한다.",
    "tags": ["notes", "taxonomy"],
    "refs": {}
  },
  {
    "namespace": "decisions",
    "title": "스키마 고정은 후순위",
    "body": "스키마는 당장 고정하지 않고, 1~2주 운영 로그를 보고 note schema v0.1을 확정한다.",
    "tags": ["decision", "schema"],
    "refs": {"reason": "초기 변동성 높음"}
  },
  {
    "namespace": "actions",
    "title": "다음 구현 순서",
    "body": "1) note_writer 도입 2) smoke script 3) IDE 작업 로그를 memory.append로 자동 적재 4) 이후 schema 확정",
    "tags": ["todo", "next"],
    "refs": {}
  }
]

if __name__ == "__main__":
    for item in SAMPLE_DATA:
        result = append_note(
            namespace=item["namespace"],
            title=item["title"],
            body=item["body"],
            tags=item["tags"],
            refs=item["refs"],
        )
        print("APPENDED:", result)
