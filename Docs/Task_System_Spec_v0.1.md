# Task System Spec v0.1

## 1. Task Definition

### 1.1 Storage & Format
- **Location**: `workspace/tasks/`
- **Format**: JSON (Single file per task)
- **Naming Convention**: `{timestamp}_{task_id}.task.json` (e.g., `20260206_subtitle_pipeline_001.task.json`)

### 1.2 Schema
```json
{
  "task_id": "subtitle_pipeline_001",
  "run_id": "run_12345", 
  "created_at": "2026-02-06T10:30:00Z",
  "status": "queued", 
  "type": "transcription",
  "requested_by": "user",
  "tool": "sophia-desktop-v0.1.4",
  
  "config_snapshot": {
    "engine": { "type": "faster_whisper", "model": "medium" },
    "refine": { "enabled": true }
  },
  
  "input": {
    "media": "workspace/inbox/meeting_audio.mp3",
    "script": null
  },
  
  "pipeline": [
    "asr",
    "refine"
  ],
  
  "output": {
    "raw_srt": "workspace/outputs/subtitles/raw/meeting_audio.raw.srt",
    "refined_srt": "workspace/outputs/subtitles/refined/meeting_audio.refined.srt"
  },
  
  "error": null
}
```

### 1.3 Status Lifecycle
- `queued`: Created, waiting for pickup.
- `running`: Picked up by Runner (Locked).
- `done`: Successfully completed.
- `failed`: Error occurred during execution.
- `canceled`: User requested cancellation.

---

## 2. Event Stream

### 2.1 Storage & Format
- **Location**: `workspace/events/`
- **Format**: NDJSON (One event per line)
- **File Naming**: `{date}_events.jsonl` (Rotated daily or per session)

### 2.2 Event Schema
All events share these common fields:
```json
{
  "ts": "2026-02-06T10:31:00.123Z",
  "run_id": "run_12345",
  "task_id": "subtitle_pipeline_001",
  "type": "task.started",
  "payload": { ... }
}
```

### 2.3 Event Types
| Type | Payload | Description |
|HT|HT|HT|
| `task.created` | `{ "input": "..." }` | Task file created |
| `task.started` | `{ "pipeline": [...] }` | Processing started |
| `stage.progress` | `{ "stage": "asr", "progress": 0.5, "msg": "..." }` | Granular progress |
| `artifact.written` | `{ "path": "...", "kind": "raw_srt" }` | Output file generated |
| `task.completed` | `{ "duration_sec": 12.5 }` | Success |
| `task.failed` | `{ "error": "Disk full", "stack": "..." }` | Failure |

---

## 3. Core Implementation

### 3.1 Components
- **TaskLoader**: Scans `workspace/tasks` for `queued` tasks.
- **TaskRunner**: Executes the pipeline logic, handles locking.
- **EventWriter**: Appends events to NDJSON stream.
- **Atomic Locking**:
    - Rename `*.task.json` -> `*.task.json.lock` (or field update)?
    - **Spec Decision**: Status field update is simpler for JSON. But file rename (moving to `running/` subdir or rename extension) provides better atomicity on file systems.
    - **Decision**: Update `status` field in-place using a file lock (.lock file sidecar) to prevent race conditions, OR simpler: Rename file to `.running.json` while processing.
    - **Chosen Approach**: **In-place status update with .lock file**.
        1. Acquire `taskname.lock`.
        2. Read Task.
        3. If `queued`, set `running`, write back.
        4. Release `taskname.lock`.
        5. Execute.
        6. Set `done/failed`, write back.

### 3.2 Error Handling
- Capture full stack trace in `error` field of Task JSON.
- Emit `task.failed` event.
- Ensure `state` reflects failure.
- Intermediate files (in `outputs/_tmp`) are cleaned up or left for debug (configurable). Inputs preserved.

---

## 4. Deliverables
- `docs/Task_System_Spec_v0.1.md`
- `core/app/task/` module
- CLI Commands: `sophia-cli run --watch`, `sophia-cli run --task <id>`
- Integration Tests
