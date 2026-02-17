export type AnalyzeMode = "idle" | "running" | "success" | "error";
export type ModuleSort = "importance" | "progress" | "risk";
export type EventFilter = "all" | "analysis" | "work" | "canopy" | "question";

export type ModuleOverview = {
    module: string;
    label: string;
    progress_pct: number;
    importance: number;
    work_total: number;
    pending_questions: number;
    max_risk_score: number;
};

export type WorkNode = {
    id: string;
    type: "work";
    label: string;
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
};

export type CanopyDataResponse = {
    status: "ok";
    project: string;
    generated_at: string;
    status_summary: Record<string, number>;
    risk: {
        threshold: number;
        max_risk_score: number;
        unverified_count: number;
        clusters: Array<Record<string, unknown>>;
    };
    module_overview: ModuleOverview[];
    roadmap: RoadmapSummary;
    sone_summary: {
        source_doc?: string;
        generated_at?: string;
        missing_slot_count?: number;
        impact_count?: number;
        risk_cluster_count?: number;
        max_risk_score?: number;
    };
    question_queue: QuestionRow[];
    recent_events: Array<Record<string, unknown>>;
    nodes: Array<Record<string, unknown>>;
    filters: {
        module_sort: ModuleSort;
        event_filter: EventFilter;
        module?: "all" | "chat" | "note" | "editor" | "subtitle" | "forest";
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
