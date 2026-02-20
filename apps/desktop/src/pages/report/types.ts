export type AnalyzeMode = "idle" | "running" | "success" | "error";
export type ModuleSort = "importance" | "progress" | "risk";
export type EventFilter = "all" | "analysis" | "work" | "canopy" | "question" | "bitmap";
export type ForestModule = "all" | "chat" | "note" | "editor" | "subtitle" | "forest" | "core";

export type ForestProjectInfo = {
    project_name: string;
    progress_pct: number;
    remaining_work: number;
    blocked_count: number;
    unverified_count: number;
    updated_at: string;
    current_phase?: string;
    current_phase_step?: string;
    roadmap_last_recorded_at?: string;
    archived?: boolean;
    archived_at?: string;
};

export type ModuleOverview = {
    module: string;
    label: string;
    dev_progress_pct: number;
    progress_pct: number;
    importance: number;
    work_total: number;
    ready?: number;
    in_progress?: number;
    done?: number;
    blocked?: number;
    failed?: number;
    pending_questions: number;
    max_risk_score: number;
};

export type WorkNode = {
    id: string;
    type: "work";
    label: string;
    title?: string;
    status: string;
    module?: string;
    module_label?: string;
    kind?: string;
    priority_score?: number;
    linked_risk?: number;
    context_tag?: string;
    linked_node?: string;
    updated_at?: string;
};

export type QuestionRow = {
    cluster_id: string;
    description: string;
    status: string;
    risk_score: number;
    hit_count: number;
    linked_nodes: string[];
    updated_at?: string;
};

export type RoadmapSummary = {
    total_work: number;
    remaining_work: number;
    done_last_7d: number;
    eta_days: number | null;
    eta_hint: string;
    in_progress?: WorkNode[];
    pending?: WorkNode[];
    done_recent?: WorkNode[];
    in_progress_count?: number;
    blocked_count?: number;
};

export type ProgressSyncSummary = {
    status: "synced" | "unsynced";
    project?: string;
    synced_at?: string;
    hint?: string;
    summary?: {
        work_total?: number;
        remaining_work?: number;
        done_last_7d?: number;
        eta_days?: number | null;
        eta_hint?: string;
    };
    next_actions?: Array<{
        priority: string;
        title: string;
        reason: string;
        source: string;
    }>;
    work?: {
        done_recent?: Array<{ id: string }>;
        in_progress?: Array<{ id: string }>;
        pending?: Array<{ id: string }>;
    };
};

export type SyncStatusSummary = {
    state: "ok" | "warning" | "blocked" | "unknown" | string;
    label: string;
    step: string;
    route_type: "sync-router" | "status-sync" | "roadmap-sync" | "unknown" | string;
    last_event_type: string;
    last_at: string;
    message: string;
    recorded: number;
    skipped: number;
    mismatch_count: number;
};

export type CanopyFocusState = {
    focus_mode: boolean;
    current_mission_id: string | null;
    current_mission?: WorkNode | null;
    next_action?: {
        text: string;
        type: string;
        ref?: string;
    } | null;
    focus_lock?: {
        level: "soft" | "hard" | string;
        reason?: string;
        wip_limit?: number;
    };
    frozen_ideas?: {
        count: number;
        top: Array<{
            id: string;
            title: string;
            tag: string;
            created_at: string;
        }>;
    };
    journey?: {
        last_footprint: string;
        next_step: string;
        streak_days?: number | null;
    };
    metrics?: {
        wip_active_count: number;
        reentry_minutes?: number | null;
    };
    human_summary?: {
        now_problem: string;
        now_building: string;
        next_decision: string;
    };
};

export type CanopyEventRow = {
    timestamp?: string;
    event_type?: string;
    target?: string;
    summary?: string;
    level?: "info" | "warning" | "error" | string;
    payload?: Record<string, unknown>;
};

export type TopologyNode = {
    id: string;
    type: "module" | "work" | "question" | string;
    label: string;
    status?: string;
};

export type TopologyEdge = {
    from: string;
    to: string;
};

export type SystemInventoryRow = {
    id: string;
    category: string;
    feature: string;
    module: string;
    status: string;
    progress_pct: number;
    risk_score: number;
    updated_at: string;
    description?: string;
    files?: string[];
    existing_files?: string[];
    missing_files?: string[];
};

export type BitmapCandidateRow = {
    id: string;
    episode_id: string;
    note: string;
    confidence: number;
    proposed_at: string;
    status: string;
};

export type BitmapAnchorRow = {
    id: string;
    bits: number;
    role: string;
    adopted_at: string;
};

export type BitmapInvalidRow = {
    stage: string;
    reason: string;
    bits: string;
    at: string;
};

export type BitmapLifecycleSummary = {
    window_days: number;
    candidate_status_counts: Record<string, number>;
    event_counts: Record<string, number>;
    invalid_reason_counts: Record<string, number>;
    adoption_rate: number;
    pending_count: number;
    recent_transitions: Array<{
        event_type: string;
        at: string;
        candidate_id?: string;
        reason?: string;
    }>;
};

export type BitmapSummaryResponse = {
    status: "ok";
    candidates: BitmapCandidateRow[];
    anchors: BitmapAnchorRow[];
    invalid_recent: BitmapInvalidRow[];
    metrics: Record<string, number | Record<string, number>>;
    lifecycle: BitmapLifecycleSummary;
};

export type BitmapAuditTransition = {
    candidate_id: string;
    episode_id?: string;
    transition_count: number;
    last_event_type: string;
    last_at: string;
    current_status: string;
};

export type BitmapAuditReason = {
    reason: string;
    count: number;
};

export type BitmapAuditResponse = {
    status: "ok";
    window_days: number;
    totals: {
        candidate_total: number;
        status_counts: Record<string, number>;
        event_counts: Record<string, number>;
    };
    candidate_transitions: BitmapAuditTransition[];
    top_failure_reasons: BitmapAuditReason[];
    recent_failures: Array<{
        event_type: string;
        candidate_id?: string;
        episode_id?: string;
        reason: string;
        at: string;
    }>;
};

export type BitmapTimelineEvent = {
    event_id: string;
    event_type: string;
    at: string;
    episode_id?: string;
    candidate_id?: string;
    summary: string;
    payload?: Record<string, unknown>;
};

export type BitmapCandidateTimelineResponse = {
    status: "ok";
    candidate: {
        id: string;
        episode_id: string;
        note: string;
        confidence: number;
        proposed_at: string;
        status_value: string;
    };
    events: BitmapTimelineEvent[];
};

export type CanopyDataResponse = {
    status: "ok";
    project: string;
    view?: "focus" | "overview" | string;
    generated_at: string;
    status_summary: Record<string, number>;
    risk: {
        threshold: number;
        max_risk_score: number;
        unverified_count: number;
        clusters: Array<Record<string, unknown>>;
    };
    module_overview: ModuleOverview[];
    system_inventory?: SystemInventoryRow[];
    roadmap: RoadmapSummary;
    progress_sync?: ProgressSyncSummary;
    sync_status?: SyncStatusSummary;
    focus?: CanopyFocusState;
    focus_mode?: boolean;
    current_mission_id?: string | null;
    next_action?: {
        text: string;
        type: string;
        ref?: string;
    } | null;
    focus_lock?: {
        level: "soft" | "hard" | string;
        reason?: string;
        wip_limit?: number;
    };
    frozen_ideas?: {
        count: number;
        top: Array<{
            id: string;
            title: string;
            tag: string;
            created_at: string;
        }>;
    };
    journey?: {
        last_footprint: string;
        next_step: string;
        streak_days?: number | null;
    };
    metrics?: {
        wip_active_count: number;
        reentry_minutes?: number | null;
    };
    human_view?: {
        summary_cards?: Array<{
            key: string;
            title: string;
            text: string;
            severity: string;
        }>;
        quick_lists?: {
            pending_top?: Array<{ id: string; title: string; status: string }>;
            risk_top?: Array<{ cluster_id: string; risk_score: number }>;
            recent_top?: Array<{ event_type: string; summary: string }>;
            recorded_top?: Array<{
                id: string;
                title: string;
                summary: string;
                category: "SYSTEM_CHANGE" | "PROBLEM_FIX" | "FEATURE_ADD" | string;
                recorded_at: string;
            }>;
        };
        roadmap_now?: {
            remaining_work: number;
            high_risk_count: number;
            current_mission_id: string | null;
            next_action: string;
            phase?: string;
            phase_step?: string;
        };
    };
    roadmap_journal?: {
        path: string;
        total: number;
        entries: Array<{
            id: string;
            recorded_at: string;
            timestamp?: string;
            title: string;
            summary: string;
            category: "SYSTEM_CHANGE" | "PROBLEM_FIX" | "FEATURE_ADD" | string;
            type: string;
            category_reason?: string;
            source?: "manual" | "sync" | "system" | string;
            files?: string[];
            tags?: string[];
            phase?: string;
            phase_step?: string;
            phase_title?: string;
            owner?: string;
            lane?: string;
            scope?: "forest" | "project" | string;
            review_state?: "draft" | "review_requested" | "applied" | "unknown" | string;
            status?: "READY" | "IN_PROGRESS" | "DONE" | "BLOCKED" | string;
            spec_refs?: string[];
        }>;
        last_recorded_at: string;
        category_counts: Record<string, number>;
        phase_counts?: Record<string, number>;
        current_phase?: string;
        current_phase_step?: string;
    };
    parallel_workboard?: {
        lanes: Array<{
            owner: string;
            label: string;
            active: number;
            ready: number;
            blocked: number;
            done: number;
            items: Array<{
                id: string;
                title: string;
                summary: string;
                status: string;
                scope: "forest" | "project" | string;
                phase_step?: string;
                recorded_at?: string;
                review_state?: string;
            }>;
        }>;
        unassigned_count: number;
        updated_at: string;
    };
    mind_workstream?: {
        learning_events?: Record<string, number>;
        chat_kinds?: Record<string, number>;
        note_context_messages?: number;
        recent_chat_scanned?: number;
        updated_at?: string;
    };
    ai_view?: {
        contract: string;
        project: string;
        focus: Record<string, unknown>;
        module_overview: Array<Record<string, unknown>>;
        risk_clusters: Array<Record<string, unknown>>;
        progress_sync: Record<string, unknown>;
    };
    sone_summary: {
        source_doc?: string;
        generated_at?: string;
        validation_stage?: string;
        reason_catalog_version?: string;
        missing_slots?: Array<{
            target: string;
            status: string;
            evidence: string;
            reason_code?: string;
            reason_description?: string;
        }>;
        missing_slot_count?: number;
        impact_count?: number;
        risk_cluster_count?: number;
        max_risk_score?: number;
        risk_reasons?: Array<{
            cluster_id: string;
            description: string;
            risk_score: number;
            reason_code?: string;
            reason_description?: string;
            category?: string;
            evidence?: string;
        }>;
    };
    question_queue: QuestionRow[];
    recent_events: CanopyEventRow[];
    nodes: Array<Record<string, unknown>>;
    topology?: {
        nodes: TopologyNode[];
        edges: TopologyEdge[];
    };
    filters: {
        module_sort: ModuleSort;
        event_filter: EventFilter;
        module?: ForestModule;
        view?: "focus" | "overview" | string;
    };
    pagination?: {
        nodes?: {
            total: number;
            offset: number;
            limit: number;
            returned: number;
            has_more: boolean;
        };
        question_queue?: {
            total: number;
            offset: number;
            limit: number;
            returned: number;
            has_more: boolean;
        };
        recent_events?: {
            total: number;
            offset: number;
            limit: number;
            returned: number;
            has_more: boolean;
        };
    };
};

export type SpecDocSummary = {
    path: string;
    title: string;
    doc_type: "constitution" | "plan" | "spec" | "guide" | "other" | string;
    status: "pending" | "review" | "confirmed" | "unknown" | string;
    linked_records: number;
    reviewers: string[];
    progress: {
        ready: number;
        in_progress: number;
        done: number;
        blocked: number;
        total: number;
    };
    updated_at: string;
};

export type SpecIndexResponse = {
    status: "ok";
    project: string;
    total: number;
    items: SpecDocSummary[];
};

export type SpecReadResponse = {
    status: "ok";
    project: string;
    path: string;
    title: string;
    content: string;
    truncated: boolean;
};

export type TodoItem = {
    id: string;
    title: string;
    detail?: string;
    priority_weight: number;
    category?: string;
    lane?: string;
    spec_ref?: string;
    status: "todo" | "doing" | "done" | string;
    checked?: boolean;
    created_at?: string;
    updated_at?: string;
};

export type TodoListResponse = {
    status: "ok";
    project: string;
    total: number;
    items: TodoItem[];
};

export type HandoffSummaryResponse = {
    status: "ok";
    project: string;
    focus: {
        current_mission_id: string;
        current_mission_title: string;
        current_mission_status: string;
        next_action_text: string;
        next_action_type: string;
        next_action_ref: string;
    };
    docs: {
        total: number;
        pending: number;
        review: number;
        confirmed: number;
        needs_review: Array<{
            path: string;
            title: string;
            status: string;
            doc_type: string;
            linked_records: number;
            updated_at: string;
        }>;
    };
    todo: {
        total: number;
        todo: number;
        doing: number;
        done: number;
        next: TodoItem[];
    };
    checklist: string[];
    sources: {
        operator_workflow: string;
        agent_handoff: string;
    };
};

export type ApplePlanResponse = {
    status: "ok";
    project: string;
    runtime: {
        shortcuts_status: "UNVERIFIED" | "VERIFIED" | string;
        ai_provider_default: string;
        ai_mode: string;
        ai_foundation_bridge_url: string;
        ai_allow_external: boolean;
    };
    checks: Array<{
        id: string;
        title: string;
        state: "done" | "in_progress" | "pending" | "blocked" | string;
        detail: string;
    }>;
    progress_pct: number;
    current_stage: string;
    plan: Array<{
        id: string;
        title: string;
        priority_weight: number;
        status: "todo" | "doing" | "done" | string;
        detail: string;
        category: string;
        lane: string;
        synced?: boolean;
    }>;
    todo_synced_count?: number;
    todo_unsynced_count?: number;
    evidence: {
        docs: Array<{ path: string; exists: boolean }>;
        tests: Array<{ path: string; exists: boolean }>;
        code: Array<{ path: string; exists: boolean }>;
    };
};
