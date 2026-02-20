# SonE-Lite Command Specification v0.1

**Objective:** Define the JSON schema for automation tasks in Phase 1 (Foundation).
**Audience:** Codex 5.3 (Backend Implementation) & Antigravity (Command Generation).

## 1. Overview
SonE-Lite is a simplified, JSON-based implementation of the full SonE Protocol. It allows Sophia to execute discrete tasks (Shell, Python, HTTP) and chain them into basic workflows. It avoids the full DSL parsing complexity of v2.0 in favor of a robust JSON schema.

## 2. Command Schema

Each SonE-Lite command is a JSON object with the following structure:

```json
{
  "command_id": "cmd_<uuid>",
  "name": "Human Readable Name",
  "type": "shell | python | http | workflow",
  "priority": "P1 | P2 | P3 | P4", // Matches Heart Engine
  "payload": { ... }, // Type-specific data
  "schedule": {
    "type": "immediate | cron | event",
    "value": "* * * * *" // For cron, or event details
  },
  "dependencies": ["cmd_<uuid>"], // Wait for these to succeed
  "timeout": 30, // Seconds
  "retry": {
    "count": 3,
    "delay": 5
  }
}
```

## 3. Payload Types

### 3.1 Shell Command (`type: "shell"`)
Executes a system command. 
*Constraint:* Sandbox restrictions apply (cwd, allowed binaries).

```json
"payload": {
  "command": "ls",
  "args": ["-la", "/Users/dragonpd/Sophia"],
  "cwd": "/Users/dragonpd/Sophia",
  "env": { "DEBUG": "true" }
}
```

### 3.2 Python Function (`type: "python"`)
Executes an internal Python function within the Sophia Core environment.

```json
"payload": {
  "module": "core.engine.workflow",
  "function": "WorkflowEngine.ingest",
  "args": [],
  "kwargs": { "log_ref": "..." }
}
```

### 3.3 HTTP Request (`type: "http"`)
Makes an external API call.

```json
"payload": {
  "method": "POST",
  "url": "https://api.example.com/v1/webhook",
  "headers": { "Authorization": "Bearer ..." },
  "body": { "event": "ingest_complete" }
}
```

### 3.4 Workflow Chain (`type: "workflow"`)
Defines a sequence of sub-commands.

```json
"payload": {
  "steps": [
    { "command_id": "step_1", "type": "shell", ... },
    { "command_id": "step_2", "type": "python", "dependencies": ["step_1"], ... }
  ]
}
```

## 4. Integration with Heart Engine

*   **Queueing:** SonE-Lite commands are enqueued into the `MessageQueue` or a separate `TaskQueue` (to be defined by Codex).
*   **Execution:** The `HeartEngine` (Dispatcher) picks up tasks based on Priority.
*   **Logging:** Execution results (Stdout/Stderr/ReturnCode) must be logged to `Event` table and `logs/tasks/{date}.jsonl`.

## 5. Codex 5.3 Implementation Requirements
1.  **Task Scheduler:** Implement a scheduler (e.g., `APScheduler` or custom loop) to handle `cron` and `event` triggers.
2.  **Executor:** Implement the logic to execute `shell`, `python`, `http` payloads safely.
3.  **Persistence:** Store command definitions in the SQLite database (Schema TBD by Codex).
4.  **API:** Provide `POST /sone/commands` to register new commands.

## 6. Future Migration (SonE v2.0)
This JSON structure maps directly to the compiled AST of the full SonE DSL.
*   `type` -> DSL Verb (EXEC, CALL, REQ)
*   `schedule` -> DSL Trigger (WHEN)
*   `dependencies` -> DSL Flow (THEN)
