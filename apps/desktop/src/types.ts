export type TaskStatus = 'queued' | 'running' | 'done' | 'failed' | 'canceled';
export type TaskType = 'transcription';

export interface ConnectorConfig {
    type: 'faster_whisper'; // other engines in future
    model_size?: string;
    device?: string;
    compute_type?: string;
}

export interface RefineConfig {
    enabled: boolean;
    model?: string; // e.g. "gpt-4o" or "local"
}

export interface TaskConfigSnapshot {
    engine: ConnectorConfig;
    refine: RefineConfig;
}

export interface TaskInput {
    media: string; // Path relative to workspace or absolute
    script?: string | null;
}

export interface TaskOutput {
    raw_srt?: string | null;
    refined_srt?: string | null;
    refined_txt?: string | null;
    log?: string | null;
}

export interface TaskError {
    message: string;
    trace?: string;
}

export interface Task {
    task_id: string;
    run_id: string;
    created_at: string; // ISO string
    status: TaskStatus;
    type: TaskType;
    requested_by: string;
    tool: string;
    
    config_snapshot: TaskConfigSnapshot;
    input: TaskInput;
    pipeline: string[];
    output: TaskOutput;
    
    error?: TaskError | null;
}

export interface AppEvent {
    ts: string;
    run_id: string;
    task_id: string;
    type: string;
    payload: any;
    agent?: string;
}

// Log Interface for UI display
export interface LogEntry {
  message: string;
  type: "info" | "error" | "success";
  timestamp: string;
}
