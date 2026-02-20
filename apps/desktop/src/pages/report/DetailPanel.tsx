import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";

import type {
    ApplePlanResponse,
    BitmapCandidateRow,
    BitmapSummaryResponse,
    BitmapTimelineEvent,
    CanopyDataResponse,
    CanopyEventRow,
    ModuleOverview,
    QuestionRow,
    SystemInventoryRow,
    WorkNode,
    SpecDocSummary,
    SpecReadResponse,
    TodoItem,
    HandoffSummaryResponse,
} from "./types";

type SyncHistoryItem = { at: string; text: string; tone: "info" | "ok" | "warn" | "error" };
type BitmapEventHighlight = { eventType: string; candidateId: string };

type DetailPanelProps = {
    moduleOverview: ModuleOverview[];
    systemInventory: SystemInventoryRow[];
    moduleWorkNodes: WorkNode[];
    allWorkNodes: WorkNode[];
    selectedModuleId: string;
    selectedModuleMeta: ModuleOverview | null;
    selectedWork: WorkNode | null;
    selectedQuestion: QuestionRow | null;
    questionQueue: QuestionRow[];
    bitmapSummary: BitmapSummaryResponse | null;
    selectedBitmapCandidateId: string;
    selectedBitmapCandidate: BitmapCandidateRow | null;
    selectedBitmapTimeline: BitmapTimelineEvent[];
    bitmapTimelineLoading: boolean;
    bitmapActionBusyId: string;
    workActionBusyId: string;
    bitmapEventHighlight: BitmapEventHighlight | null;
    onCreateWorkFromQuestion: () => Promise<void>;
    onCreateWorkFromCluster: (clusterId?: string) => Promise<void>;
    onAcknowledgeWork: (workId?: string) => Promise<void>;
    onCompleteWork: (workId?: string) => Promise<void>;
    onSelectWorkNode: (workId: string) => void;
    onSelectModuleNode: (moduleId: string) => void;
    onSelectQuestionNode: (clusterId: string) => void;
    onSelectBitmapCandidate: (candidateId: string) => void;
    onAdoptBitmapCandidate: (candidateId: string, episodeId: string) => Promise<void>;
    onRejectBitmapCandidate: (candidateId: string, episodeId: string, reason?: string) => Promise<void>;
    moduleBottlenecks: WorkNode[];
    roadmap: CanopyDataResponse["roadmap"] | null;
    progressSync: CanopyDataResponse["progress_sync"] | null;
    recentEvents: CanopyEventRow[];
    topologyNodes: Array<Record<string, unknown>>;
    topologyEdges: Array<Record<string, unknown>>;
    focus: CanopyDataResponse["focus"] | null;
    roadmapJournal: CanopyDataResponse["roadmap_journal"] | null;
    parallelWorkboard: CanopyDataResponse["parallel_workboard"] | null;
    specIndex: SpecDocSummary[];
    selectedSpecPath: string;
    selectedSpecContent: SpecReadResponse | null;
    specLoading: boolean;
    specUploadBusy: boolean;
    specReviewBusy: boolean;
    onSelectSpecPath: (path: string) => void;
    onRequestSpecReview: (path?: string) => Promise<void>;
    onSetSpecStatus: (path: string, status: "pending" | "review" | "confirmed", note?: string) => Promise<void>;
    onUploadSpecByFile: (event: ChangeEvent<HTMLInputElement>) => Promise<void>;
    todoItems: TodoItem[];
    todoBusy: boolean;
    onUpsertTodo: (payload: {
        id?: string;
        title: string;
        detail?: string;
        priority_weight?: number;
        category?: string;
        lane?: string;
        spec_ref?: string;
        status?: "todo" | "doing" | "done";
    }) => Promise<void>;
    onSetTodoStatus: (itemId: string, status: "todo" | "doing" | "done", checked?: boolean) => Promise<void>;
    rootMode: boolean;
    mindWorkstream: {
        learning_events?: Record<string, number>;
        chat_kinds?: Record<string, number>;
        note_context_messages?: number;
        recent_chat_scanned?: number;
        updated_at?: string;
    } | null;
    handoffSummary: HandoffSummaryResponse | null;
    applePlan: ApplePlanResponse | null;
    applePlanBusy: boolean;
    onSyncApplePlan: () => Promise<void>;
    humanView: CanopyDataResponse["human_view"] | null;
    overviewUnlocked: boolean;
    selectedPhaseStepFilter: string;
    onClearPhaseStepFilter: () => void;
    onSelectPhaseStep: (phaseStep: string) => void;
    snapshotDiff: {
        recordedAt: string;
        statusChanges: Array<{ status: string; delta: number }>;
        maxRiskDelta: number;
        highlights: string[];
        changed: boolean;
    } | null;
    syncDigestLine: string;
    syncHistory: SyncHistoryItem[];
    lastRoadmapRecordSummary: string;
    recordedOnlyHint: string;
    recordedOnlyHiddenSamples: string[];
};

type GridRow = {
    id: string;
    category: string;
    feature: string;
    status: string;
    progress: number;
    risk: string;
    updatedAt: string;
    kind: "focus" | "work" | "question" | "module" | "system" | "roadmap" | "placeholder";
    workId?: string;
    moduleId?: string;
    clusterId?: string;
    systemId?: string;
};

type ImmediateAction = {
    id: string;
    title: string;
    status: string;
    reason: string;
    workId?: string;
    moduleId?: string;
    clusterId?: string;
};

function normStatus(value: string): string {
    const s = String(value || "").trim().toUpperCase();
    return s || "READY";
}

function statusLabel(status: string): string {
    const s = normStatus(status);
    if (s === "IN_PROGRESS") return "ACTIVE";
    if (s === "DONE") return "DONE";
    if (s === "BLOCKED" || s === "FAILED") return "BLOCKED";
    if (s === "READY") return "READY";
    if (s === "PENDING" || s === "READY_TO_ASK") return "PENDING";
    if (s === "RESOLVED" || s === "ACKNOWLEDGED") return "DONE";
    return s;
}

function statusTone(status: string): string {
    const s = normStatus(status);
    if (s === "DONE" || s === "RESOLVED") return "border-emerald-400/50 bg-emerald-900/20 text-emerald-100";
    if (s === "BLOCKED" || s === "FAILED") return "border-rose-400/50 bg-rose-900/20 text-rose-100";
    if (s === "IN_PROGRESS") return "border-amber-400/50 bg-amber-900/20 text-amber-100";
    if (s === "PENDING" || s === "READY_TO_ASK") return "border-cyan-400/50 bg-cyan-900/20 text-cyan-100";
    return "border-[#334155] bg-[#0b1220] text-gray-300";
}

function progressFromStatus(status: string): number {
    const s = normStatus(status);
    if (s === "DONE" || s === "RESOLVED") return 100;
    if (s === "IN_PROGRESS") return 60;
    if (s === "BLOCKED" || s === "FAILED") return 35;
    if (s === "PENDING" || s === "READY_TO_ASK") return 45;
    return 20;
}

function progressBarTone(progress: number, status: string): string {
    const s = normStatus(status);
    if (s === "DONE") return "bg-emerald-400";
    if (s === "BLOCKED" || s === "FAILED") return "bg-rose-400";
    if (progress >= 60) return "bg-amber-400";
    return "bg-cyan-400";
}

function shortText(value: string, max = 88): string {
    const normalized = String(value || "").replace(/\s+/g, " ").trim();
    if (!normalized) return "-";
    if (normalized.length <= max) return normalized;
    return `${normalized.slice(0, Math.max(1, max - 1))}…`;
}

function formatWhen(value: string): string {
    const raw = String(value || "").trim();
    if (!raw) return "-";
    const dt = new Date(raw);
    if (Number.isNaN(dt.getTime())) return raw;
    return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")} ${String(dt.getHours()).padStart(2, "0")}:${String(dt.getMinutes()).padStart(2, "0")}`;
}

function numericOrDash(value: number | null | undefined, digits = 2): string {
    if (value === null || value === undefined || Number.isNaN(value)) return "-";
    return Number(value).toFixed(digits);
}

function roadmapCategoryToStatus(category: string): string {
    const normalized = String(category || "").toUpperCase();
    if (normalized === "SYSTEM_CHANGE") return "IN_PROGRESS";
    if (normalized === "FEATURE_ADD") return "READY";
    if (normalized === "PROBLEM_FIX") return "BLOCKED";
    return "DONE";
}

function statusPriority(status: string): number {
    const normalized = normStatus(status);
    if (normalized === "IN_PROGRESS") return 0;
    if (normalized === "BLOCKED" || normalized === "FAILED") return 1;
    if (normalized === "READY" || normalized === "PENDING" || normalized === "READY_TO_ASK") return 2;
    if (normalized === "DONE" || normalized === "RESOLVED") return 3;
    return 4;
}

function nodeKindFromId(nodeId: string): "module" | "work" | "question" | "other" {
    const id = String(nodeId || "").trim();
    if (id.startsWith("module:")) return "module";
    if (id.startsWith("work:")) return "work";
    if (id.startsWith("question:")) return "question";
    return "other";
}

function nodeDisplayLabel(rawLabel: string): string {
    const normalized = String(rawLabel || "").replace(/\s+/g, " ").trim();
    if (!normalized) return "-";
    const line = normalized.split("[")[0].trim();
    return shortText(line || normalized, 46);
}

export function DetailPanel(props: DetailPanelProps) {
    const [selectedRowId, setSelectedRowId] = useState<string>("");
    const [rejectReason, setRejectReason] = useState<string>("");
    const [detailMenu, setDetailMenu] = useState<"status" | "plan" | "spec" | "parallel">("status");
    const [todoTitle, setTodoTitle] = useState("");
    const [todoDetail, setTodoDetail] = useState("");
    const [todoPriority, setTodoPriority] = useState(70);
    const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({});

    const overallCompletion = useMemo(() => {
        const total = Number(props.roadmap?.total_work || 0);
        const remaining = Number(props.roadmap?.remaining_work || 0);
        if (total <= 0) return Math.max(0, Math.min(100, Number(props.selectedModuleMeta?.progress_pct || 0)));
        const done = Math.max(0, total - remaining);
        return Math.max(0, Math.min(100, Math.round((done / total) * 100)));
    }, [props.roadmap?.remaining_work, props.roadmap?.total_work, props.selectedModuleMeta?.progress_pct]);

    const currentMission = props.focus?.current_mission || null;
    const currentFocusTitle = currentMission?.title || "현재 미션 없음";
    const currentFocusStatus = currentMission?.status || (props.focus?.current_mission_id ? "IN_PROGRESS" : "READY");
    const currentFocusProgress = progressFromStatus(currentFocusStatus);
    const selectionSource = useMemo(() => {
        if (props.selectedWork) {
            return {
                kind: "작업",
                title: shortText(String(props.selectedWork.title || props.selectedWork.label || props.selectedWork.id), 64),
                note: "좌측 작업 선택 기준으로 상세를 표시합니다.",
                tone: "border-amber-400/40 bg-amber-900/15 text-amber-100",
            };
        }
        if (props.selectedQuestion) {
            return {
                kind: "질문",
                title: shortText(String(props.selectedQuestion.description || props.selectedQuestion.cluster_id), 64),
                note: "좌측 질문 선택 기준으로 상세를 표시합니다.",
                tone: "border-cyan-400/40 bg-cyan-900/15 text-cyan-100",
            };
        }
        if (props.selectedModuleMeta) {
            return {
                kind: "모듈",
                title: shortText(String(props.selectedModuleMeta.label || props.selectedModuleMeta.module), 64),
                note: "좌측 모듈 선택 기준으로 상세를 표시합니다.",
                tone: "border-violet-400/40 bg-violet-900/15 text-violet-100",
            };
        }
        return {
            kind: "기본",
            title: "프로젝트 전체",
            note: "현재 프로젝트 전체 범위를 기준으로 표시합니다.",
            tone: "border-[#334155] bg-[#0b1220] text-gray-300",
        };
    }, [props.selectedWork, props.selectedQuestion, props.selectedModuleMeta]);

    const rootDocGroups = useMemo(() => {
        const groups: Record<string, SpecDocSummary[]> = {
            constitution: [],
            plan: [],
            spec: [],
            guide: [],
            other: [],
        };
        for (const row of props.specIndex) {
            const key = String(row.doc_type || "other").toLowerCase();
            if (key in groups) groups[key].push(row);
            else groups.other.push(row);
        }
        return groups;
    }, [props.specIndex]);

    const rootDocStatusSummary = useMemo(() => {
        const summary = { pending: 0, review: 0, confirmed: 0, unknown: 0 };
        for (const row of props.specIndex) {
            const key = String(row.status || "unknown").toLowerCase();
            if (key === "pending") summary.pending += 1;
            else if (key === "review") summary.review += 1;
            else if (key === "confirmed") summary.confirmed += 1;
            else summary.unknown += 1;
        }
        return summary;
    }, [props.specIndex]);

    const todoStatusSummary = useMemo(() => {
        const summary = { todo: 0, doing: 0, done: 0 };
        for (const row of props.todoItems) {
            const key = String(row.status || "").toLowerCase();
            if (key === "doing") summary.doing += 1;
            else if (key === "done") summary.done += 1;
            else summary.todo += 1;
        }
        return summary;
    }, [props.todoItems]);

    const gridRows = useMemo<GridRow[]>(() => {
        const rows: GridRow[] = [];
        const phaseFilter = String(props.selectedPhaseStepFilter || "").trim();

        rows.push({
            id: "focus:current",
            category: "CURRENT FOCUS",
            feature: shortText(currentFocusTitle, 96),
            status: currentFocusStatus,
            progress: currentFocusProgress,
            risk: props.selectedQuestion ? numericOrDash(Number(props.selectedQuestion.risk_score || 0), 2) : "-",
            updatedAt: formatWhen(currentMission?.updated_at || ""),
            kind: "focus",
            workId: currentMission?.id,
            moduleId: String(currentMission?.module || "").trim() || undefined,
        });

        if (phaseFilter) {
            const phaseRows = (props.roadmapJournal?.entries || [])
                .filter((entry) => String(entry.phase_step || "").trim() === phaseFilter)
                .slice(0, 10)
                .map((entry) => {
                    const status = roadmapCategoryToStatus(entry.category);
                    return {
                        id: `roadmap:${entry.id}`,
                        category: `PHASE ${phaseFilter}`,
                        feature: shortText(String(entry.title || entry.summary || "-"), 96),
                        status,
                        progress: progressFromStatus(status),
                        risk: "-",
                        updatedAt: formatWhen(String(entry.recorded_at || entry.timestamp || "")),
                        kind: "roadmap" as const,
                    };
                });
            if (phaseRows.length > 0) {
                return [...rows, ...phaseRows];
            }
            return [
                ...rows,
                {
                    id: `phase-empty:${phaseFilter}`,
                    category: `PHASE ${phaseFilter}`,
                    feature: "해당 phase_step 기록이 아직 없습니다.",
                    status: "READY",
                    progress: 0,
                    risk: "-",
                    updatedAt: "-",
                    kind: "placeholder",
                },
            ];
        }

        if ((props.systemInventory || []).length > 0) {
            const systemRows = props.systemInventory
                .map((system) => ({
                    id: `system:${system.id}`,
                    category: shortText(system.category || "SYSTEM", 28),
                    feature: shortText(system.feature || system.id, 96),
                    status: system.status || "READY",
                    progress: Math.max(0, Math.min(100, Number(system.progress_pct || 0))),
                    risk: numericOrDash(Number(system.risk_score || 0), 2),
                    updatedAt: formatWhen(String(system.updated_at || "")),
                    kind: "system" as const,
                    systemId: system.id,
                }))
                .sort((left, right) => {
                    const l = statusPriority(left.status);
                    const r = statusPriority(right.status);
                    if (l !== r) return l - r;
                    const lRisk = Number.parseFloat(String(left.risk || "0")) || 0;
                    const rRisk = Number.parseFloat(String(right.risk || "0")) || 0;
                    if (rRisk !== lRisk) return rRisk - lRisk;
                    return right.progress - left.progress;
                });
            rows.push(...systemRows);
        } else {
            const missionId = String(currentMission?.id || "").trim();
            const workRows = props.moduleWorkNodes
                .map((work) => ({
                    id: `work:${work.id}`,
                    category: String(work.kind || "WORK"),
                    feature: shortText(work.title || work.label || work.id, 96),
                    status: work.status,
                    progress: progressFromStatus(work.status),
                    risk: numericOrDash(Number(work.linked_risk || 0), 2),
                    updatedAt: formatWhen(String(work.updated_at || "")),
                    kind: "work" as const,
                    workId: work.id,
                    moduleId: String(work.module || "").trim() || undefined,
                }))
                .sort((left, right) => {
                    const leftMission = missionId.length > 0 && left.workId === missionId ? 0 : 1;
                    const rightMission = missionId.length > 0 && right.workId === missionId ? 0 : 1;
                    if (leftMission !== rightMission) return leftMission - rightMission;
                    const l = statusPriority(left.status);
                    const r = statusPriority(right.status);
                    if (l !== r) return l - r;
                    const lRisk = Number.parseFloat(String(left.risk || "0")) || 0;
                    const rRisk = Number.parseFloat(String(right.risk || "0")) || 0;
                    if (rRisk !== lRisk) return rRisk - lRisk;
                    return right.progress - left.progress;
                });
            rows.push(...workRows);
        }

        if (props.selectedQuestion) {
            rows.push({
                id: `question:${props.selectedQuestion.cluster_id}`,
                category: "QUESTION",
                feature: shortText(props.selectedQuestion.description || props.selectedQuestion.cluster_id, 96),
                status: props.selectedQuestion.status,
                progress: progressFromStatus(props.selectedQuestion.status),
                risk: numericOrDash(Number(props.selectedQuestion.risk_score || 0), 2),
                updatedAt: formatWhen(String(props.selectedQuestion.updated_at || "")),
                kind: "question",
                clusterId: props.selectedQuestion.cluster_id,
            });
        }

        if (rows.length === 1 && props.selectedModuleMeta) {
            rows.push({
                id: `module:${props.selectedModuleMeta.module}`,
                category: "MODULE",
                feature: shortText(props.selectedModuleMeta.label, 96),
                status: Number(props.selectedModuleMeta.progress_pct || 0) >= 95 ? "DONE" : "IN_PROGRESS",
                progress: Math.max(0, Math.min(100, Number(props.selectedModuleMeta.progress_pct || 0))),
                risk: numericOrDash(Number(props.selectedModuleMeta.max_risk_score || 0), 2),
                updatedAt: "-",
                kind: "module",
                moduleId: props.selectedModuleMeta.module,
            });
        }

        return rows;
    }, [
        currentFocusProgress,
        currentFocusStatus,
        currentFocusTitle,
        currentMission?.id,
        currentMission?.updated_at,
        props.moduleWorkNodes,
        props.roadmapJournal?.entries,
        props.selectedPhaseStepFilter,
        props.selectedModuleMeta,
        props.selectedQuestion,
        props.systemInventory,
    ]);

    const selectedRow =
        gridRows.find((row) => row.id === selectedRowId) ||
        (props.selectedWork ? gridRows.find((row) => row.workId === props.selectedWork?.id) : null) ||
        gridRows[0] ||
        null;

    useEffect(() => {
        if (gridRows.length === 0) {
            if (selectedRowId) setSelectedRowId("");
            return;
        }
        if (selectedRowId && !gridRows.some((row) => row.id === selectedRowId)) {
            setSelectedRowId(gridRows[0].id);
        }
    }, [gridRows, selectedRowId]);

    useEffect(() => {
        const workId = String(props.selectedWork?.id || "").trim();
        if (!workId) return;
        const target = `work:${workId}`;
        if (gridRows.some((row) => row.id === target) && selectedRowId !== target) {
            setSelectedRowId(target);
        }
    }, [props.selectedWork?.id, gridRows, selectedRowId]);

    useEffect(() => {
        if (props.selectedWork?.id) return;
        const clusterId = String(props.selectedQuestion?.cluster_id || "").trim();
        if (!clusterId) return;
        const target = `question:${clusterId}`;
        if (gridRows.some((row) => row.id === target) && selectedRowId !== target) {
            setSelectedRowId(target);
        }
    }, [props.selectedQuestion?.cluster_id, props.selectedWork?.id, gridRows, selectedRowId]);

    useEffect(() => {
        if (props.selectedWork?.id || props.selectedQuestion?.cluster_id) return;
        const moduleId = String(props.selectedModuleId || "").trim();
        if (!moduleId) return;
        const target = `module:${moduleId}`;
        if (gridRows.some((row) => row.id === target) && selectedRowId !== target) {
            setSelectedRowId(target);
        }
    }, [props.selectedModuleId, props.selectedWork?.id, props.selectedQuestion?.cluster_id, gridRows, selectedRowId]);

    useEffect(() => {
        const targetId = String(selectedRow?.id || "").trim();
        if (!targetId) return;
        const rowEl = rowRefs.current[targetId];
        if (!rowEl) return;
        rowEl.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
    }, [selectedRow?.id]);

    const selectedSystem = useMemo(
        () => (selectedRow?.systemId ? props.systemInventory.find((row) => row.id === selectedRow.systemId) || null : null),
        [props.systemInventory, selectedRow?.systemId],
    );

    const pendingCount = Number(props.bitmapSummary?.lifecycle?.pending_count || 0);
    const adoptionRate = Number(props.bitmapSummary?.lifecycle?.adoption_rate || 0);
    const statusCounts = props.bitmapSummary?.lifecycle?.candidate_status_counts || {};
    const pendingCandidates = (props.bitmapSummary?.candidates || []).filter(
        (row) => String(row.status || "").toUpperCase() === "PENDING",
    );
    const effectiveCandidate =
        props.selectedBitmapCandidate ||
        pendingCandidates.find((row) => row.id === props.selectedBitmapCandidateId) ||
        pendingCandidates[0] ||
        null;
    const bitmapBusy = Boolean(effectiveCandidate && props.bitmapActionBusyId === effectiveCandidate.id);

    const phasePlan = useMemo(() => {
        const entries = props.roadmapJournal?.entries || [];
        const phaseFilter = String(props.selectedPhaseStepFilter || "").trim();
        const ready: string[] = [];
        const progress: string[] = [];
        const done: string[] = [];

        entries.slice(0, 40).forEach((entry) => {
            if (phaseFilter) {
                const step = String(entry.phase_step || "").trim();
                if (step !== phaseFilter) return;
            }
            const title = shortText(String(entry.title || entry.summary || ""), 72);
            if (!title || title === "-") return;
            const category = String(entry.category || "").toUpperCase();
            if (category === "FEATURE_ADD") {
                ready.push(title);
            } else if (category === "SYSTEM_CHANGE") {
                progress.push(title);
            } else {
                done.push(title);
            }
        });

        if (!phaseFilter && ready.length === 0 && props.progressSync?.next_actions?.length) {
            props.progressSync.next_actions.slice(0, 3).forEach((row) => ready.push(shortText(row.title, 72)));
        }

        return {
            ready: ready.slice(0, 5),
            progress: progress.slice(0, 5),
            done: done.slice(0, 5),
        };
    }, [props.progressSync?.next_actions, props.roadmapJournal?.entries, props.selectedPhaseStepFilter]);
    const phaseStepOptions = useMemo(() => {
        const entries = props.roadmapJournal?.entries || [];
        const bucket = new Map<string, number>();
        for (const entry of entries) {
            const step = String(entry.phase_step || "").trim();
            if (!step) continue;
            bucket.set(step, (bucket.get(step) || 0) + 1);
        }
        return Array.from(bucket.entries())
            .map(([step, count]) => ({ step, count }))
            .sort((a, b) => {
                const pa = a.step.split(".").map((n) => Number(n));
                const pb = b.step.split(".").map((n) => Number(n));
                for (let i = 0; i < Math.max(pa.length, pb.length); i += 1) {
                    const da = Number.isFinite(pa[i]) ? pa[i] : 0;
                    const db = Number.isFinite(pb[i]) ? pb[i] : 0;
                    if (da !== db) return db - da;
                }
                return 0;
            })
            .slice(0, 8);
    }, [props.roadmapJournal?.entries]);

    const parallelLanes = useMemo(() => {
        const rows = Array.isArray(props.parallelWorkboard?.lanes) ? props.parallelWorkboard?.lanes : [];
        return rows || [];
    }, [props.parallelWorkboard?.lanes]);

    const selectedSpecSummary = useMemo(
        () => props.specIndex.find((row) => row.path === props.selectedSpecPath) || null,
        [props.specIndex, props.selectedSpecPath],
    );

    const recentLogs = (props.recentEvents || []).slice(-8).reverse();
    const auditRows = useMemo(() => {
        const phaseFilter = String(props.selectedPhaseStepFilter || "").trim();
        if (!phaseFilter) {
            return recentLogs.map((event, idx) => ({
                key: `${event.timestamp || idx}-${event.event_type || ""}`,
                type: String(event.event_type || "EVENT"),
                text: shortText(String(event.summary || event.target || ""), 96),
                at: formatWhen(String(event.timestamp || "")),
            }));
        }
        const filtered = (props.roadmapJournal?.entries || [])
            .filter((entry) => String(entry.phase_step || "").trim() === phaseFilter)
            .slice(0, 8)
            .map((entry) => ({
                key: `phase-audit:${entry.id}`,
                type: String(entry.category || "ROADMAP"),
                text: shortText(String(entry.title || entry.summary || "-"), 96),
                at: formatWhen(String(entry.recorded_at || entry.timestamp || "")),
            }));
        return filtered;
    }, [props.selectedPhaseStepFilter, props.roadmapJournal?.entries, recentLogs]);

    const topologyNodeMap = useMemo(() => {
        const map = new Map<string, { id: string; label: string; kind: "module" | "work" | "question" | "other" }>();
        (props.topologyNodes || []).forEach((row) => {
            const id = String((row as { id?: unknown }).id || "").trim();
            if (!id) return;
            const label = nodeDisplayLabel(String((row as { label?: unknown }).label || id));
            map.set(id, { id, label, kind: nodeKindFromId(id) });
        });
        return map;
    }, [props.topologyNodes]);

    const topologyRelations = useMemo(() => {
        return (props.topologyEdges || [])
            .map((row, index) => {
                const from = String((row as { from?: unknown }).from || "").trim();
                const to = String((row as { to?: unknown }).to || "").trim();
                if (!from || !to) return null;
                return {
                    id: `${from}->${to}:${index}`,
                    from,
                    to,
                    fromNode: topologyNodeMap.get(from),
                    toNode: topologyNodeMap.get(to),
                };
            })
            .filter((row): row is NonNullable<typeof row> => Boolean(row))
            .slice(0, 16);
    }, [props.topologyEdges, topologyNodeMap]);

    const immediateActions = useMemo<ImmediateAction[]>(() => {
        const rows: ImmediateAction[] = [];
        const mission = props.focus?.current_mission;
        const missionId = String(mission?.id || "").trim();
        const missionModuleId = String(mission?.module || "").trim();
        const missionNext = shortText(String(props.focus?.next_action?.text || "").trim(), 92);
        if (missionId && missionNext !== "-") {
            rows.push({
                id: `mission:${missionId}`,
                title: missionNext,
                status: normStatus(String(mission?.status || "IN_PROGRESS")),
                reason: "현재 미션 기준",
                workId: missionId,
                moduleId: missionModuleId || undefined,
            });
        }
        const candidateWorks = [...props.allWorkNodes]
            .filter((row) => String(row.id || "").trim() !== missionId)
            .filter((row) => {
                const s = normStatus(String(row.status || ""));
                return s === "IN_PROGRESS" || s === "READY" || s === "BLOCKED" || s === "FAILED";
            })
            .sort((left, right) => {
                const ls = statusPriority(String(left.status || ""));
                const rs = statusPriority(String(right.status || ""));
                if (ls !== rs) return ls - rs;
                const lp = Number(left.priority_score || 0);
                const rp = Number(right.priority_score || 0);
                if (rp !== lp) return rp - lp;
                return Number(right.linked_risk || 0) - Number(left.linked_risk || 0);
            })
            .slice(0, 3);
        candidateWorks.forEach((row) => {
            const status = normStatus(String(row.status || ""));
            const reason =
                status === "BLOCKED" || status === "FAILED"
                    ? "문제 해결 우선"
                    : status === "IN_PROGRESS"
                      ? "진행중 작업"
                      : "다음 실행 후보";
            rows.push({
                id: `work:${row.id}`,
                title: shortText(String(row.title || row.label || row.id), 92),
                status,
                reason,
                workId: String(row.id || "").trim() || undefined,
                moduleId: String(row.module || "").trim() || undefined,
            });
        });
        if (rows.length < 3) {
            const questionCandidates = [...props.questionQueue]
                .filter((row) => {
                    const s = normStatus(String(row.status || ""));
                    return s === "READY_TO_ASK" || s === "PENDING" || s === "COLLECTING";
                })
                .sort((left, right) => {
                    const ls = statusPriority(String(left.status || ""));
                    const rs = statusPriority(String(right.status || ""));
                    if (ls !== rs) return ls - rs;
                    return Number(right.risk_score || 0) - Number(left.risk_score || 0);
                })
                .slice(0, 3);
            questionCandidates.forEach((row) => {
                rows.push({
                    id: `question:${row.cluster_id}`,
                    title: shortText(String(row.description || row.cluster_id), 92),
                    status: normStatus(String(row.status || "PENDING")),
                    reason: "질문 정리 우선",
                    clusterId: String(row.cluster_id || "").trim() || undefined,
                });
            });
        }
        if (rows.length < 3) {
            const syncFallback = (props.progressSync?.next_actions || [])
                .slice(0, 5)
                .map((row, index) => ({
                    id: `sync-next:${index}:${String(row.title || "").trim()}`,
                    title: shortText(String(row.title || "다음 액션"), 92),
                    status: "READY",
                    reason: "sync 추천",
                }));
            syncFallback.forEach((row) => rows.push(row));
        }
        const unique = new Map<string, ImmediateAction>();
        rows.forEach((row) => {
            if (!unique.has(row.id)) unique.set(row.id, row);
        });
        return Array.from(unique.values()).slice(0, 3);
    }, [
        props.focus?.current_mission,
        props.focus?.next_action?.text,
        props.allWorkNodes,
        props.questionQueue,
        props.progressSync?.next_actions,
    ]);

    const latestDecision = useMemo(() => {
        const fromSync = props.syncHistory.find((row) =>
            /(ACK|완료 처리|작업 생성|실패|처리 중)/.test(String(row.text || "")),
        );
        if (fromSync) {
            return {
                text: shortText(fromSync.text, 140),
                at: fromSync.at,
                tone: fromSync.tone,
                source: "sync",
            } as const;
        }
        const fromHuman = (props.humanView?.summary_cards || []).find((row) => row.key === "decision");
        if (fromHuman?.text) {
            return {
                text: shortText(fromHuman.text, 140),
                at: "",
                tone: "info" as const,
                source: "human",
            };
        }
        return null;
    }, [props.humanView?.summary_cards, props.syncHistory]);

    const handoffChecklist = useMemo(() => {
        const rows = props.handoffSummary?.checklist || [];
        if (rows.length > 0) return rows.slice(0, 4);
        return [
            "1) 루트(소피아)에서 문서 상태부터 확인",
            "2) review/pending 문서 SonE 검토 후 상태 정리",
            "3) TODO 우선순위 높은 항목 1개를 doing으로 전환",
            "4) 구현 후 status/sync로 현황 갱신",
        ];
    }, [props.handoffSummary?.checklist]);

    const handoffNextTodos = useMemo(() => {
        return (props.handoffSummary?.todo?.next || []).slice(0, 3);
    }, [props.handoffSummary?.todo?.next]);

    const appleCheckSummary = useMemo(() => {
        const checks = Array.isArray(props.applePlan?.checks) ? props.applePlan?.checks : [];
        const done = checks.filter((row) => String(row.state || "").toLowerCase() === "done").length;
        const inProgress = checks.filter((row) => String(row.state || "").toLowerCase() === "in_progress").length;
        const pending = checks.filter((row) => String(row.state || "").toLowerCase() === "pending").length;
        const blocked = checks.filter((row) => String(row.state || "").toLowerCase() === "blocked").length;
        return {
            done,
            inProgress,
            pending,
            blocked,
            total: checks.length,
        };
    }, [props.applePlan?.checks]);

    const applePlanRows = useMemo(() => {
        const rows = Array.isArray(props.applePlan?.plan) ? props.applePlan?.plan : [];
        return [...rows].sort((left, right) => Number(right.priority_weight || 0) - Number(left.priority_weight || 0));
    }, [props.applePlan?.plan]);

    if (props.rootMode) {
        return (
            <div className="h-full min-h-0 overflow-auto p-3 space-y-3">
                <div className="rounded-lg border border-[#334155] bg-[#111827] p-4">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <p className="text-xs tracking-wide text-cyan-300 font-semibold">소피아 · 문서/계획 워크스페이스</p>
                            <p className="text-xl font-bold text-gray-100 mt-1">헌법 · 명세 · 로드맵 기준 작업</p>
                            <p className="text-sm text-gray-400 mt-1">
                                문서를 업로드하고 상태(대기/검토/확정)를 관리하며, SonE 검토와 TODO 우선순위를 기준으로 작업을 진행합니다.
                            </p>
                        </div>
                        <div className="text-right min-w-[180px]">
                            <p className="text-xs text-gray-400">문서 상태 요약</p>
                            <p className="text-sm text-gray-200 mt-1">
                                대기 {rootDocStatusSummary.pending} · 검토 {rootDocStatusSummary.review} · 확정 {rootDocStatusSummary.confirmed}
                            </p>
                            <p className="text-[11px] text-gray-500 mt-1">총 문서 {props.specIndex.length}</p>
                        </div>
                    </div>
                </div>

                <div className="rounded-lg border border-cyan-500/30 bg-cyan-950/20 p-3">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <p className="text-xs tracking-wide text-cyan-300 font-semibold">AI 인수인계 요약</p>
                            <p className="text-sm text-gray-200 mt-1">
                                현재 미션: {shortText(String(props.handoffSummary?.focus?.current_mission_title || "없음"), 90)}
                            </p>
                            <p className="text-xs text-gray-400 mt-1">
                                다음 액션: {shortText(String(props.handoffSummary?.focus?.next_action_text || "우선순위 TODO 선택"), 110)}
                            </p>
                        </div>
                        <div className="text-right min-w-[180px]">
                            <p className="text-xs text-gray-400">즉시 점검</p>
                            <p className="text-[11px] text-amber-200 mt-1">
                                문서 검토 필요 {Number(props.handoffSummary?.docs?.needs_review?.length || 0)}건
                            </p>
                            <p className="text-[11px] text-cyan-200 mt-0.5">
                                다음 TODO {Number(handoffNextTodos.length)}건
                            </p>
                        </div>
                    </div>
                    <div className="mt-2 space-y-2">
                        <div className="rounded border border-[#334155] bg-[#0b1220] p-2">
                            <p className="text-[11px] text-gray-400">시작 체크리스트</p>
                            <ul className="mt-1 space-y-1">
                                {handoffChecklist.map((row) => (
                                    <li key={`handoff-check-${row}`} className="text-[11px] text-gray-200">
                                        {shortText(row, 120)}
                                    </li>
                                ))}
                            </ul>
                        </div>
                        <div className="rounded border border-[#334155] bg-[#0b1220] p-2">
                            <p className="text-[11px] text-gray-400">다음 할 일 (Top 3)</p>
                            {handoffNextTodos.length === 0 ? (
                                <p className="mt-1 text-[11px] text-gray-500">진행 가능한 TODO가 없습니다.</p>
                            ) : (
                                <ul className="mt-1 space-y-1">
                                    {handoffNextTodos.map((row) => (
                                        <li key={`handoff-todo-${row.id}`} className="text-[11px] text-gray-200">
                                            {shortText(String(row.title || row.id), 88)}
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    </div>
                    <p className="mt-2 text-[11px] text-gray-500">
                        가이드: {shortText(String(props.handoffSummary?.sources?.agent_handoff || "/Users/dragonpd/Sophia/Docs/forest_agent_handoff.md"), 120)}
                    </p>
                </div>

                <div className="rounded-lg border border-amber-400/35 bg-amber-950/15 p-3">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <p className="text-xs tracking-wide text-amber-300 font-semibold">Apple Intelligence 상태/계획</p>
                            <p className="text-sm text-gray-200 mt-1">
                                단계: {shortText(String(props.applePlan?.current_stage || "unavailable"), 72)}
                            </p>
                            <p className="text-[11px] text-gray-400 mt-0.5">
                                Shortcuts: {String(props.applePlan?.runtime?.shortcuts_status || "UNVERIFIED")} · provider: {String(props.applePlan?.runtime?.ai_provider_default || "ollama")}
                            </p>
                            <p className="text-[11px] text-gray-500 mt-0.5">
                                TODO 동기화: {Number(props.applePlan?.todo_synced_count || 0)} / {Array.isArray(props.applePlan?.plan) ? props.applePlan?.plan.length : 0}
                            </p>
                        </div>
                        <div className="text-right min-w-[180px]">
                            <p className="text-xs text-gray-400">진행도</p>
                            <p className="text-2xl font-bold text-amber-200 mt-1">{Number(props.applePlan?.progress_pct || 0)}%</p>
                            <button
                                onClick={() => void props.onSyncApplePlan()}
                                disabled={props.applePlanBusy}
                                className="mt-2 rounded border border-amber-400/50 bg-amber-900/20 px-2 py-1 text-[11px] text-amber-100 hover:bg-amber-900/30 disabled:opacity-60"
                            >
                                {props.applePlanBusy ? "동기화 중..." : "Apple 계획 동기화"}
                            </button>
                        </div>
                    </div>
                    <div className="mt-2 grid grid-cols-4 gap-2 text-[11px]">
                        <div className="rounded border border-emerald-400/35 bg-emerald-900/10 px-2 py-1">
                            done {appleCheckSummary.done}
                        </div>
                        <div className="rounded border border-amber-400/35 bg-amber-900/10 px-2 py-1">
                            in_progress {appleCheckSummary.inProgress}
                        </div>
                        <div className="rounded border border-cyan-400/35 bg-cyan-900/10 px-2 py-1">
                            pending {appleCheckSummary.pending}
                        </div>
                        <div className="rounded border border-rose-400/35 bg-rose-900/10 px-2 py-1">
                            blocked {appleCheckSummary.blocked}
                        </div>
                    </div>
                    <div className="mt-2 space-y-1.5 max-h-[140px] overflow-auto pr-1">
                        {applePlanRows.length === 0 ? (
                            <p className="text-[11px] text-gray-500">등록된 Apple 구현계획이 없습니다.</p>
                        ) : (
                            applePlanRows.slice(0, 4).map((row) => (
                                <div key={`apple-plan-${row.id}`} className="rounded border border-[#334155] bg-[#0b1220] px-2 py-1.5">
                                    <div className="flex items-center justify-between gap-2">
                                        <p className="text-[11px] text-gray-100">{shortText(row.title, 92)}</p>
                                        <span className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] ${statusTone(row.status)}`}>
                                            {statusLabel(row.status)}
                                        </span>
                                    </div>
                                    <p className="mt-0.5 text-[10px] text-gray-500">
                                        W{Number(row.priority_weight || 0)} · lane {row.lane || "codex"} · {row.synced ? "synced" : "unsynced"}
                                    </p>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                <div className="space-y-3">
                        <div className="rounded-lg border border-[#334155] bg-[#0f172a] p-3">
                            <div className="flex items-center justify-between gap-2">
                                <p className="text-xs text-gray-400">문서 인덱스</p>
                            <label className="rounded border border-cyan-400/50 bg-cyan-900/20 px-2 py-1 text-[11px] text-cyan-100 cursor-pointer hover:bg-cyan-900/35">
                                {props.specUploadBusy ? "업로드 중..." : "문서 업로드"}
                                <input
                                    type="file"
                                    accept=".md,.markdown,.txt"
                                    className="hidden"
                                    onChange={(event) => void props.onUploadSpecByFile(event)}
                                    disabled={props.specUploadBusy}
                                />
                            </label>
                        </div>
                        <div className="mt-2 space-y-2 max-h-[260px] overflow-auto pr-1">
                            {Object.entries(rootDocGroups).map(([docType, rows]) => (
                                <div key={`root-doc-group-${docType}`} className="rounded border border-[#334155] bg-[#111827] p-2">
                                    <p className="text-[11px] uppercase tracking-wide text-gray-400">
                                        {docType} ({rows.length})
                                    </p>
                                    {rows.length === 0 ? (
                                        <p className="mt-1 text-[11px] text-gray-500">문서 없음</p>
                                    ) : (
                                        <div className="mt-1.5 space-y-1.5">
                                            {rows.map((row) => {
                                                const active = row.path === props.selectedSpecPath;
                                                const status = String(row.status || "unknown").toLowerCase();
                                                const statusTone =
                                                    status === "confirmed"
                                                        ? "border-emerald-400/50 bg-emerald-900/20 text-emerald-100"
                                                        : status === "review"
                                                          ? "border-amber-400/50 bg-amber-900/20 text-amber-100"
                                                          : status === "pending"
                                                            ? "border-cyan-400/50 bg-cyan-900/20 text-cyan-100"
                                                            : "border-[#334155] bg-[#0b1220] text-gray-300";
                                                return (
                                                    <div
                                                        key={row.path}
                                                        className={`rounded border px-2 py-1.5 ${
                                                            active
                                                                ? "border-violet-400 bg-violet-900/20"
                                                                : "border-[#334155] bg-[#0b1220]"
                                                        }`}
                                                    >
                                                        <button
                                                            onClick={() => props.onSelectSpecPath(row.path)}
                                                            className="w-full text-left"
                                                        >
                                                            <p className="text-xs text-gray-100">{shortText(row.title, 80)}</p>
                                                            <p className="text-[11px] text-gray-500 mt-0.5">{row.path}</p>
                                                        </button>
                                                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                                                            <span className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] ${statusTone}`}>
                                                                {status === "confirmed" ? "확정" : status === "review" ? "검토" : status === "pending" ? "대기" : "미분류"}
                                                            </span>
                                                            <button
                                                                onClick={() => void props.onSetSpecStatus(row.path, "pending")}
                                                                className="rounded border border-cyan-400/40 bg-cyan-900/20 px-1.5 py-0.5 text-[10px] text-cyan-100 hover:bg-cyan-900/35"
                                                            >
                                                                대기
                                                            </button>
                                                            <button
                                                                onClick={() => void props.onSetSpecStatus(row.path, "review")}
                                                                className="rounded border border-amber-400/40 bg-amber-900/20 px-1.5 py-0.5 text-[10px] text-amber-100 hover:bg-amber-900/35"
                                                            >
                                                                검토
                                                            </button>
                                                            <button
                                                                onClick={() => void props.onSetSpecStatus(row.path, "confirmed")}
                                                                className="rounded border border-emerald-400/40 bg-emerald-900/20 px-1.5 py-0.5 text-[10px] text-emerald-100 hover:bg-emerald-900/35"
                                                            >
                                                                확정
                                                            </button>
                                                            <button
                                                                onClick={() => void props.onRequestSpecReview(row.path)}
                                                                disabled={props.specReviewBusy}
                                                                className="rounded border border-violet-400/40 bg-violet-900/20 px-1.5 py-0.5 text-[10px] text-violet-100 hover:bg-violet-900/35 disabled:opacity-60"
                                                            >
                                                                {props.specReviewBusy ? "검토중..." : "SonE 검토"}
                                                            </button>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="space-y-3">
                        <div className="rounded-lg border border-[#334155] bg-[#0f172a] p-3">
                            <p className="text-xs text-gray-400">선택 문서 내용 (읽기 전용)</p>
                            <p className="text-sm text-gray-100 font-semibold mt-1">
                                {selectedSpecSummary?.title || props.selectedSpecContent?.title || "선택된 문서 없음"}
                            </p>
                            <div className="mt-2 rounded border border-[#334155] bg-[#0b1220] p-2 max-h-[420px] overflow-auto">
                                {props.specLoading ? (
                                    <p className="text-xs text-gray-500">문서 로딩 중...</p>
                                ) : props.selectedSpecContent?.content ? (
                                    <pre className="text-xs text-gray-200 whitespace-pre-wrap break-words font-mono">
                                        {props.selectedSpecContent.content}
                                    </pre>
                                ) : (
                                    <p className="text-xs text-gray-500">문서를 선택하면 내용이 표시됩니다.</p>
                                )}
                            </div>
                        </div>

                        <div className="rounded-lg border border-[#334155] bg-[#0f172a] p-3">
                            <div className="flex items-center justify-between gap-2">
                                <p className="text-xs text-gray-400">우선순위 TODO</p>
                                <p className="text-[11px] text-gray-500">
                                    TODO {todoStatusSummary.todo} · 진행 {todoStatusSummary.doing} · 완료 {todoStatusSummary.done}
                                </p>
                            </div>
                            <div className="mt-2 grid grid-cols-[1fr_90px_auto] gap-2">
                                <input
                                    value={todoTitle}
                                    onChange={(event) => setTodoTitle(event.target.value)}
                                    placeholder="작업 제목"
                                    className="rounded border border-[#334155] bg-[#111827] px-2 py-1 text-xs text-gray-200"
                                />
                                <input
                                    type="number"
                                    min={0}
                                    max={100}
                                    value={todoPriority}
                                    onChange={(event) => setTodoPriority(Number(event.target.value || 0))}
                                    className="rounded border border-[#334155] bg-[#111827] px-2 py-1 text-xs text-gray-200"
                                />
                                <button
                                    onClick={() => {
                                        const title = todoTitle.trim();
                                        if (!title) return;
                                        void props.onUpsertTodo({
                                            title,
                                            detail: todoDetail.trim() || undefined,
                                            priority_weight: todoPriority,
                                            category: "implementation",
                                            lane: "codex",
                                            spec_ref: props.selectedSpecPath || undefined,
                                            status: "todo",
                                        });
                                        setTodoTitle("");
                                        setTodoDetail("");
                                        setTodoPriority(70);
                                    }}
                                    disabled={props.todoBusy}
                                    className="rounded border border-cyan-400/50 bg-cyan-900/20 px-2 py-1 text-xs text-cyan-100 hover:bg-cyan-900/35 disabled:opacity-60"
                                >
                                    추가
                                </button>
                            </div>
                            <input
                                value={todoDetail}
                                onChange={(event) => setTodoDetail(event.target.value)}
                                placeholder="상세(선택)"
                                className="mt-2 w-full rounded border border-[#334155] bg-[#111827] px-2 py-1 text-xs text-gray-200"
                            />
                            <div className="mt-2 space-y-1.5 max-h-[180px] overflow-auto pr-1">
                                {props.todoItems.length === 0 ? (
                                    <p className="text-xs text-gray-500">등록된 TODO가 없습니다.</p>
                                ) : (
                                    props.todoItems.map((row) => (
                                        <div key={row.id} className="rounded border border-[#334155] bg-[#111827] px-2 py-1.5">
                                            <div className="flex items-center justify-between gap-2">
                                                <p className="text-xs text-gray-100">{row.title}</p>
                                                <span className="text-[11px] text-gray-400">W{Number(row.priority_weight || 0)}</span>
                                            </div>
                                            {row.detail ? (
                                                <p className="mt-0.5 text-[11px] text-gray-400">{shortText(row.detail, 92)}</p>
                                            ) : null}
                                            <div className="mt-1.5 flex items-center gap-1.5">
                                                {(["todo", "doing", "done"] as const).map((state) => {
                                                    const active = String(row.status || "").toLowerCase() === state;
                                                    const tone =
                                                        state === "done"
                                                            ? "border-emerald-400/50 bg-emerald-900/20 text-emerald-100"
                                                            : state === "doing"
                                                              ? "border-amber-400/50 bg-amber-900/20 text-amber-100"
                                                              : "border-cyan-400/50 bg-cyan-900/20 text-cyan-100";
                                                    return (
                                                        <button
                                                            key={`${row.id}-${state}`}
                                                            onClick={() => void props.onSetTodoStatus(row.id, state, state === "done")}
                                                            disabled={props.todoBusy}
                                                            className={`rounded border px-1.5 py-0.5 text-[10px] ${tone} ${
                                                                active ? "ring-1 ring-white/20" : "opacity-80"
                                                            }`}
                                                        >
                                                            {state}
                                                        </button>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>

                        <div className="rounded-lg border border-[#334155] bg-[#0f172a] p-3">
                            <p className="text-xs text-gray-400">소피아 마음/작업 흐름 연동</p>
                            <div className="mt-2 space-y-2 text-[11px]">
                                <div className="rounded border border-[#334155] bg-[#111827] px-2 py-1">
                                    학습 이벤트 {Object.keys(props.mindWorkstream?.learning_events || {}).length}
                                </div>
                                <div className="rounded border border-[#334155] bg-[#111827] px-2 py-1">
                                    노트 컨텍스트 {Number(props.mindWorkstream?.note_context_messages || 0)}
                                </div>
                                <div className="rounded border border-[#334155] bg-[#111827] px-2 py-1">
                                    채팅 분류 {Object.keys(props.mindWorkstream?.chat_kinds || {}).length}
                                </div>
                                <div className="rounded border border-[#334155] bg-[#111827] px-2 py-1">
                                    최근 스캔 {Number(props.mindWorkstream?.recent_chat_scanned || 0)}
                                </div>
                            </div>
                            {props.humanView?.roadmap_now?.next_action ? (
                                <p className="mt-2 text-xs text-gray-300">
                                    다음 액션: {shortText(String(props.humanView.roadmap_now.next_action), 96)}
                                </p>
                            ) : null}
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="h-full min-h-0 overflow-auto p-3 space-y-3">
            <div className="rounded-lg border border-[#334155] bg-[#111827] p-4">
                <div className="flex items-center justify-between gap-3">
                    <div>
                        <p className="text-xs tracking-wide text-amber-300 font-semibold">CURRENT FOCUS (WIP LIMIT: 1)</p>
                        <p className="text-2xl font-bold text-gray-100 mt-1">{shortText(currentFocusTitle, 120)}</p>
                        <p className="text-sm text-gray-400 mt-1">{shortText(props.focus?.next_action?.text || "다음 액션 없음", 140)}</p>
                    </div>
                    <div className="text-right min-w-[140px]">
                        <p className="text-xs text-gray-400">프로젝트 진행</p>
                        <div className="mt-1 flex items-center justify-end gap-2">
                            <span className="text-2xl font-bold text-amber-300 leading-none">{overallCompletion}%</span>
                            <span className="text-[10px] text-gray-500">전체 기준</span>
                        </div>
                        <div className="mt-1 h-2 rounded bg-[#1f2a3d] overflow-hidden">
                            <div className="h-full bg-amber-400" style={{ width: `${overallCompletion}%` }} />
                        </div>
                    </div>
                </div>
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#0b1220] p-3">
                <div className="flex items-center justify-between gap-2">
                    <p className="text-xs text-gray-400">전후 변화(diff)</p>
                    <p className="text-[11px] text-gray-500">
                        {props.snapshotDiff?.recordedAt ? `기준 ${formatWhen(props.snapshotDiff.recordedAt)}` : "기준 스냅샷 없음"}
                    </p>
                </div>
                {!props.snapshotDiff ? (
                    <p className="mt-2 text-xs text-gray-500">첫 동기화 직후에는 비교 기준이 없어 diff를 표시하지 않습니다.</p>
                ) : props.snapshotDiff.changed ? (
                    <div className="mt-2 space-y-2">
                        <div className="flex flex-wrap gap-1.5">
                            {props.snapshotDiff.highlights.map((row) => (
                                <span
                                    key={`diff-highlight-${row}`}
                                    className="rounded border border-cyan-400/40 bg-cyan-900/20 px-2 py-0.5 text-[11px] text-cyan-100"
                                >
                                    {row}
                                </span>
                            ))}
                        </div>
                        <div className="grid grid-cols-2 gap-1.5 text-xs">
                            {props.snapshotDiff.statusChanges.slice(0, 6).map((row) => {
                                const positive = row.delta > 0;
                                const tone = positive
                                    ? "border-amber-400/40 bg-amber-900/20 text-amber-100"
                                    : "border-emerald-400/40 bg-emerald-900/20 text-emerald-100";
                                const sign = row.delta > 0 ? "+" : "";
                                return (
                                    <div key={`diff-${row.status}`} className={`rounded border px-2 py-1 ${tone}`}>
                                        <span className="font-semibold">{row.status}</span>
                                        <span className="ml-1">{sign}{row.delta}</span>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                ) : (
                    <p className="mt-2 text-xs text-emerald-200">최근 동기화 대비 상태 변화가 없습니다.</p>
                )}
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#0b1220] p-3">
                <div className="flex items-center justify-between gap-2">
                    <p className="text-xs text-gray-400">지금 바로 실행 (Top 3)</p>
                    <p className="text-[11px] text-gray-500">focus 기준 우선순위</p>
                </div>
                {immediateActions.length === 0 ? (
                    <p className="mt-2 text-xs text-gray-500">실행 후보가 없습니다.</p>
                ) : (
                    <div className="mt-2 space-y-1.5">
                        {immediateActions.map((row, index) => {
                            const normalized = normStatus(row.status);
                            const actionableWork =
                                Boolean(row.workId) &&
                                normalized !== "DONE" &&
                                normalized !== "RESOLVED";
                            const busy = actionableWork && row.workId === props.workActionBusyId;
                            return (
                                <div
                                    key={row.id}
                                    className="w-full rounded border border-[#334155] bg-[#111827] px-2 py-1.5"
                                >
                                    <button
                                        onClick={() => {
                                            if (row.moduleId) props.onSelectModuleNode(row.moduleId);
                                            if (row.workId) props.onSelectWorkNode(row.workId);
                                            if (row.clusterId) props.onSelectQuestionNode(row.clusterId);
                                        }}
                                        className="w-full text-left hover:bg-[#172033] rounded"
                                    >
                                        <div className="flex items-center justify-between gap-2">
                                            <p className="text-xs text-gray-200">
                                                {index + 1}. {row.title}
                                            </p>
                                            <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] ${statusTone(row.status)}`}>
                                                {statusLabel(row.status)}
                                            </span>
                                        </div>
                                        <p className="mt-0.5 text-[11px] text-gray-500">{row.reason}</p>
                                    </button>
                                    {actionableWork ? (
                                        <div className="mt-2 flex gap-2">
                                            <button
                                                onClick={() => {
                                                    if (row.moduleId) props.onSelectModuleNode(row.moduleId);
                                                    if (row.workId) props.onSelectWorkNode(row.workId);
                                                    void props.onAcknowledgeWork(row.workId);
                                                }}
                                                disabled={busy}
                                                className="rounded border border-amber-400/50 bg-amber-900/20 px-2 py-0.5 text-[11px] text-amber-100 hover:bg-amber-900/35 disabled:opacity-60"
                                            >
                                                {busy ? "처리중..." : "ACK"}
                                            </button>
                                            <button
                                                onClick={() => {
                                                    if (row.moduleId) props.onSelectModuleNode(row.moduleId);
                                                    if (row.workId) props.onSelectWorkNode(row.workId);
                                                    void props.onCompleteWork(row.workId);
                                                }}
                                                disabled={busy}
                                                className="rounded border border-emerald-400/50 bg-emerald-900/20 px-2 py-0.5 text-[11px] text-emerald-100 hover:bg-emerald-900/35 disabled:opacity-60"
                                            >
                                                {busy ? "처리중..." : "완료"}
                                            </button>
                                        </div>
                                    ) : row.clusterId ? (
                                        <div className="mt-2">
                                            <button
                                                onClick={() => {
                                                    if (row.clusterId) props.onSelectQuestionNode(row.clusterId);
                                                    void props.onCreateWorkFromCluster(row.clusterId);
                                                }}
                                                className="rounded border border-cyan-400/50 bg-cyan-900/20 px-2 py-0.5 text-[11px] text-cyan-100 hover:bg-cyan-900/35"
                                            >
                                                작업 생성
                                            </button>
                                        </div>
                                    ) : null}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {latestDecision ? (
                <div className="rounded-lg border border-[#334155] bg-[#0b1220] p-3">
                    <div className="flex items-center justify-between gap-2">
                        <p className="text-xs text-gray-400">최근 결정</p>
                        <span
                            className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] ${
                                latestDecision.tone === "ok"
                                    ? "border-emerald-400/50 bg-emerald-900/20 text-emerald-100"
                                    : latestDecision.tone === "warn"
                                      ? "border-amber-400/50 bg-amber-900/20 text-amber-100"
                                      : latestDecision.tone === "error"
                                        ? "border-rose-400/50 bg-rose-900/20 text-rose-100"
                                        : "border-cyan-400/50 bg-cyan-900/20 text-cyan-100"
                            }`}
                        >
                            {latestDecision.source === "sync" ? "실행 반영" : "포커스 제안"}
                        </span>
                    </div>
                    <p className="mt-2 text-sm text-gray-100">{latestDecision.text}</p>
                    {latestDecision.at ? <p className="mt-1 text-[11px] text-gray-500">{latestDecision.at}</p> : null}
                </div>
            ) : null}

            <div className="rounded-lg border border-[#334155] bg-[#0f172a] overflow-hidden">
                <div className={`px-4 py-2 border-b ${selectionSource.tone}`}>
                    <div className="flex items-center gap-2">
                        <span className="text-[10px] rounded border border-current/40 px-1.5 py-0.5">{selectionSource.kind}</span>
                        <p className="text-xs font-medium">{selectionSource.title}</p>
                    </div>
                    <p className="text-[11px] opacity-90 mt-1">{selectionSource.note}</p>
                </div>
                {props.selectedPhaseStepFilter ? (
                    <div className="px-4 py-2 border-b border-violet-400/25 bg-violet-950/20">
                        <p className="text-[11px] text-violet-100">
                            phase {props.selectedPhaseStepFilter} 필터 적용 중: 테이블을 해당 phase 기록 중심으로 표시합니다.
                        </p>
                    </div>
                ) : null}
                <div className="overflow-x-auto">
                    <div className="px-4 py-2 border-b border-[#1f2a3d] bg-[#0b1220]">
                        <p className="text-[11px] text-gray-400">
                            정렬 기준: 현재 미션 우선 → 진행중/문제 우선 → 리스크 높은 순
                        </p>
                    </div>
                    <table className="w-full text-left min-w-[860px]">
                        <thead className="bg-[#111827] text-xs text-gray-400 uppercase tracking-wide border-b border-[#1f2a3d]">
                            <tr>
                                <th className="px-4 py-3">Category & Feature</th>
                                <th className="px-4 py-3">Status</th>
                                <th className="px-4 py-3">Progress</th>
                                <th className="px-4 py-3">Risk</th>
                                <th className="px-4 py-3">Last Update</th>
                            </tr>
                        </thead>
                        <tbody>
                            {gridRows.map((row) => {
                                const selected = selectedRow?.id === row.id;
                                return (
                                    <tr
                                        key={row.id}
                                        ref={(el) => {
                                            rowRefs.current[row.id] = el;
                                        }}
                                        className={`border-b border-[#1f2a3d] cursor-pointer ${selected ? "bg-cyan-900/15" : "hover:bg-[#0b1220]"}`}
                                        onClick={() => {
                                            setSelectedRowId(row.id);
                                            if (row.kind === "work" && row.workId) {
                                                if (row.moduleId) props.onSelectModuleNode(row.moduleId);
                                                props.onSelectWorkNode(row.workId);
                                                return;
                                            }
                                            if (row.kind === "question" && row.clusterId) {
                                                props.onSelectQuestionNode(row.clusterId);
                                                return;
                                            }
                                            if (row.kind === "module" && row.moduleId) {
                                                props.onSelectModuleNode(row.moduleId);
                                            }
                                        }}
                                    >
                                        <td className="px-4 py-3">
                                            <p className="text-[11px] uppercase tracking-wide text-cyan-300">{row.category}</p>
                                            <p className="text-sm text-gray-100 font-medium mt-1">{row.feature}</p>
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-semibold ${statusTone(row.status)}`}>
                                                {statusLabel(row.status)}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3">
                                            <div className="flex items-center gap-3">
                                                <div className="h-2 w-28 rounded bg-[#1f2a3d] overflow-hidden">
                                                    <div
                                                        className={`h-full ${progressBarTone(row.progress, row.status)}`}
                                                        style={{ width: `${Math.max(0, Math.min(100, row.progress))}%` }}
                                                    />
                                                </div>
                                                <span className="text-sm text-gray-300 w-10">{row.progress}%</span>
                                            </div>
                                        </td>
                                        <td className="px-4 py-3 text-sm text-amber-200">{row.risk}</td>
                                        <td className="px-4 py-3 text-sm text-gray-400">{row.updatedAt}</td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#0b1220] p-3">
                <div className="flex items-center justify-between gap-2">
                    <p className="text-xs text-gray-400">상호작용 그래프(최소)</p>
                    <p className="text-[11px] text-gray-500">
                        노드 {topologyNodeMap.size} · 연결 {topologyRelations.length}
                    </p>
                </div>
                {topologyRelations.length === 0 ? (
                    <p className="mt-2 text-xs text-gray-500">표시할 연결 관계가 없습니다.</p>
                ) : (
                    <div className="mt-2 space-y-1.5 max-h-40 overflow-auto pr-1">
                        {topologyRelations.map((edge) => {
                            const toKind = edge.toNode?.kind || "other";
                            const tone =
                                toKind === "work"
                                    ? "border-amber-400/35 bg-amber-900/15 text-amber-100"
                                    : toKind === "question"
                                      ? "border-cyan-400/35 bg-cyan-900/15 text-cyan-100"
                                      : toKind === "module"
                                        ? "border-violet-400/35 bg-violet-900/15 text-violet-100"
                                        : "border-[#334155] bg-[#111827] text-gray-300";
                            return (
                                <button
                                    key={edge.id}
                                    onClick={() => {
                                        const targetKind = edge.toNode?.kind || "other";
                                        const targetId = String(edge.to || "");
                                        if (targetKind === "work" && targetId.startsWith("work:")) {
                                            const workId = targetId.slice("work:".length);
                                            props.onSelectWorkNode(workId);
                                            return;
                                        }
                                        if (targetKind === "question" && targetId.startsWith("question:")) {
                                            const clusterId = targetId.slice("question:".length);
                                            props.onSelectQuestionNode(clusterId);
                                            return;
                                        }
                                        if (targetKind === "module" && targetId.startsWith("module:")) {
                                            const moduleId = targetId.slice("module:".length);
                                            props.onSelectModuleNode(moduleId);
                                        }
                                    }}
                                    className={`w-full rounded border px-2 py-1.5 text-left hover:bg-[#172033] ${tone}`}
                                >
                                    <div className="flex items-center gap-2 text-xs">
                                        <span className="text-[10px] uppercase tracking-wide">{edge.fromNode?.kind || "node"}</span>
                                        <span className="text-gray-400">→</span>
                                        <span className="text-[10px] uppercase tracking-wide">{edge.toNode?.kind || "node"}</span>
                                    </div>
                                    <div className="mt-0.5 text-xs text-gray-100">
                                        {edge.fromNode?.label || edge.from}
                                        <span className="text-gray-500"> → </span>
                                        {edge.toNode?.label || edge.to}
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                )}
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#0b1220] p-3">
                <div className="mb-3 flex items-center justify-between gap-2">
                    <p className="text-xs text-gray-400">상세 메뉴</p>
                    <div className="flex items-center gap-1.5">
                        <button
                            onClick={() => setDetailMenu("status")}
                            className={`rounded border px-2 py-1 text-[11px] ${
                                detailMenu === "status"
                                    ? "border-cyan-400 bg-cyan-900/25 text-cyan-100"
                                    : "border-[#334155] bg-[#111827] text-gray-300"
                            }`}
                        >
                            현황
                        </button>
                        <button
                            onClick={() => setDetailMenu("plan")}
                            className={`rounded border px-2 py-1 text-[11px] ${
                                detailMenu === "plan"
                                    ? "border-amber-400 bg-amber-900/25 text-amber-100"
                                    : "border-[#334155] bg-[#111827] text-gray-300"
                            }`}
                        >
                            계획서
                        </button>
                        <button
                            onClick={() => setDetailMenu("spec")}
                            className={`rounded border px-2 py-1 text-[11px] ${
                                detailMenu === "spec"
                                    ? "border-violet-400 bg-violet-900/25 text-violet-100"
                                    : "border-[#334155] bg-[#111827] text-gray-300"
                            }`}
                        >
                            명세서
                        </button>
                        <button
                            onClick={() => setDetailMenu("parallel")}
                            className={`rounded border px-2 py-1 text-[11px] ${
                                detailMenu === "parallel"
                                    ? "border-emerald-400 bg-emerald-900/25 text-emerald-100"
                                    : "border-[#334155] bg-[#111827] text-gray-300"
                            }`}
                        >
                            병렬작업
                        </button>
                    </div>
                </div>

                {detailMenu === "status" ? (
                    <div className="grid grid-cols-3 gap-3">
                        <div className="rounded-lg border border-[#334155] bg-[#0b1220] p-3">
                            <p className="text-xs text-gray-400 mb-2">선택 항목 상세</p>
                            <p className="text-sm font-semibold text-gray-100">{selectedRow?.feature || "-"}</p>
                            <div className="mt-2 space-y-1 text-xs text-gray-300">
                                <p>상태: <span className="text-gray-100">{selectedRow ? statusLabel(selectedRow.status) : "-"}</span></p>
                                <p>리스크: <span className="text-gray-100">{selectedRow?.risk || "-"}</span></p>
                                <p>우선순위: <span className="text-gray-100">{props.selectedWork?.priority_score ? `P${Math.max(0, Math.round((100 - Number(props.selectedWork.priority_score)) / 20))}` : "-"}</span></p>
                                <p>다음 액션: <span className="text-gray-100">{shortText(props.focus?.next_action?.text || "없음", 72)}</span></p>
                                {selectedSystem?.description ? (
                                    <p>
                                        설명: <span className="text-gray-100">{shortText(selectedSystem.description, 72)}</span>
                                    </p>
                                ) : null}
                            </div>
                            {props.selectedQuestion ? (
                                <button
                                    onClick={() => void props.onCreateWorkFromQuestion()}
                                    className="mt-3 w-full rounded border border-cyan-400/50 bg-cyan-900/20 px-2 py-1 text-xs text-cyan-100 hover:bg-cyan-900/35"
                                >
                                    질문 기반 작업 생성
                                </button>
                            ) : null}
                        </div>

                        <div className="rounded-lg border border-[#334155] bg-[#0b1220] p-3">
                            <p className="text-xs text-gray-400 mb-2">
                                {props.selectedPhaseStepFilter ? `Audit Trail (phase ${props.selectedPhaseStepFilter})` : "Audit Trail"}
                            </p>
                            <div className="space-y-1.5 max-h-40 overflow-auto pr-1">
                                {auditRows.length === 0 ? (
                                    <p className="text-xs text-gray-500">최근 로그 없음</p>
                                ) : (
                                    auditRows.map((row) => (
                                        <div key={row.key} className="rounded border border-[#253247] bg-[#0f172a] px-2 py-1.5">
                                            <div className="flex items-center justify-between gap-2">
                                                <p className="text-[11px] text-cyan-300">{row.type}</p>
                                                <p className="text-[10px] text-gray-500">{row.at}</p>
                                            </div>
                                            <p className="text-xs text-gray-300 mt-0.5">{row.text}</p>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>

                        <div className="rounded-lg border border-[#334155] bg-[#0b1220] p-3">
                            <p className="text-xs text-gray-400 mb-2">Bitmap Action</p>
                            <div className="text-xs text-gray-300 space-y-1">
                                <p>PENDING: <span className="text-gray-100">{pendingCount}</span></p>
                                <p>ADOPTED: <span className="text-gray-100">{Number(statusCounts.ADOPTED || 0)}</span></p>
                                <p>REJECTED: <span className="text-gray-100">{Number(statusCounts.REJECTED || 0)}</span></p>
                                <p>채택률: <span className="text-gray-100">{Math.round(adoptionRate * 100)}%</span></p>
                            </div>
                            {effectiveCandidate ? (
                                <div className="mt-3 space-y-2">
                                    <select
                                        value={props.selectedBitmapCandidateId || effectiveCandidate.id}
                                        onChange={(event) => props.onSelectBitmapCandidate(event.target.value)}
                                        className="w-full rounded border border-[#334155] bg-[#111827] px-2 py-1 text-xs text-gray-200"
                                    >
                                        {pendingCandidates.map((row) => (
                                            <option key={row.id} value={row.id}>
                                                {shortText(row.note || row.id, 64)}
                                            </option>
                                        ))}
                                    </select>
                                    <div className="flex gap-2">
                                        <button
                                            onClick={() =>
                                                void props.onAdoptBitmapCandidate(
                                                    effectiveCandidate.id,
                                                    String(effectiveCandidate.episode_id || ""),
                                                )
                                            }
                                            disabled={bitmapBusy}
                                            className="flex-1 rounded border border-emerald-400/50 bg-emerald-900/20 px-2 py-1 text-xs text-emerald-100 disabled:opacity-60"
                                        >
                                            {bitmapBusy ? "처리중..." : "Adopt"}
                                        </button>
                                        <button
                                            onClick={() =>
                                                void props.onRejectBitmapCandidate(
                                                    effectiveCandidate.id,
                                                    String(effectiveCandidate.episode_id || ""),
                                                    rejectReason.trim() || undefined,
                                                )
                                            }
                                            disabled={bitmapBusy}
                                            className="flex-1 rounded border border-rose-400/50 bg-rose-900/20 px-2 py-1 text-xs text-rose-100 disabled:opacity-60"
                                        >
                                            {bitmapBusy ? "처리중..." : "Reject"}
                                        </button>
                                    </div>
                                    <input
                                        value={rejectReason}
                                        onChange={(event) => setRejectReason(event.target.value)}
                                        placeholder="reject 사유(선택)"
                                        className="w-full rounded border border-[#334155] bg-[#111827] px-2 py-1 text-xs text-gray-200"
                                    />
                                </div>
                            ) : (
                                <p className="text-xs text-gray-500 mt-2">처리할 pending 후보가 없습니다.</p>
                            )}
                        </div>
                    </div>
                ) : null}

                {detailMenu === "plan" ? (
                    <div>
                        {phaseStepOptions.length > 0 ? (
                            <div className="mb-2 flex flex-wrap gap-1.5">
                                {phaseStepOptions.map((row) => {
                                    const active = row.step === props.selectedPhaseStepFilter;
                                    return (
                                        <button
                                            key={`phase-opt-${row.step}`}
                                            onClick={() =>
                                                props.onSelectPhaseStep(active ? "" : row.step)
                                            }
                                            className={`rounded border px-1.5 py-0.5 text-[10px] ${
                                                active
                                                    ? "border-violet-300 bg-violet-800/35 text-violet-50"
                                                    : "border-[#334155] bg-[#111827] text-gray-300 hover:bg-[#1a2335]"
                                            }`}
                                            title={`phase ${row.step} (${row.count}건)`}
                                        >
                                            {row.step} · {row.count}
                                        </button>
                                    );
                                })}
                            </div>
                        ) : null}
                        {props.selectedPhaseStepFilter ? (
                            <div className="mb-2 flex items-center justify-between gap-2">
                                <p className="text-[11px] text-violet-200">
                                    phase 필터 적용: {props.selectedPhaseStepFilter}
                                </p>
                                <button
                                    onClick={props.onClearPhaseStepFilter}
                                    className="rounded border border-violet-400/50 bg-violet-900/20 px-1.5 py-0.5 text-[10px] text-violet-100 hover:bg-violet-900/35"
                                >
                                    필터 해제
                                </button>
                            </div>
                        ) : null}
                        <div className="grid grid-cols-3 gap-3">
                            <div className="rounded border border-cyan-400/35 bg-cyan-900/10 p-2">
                                <p className="text-xs text-cyan-200 font-semibold">계획(READY)</p>
                                <ul className="mt-2 space-y-1 text-xs text-gray-300">
                                    {(phasePlan.ready.length ? phasePlan.ready : ["없음"]).map((row) => (
                                        <li key={`ready-${row}`}>· {row}</li>
                                    ))}
                                </ul>
                            </div>
                            <div className="rounded border border-amber-400/35 bg-amber-900/10 p-2">
                                <p className="text-xs text-amber-200 font-semibold">구현중(IN_PROGRESS)</p>
                                <ul className="mt-2 space-y-1 text-xs text-gray-300">
                                    {(phasePlan.progress.length ? phasePlan.progress : ["없음"]).map((row) => (
                                        <li key={`progress-${row}`}>· {row}</li>
                                    ))}
                                </ul>
                            </div>
                            <div className="rounded border border-emerald-400/35 bg-emerald-900/10 p-2">
                                <p className="text-xs text-emerald-200 font-semibold">완료(DONE)</p>
                                <ul className="mt-2 space-y-1 text-xs text-gray-300">
                                    {(phasePlan.done.length ? phasePlan.done : ["없음"]).map((row) => (
                                        <li key={`done-${row}`}>· {row}</li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    </div>
                ) : null}

                {detailMenu === "spec" ? (
                    <div className="space-y-3">
                        <div className="rounded border border-[#334155] bg-[#0f172a] p-2 max-h-[360px] overflow-auto">
                            <p className="text-xs text-gray-400 mb-2">명세/계획 문서</p>
                            {props.specIndex.length === 0 ? (
                                <p className="text-xs text-gray-500">연결된 명세 문서가 없습니다.</p>
                            ) : (
                                <div className="space-y-1.5">
                                    {props.specIndex.map((row) => {
                                        const active = row.path === props.selectedSpecPath;
                                        return (
                                            <button
                                                key={row.path}
                                                onClick={() => props.onSelectSpecPath(row.path)}
                                                className={`w-full rounded border px-2 py-1.5 text-left ${
                                                    active
                                                        ? "border-violet-400 bg-violet-900/20 text-violet-100"
                                                        : "border-[#334155] bg-[#111827] text-gray-200 hover:bg-[#1a2335]"
                                                }`}
                                            >
                                                <p className="text-[11px] uppercase tracking-wide text-gray-400">{row.doc_type}</p>
                                                <p className="text-xs mt-0.5">{shortText(row.title, 60)}</p>
                                                <p className="text-[11px] text-gray-500 mt-0.5">연결 {row.linked_records} · 상태 {row.status}</p>
                                            </button>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                        <div className="rounded border border-[#334155] bg-[#0f172a] p-3">
                            <div className="flex items-center justify-between gap-2">
                                <div>
                                    <p className="text-xs text-gray-400">문서 상세</p>
                                    <p className="text-sm text-gray-100 font-semibold mt-1">
                                        {selectedSpecSummary?.title || props.selectedSpecContent?.title || "선택된 문서 없음"}
                                    </p>
                                    <p className="text-[11px] text-gray-500 mt-0.5">
                                        {selectedSpecSummary?.path || props.selectedSpecPath || "-"}
                                    </p>
                                </div>
                                <button
                                    onClick={() => void props.onRequestSpecReview(props.selectedSpecPath)}
                                    disabled={!props.selectedSpecPath || props.specReviewBusy}
                                    className="rounded border border-cyan-400/50 bg-cyan-900/20 px-2 py-1 text-xs text-cyan-100 disabled:opacity-60"
                                >
                                    {props.specReviewBusy ? "기록중..." : "검토 요청 기록"}
                                </button>
                            </div>
                            <div className="mt-2 grid grid-cols-4 gap-2 text-xs">
                                <div className="rounded border border-cyan-400/35 bg-cyan-900/10 px-2 py-1">
                                    READY {selectedSpecSummary?.progress.ready ?? 0}
                                </div>
                                <div className="rounded border border-amber-400/35 bg-amber-900/10 px-2 py-1">
                                    IN_PROGRESS {selectedSpecSummary?.progress.in_progress ?? 0}
                                </div>
                                <div className="rounded border border-emerald-400/35 bg-emerald-900/10 px-2 py-1">
                                    DONE {selectedSpecSummary?.progress.done ?? 0}
                                </div>
                                <div className="rounded border border-rose-400/35 bg-rose-900/10 px-2 py-1">
                                    BLOCKED {selectedSpecSummary?.progress.blocked ?? 0}
                                </div>
                            </div>
                            <div className="mt-3 rounded border border-[#334155] bg-[#0b1220] p-2 max-h-[260px] overflow-auto">
                                {props.specLoading ? (
                                    <p className="text-xs text-gray-500">문서 로딩 중...</p>
                                ) : props.selectedSpecContent?.content ? (
                                    <pre className="text-xs text-gray-200 whitespace-pre-wrap break-words font-mono">
                                        {props.selectedSpecContent.content}
                                    </pre>
                                ) : (
                                    <p className="text-xs text-gray-500">표시할 문서 내용이 없습니다.</p>
                                )}
                            </div>
                        </div>
                    </div>
                ) : null}

                {detailMenu === "parallel" ? (
                    <div className="space-y-3">
                        <div className="text-xs text-gray-400">
                            병렬 작업 lane 요약 · 미할당 {props.parallelWorkboard?.unassigned_count || 0}
                        </div>
                        {parallelLanes.length === 0 ? (
                            <p className="text-xs text-gray-500">병렬 작업 기록이 없습니다. roadmap 기록 시 owner/lane 태그를 추가하세요.</p>
                        ) : (
                            <div className="grid grid-cols-2 gap-3">
                                {parallelLanes.map((lane) => (
                                    <div key={`lane-${lane.owner}`} className="rounded border border-[#334155] bg-[#0f172a] p-2">
                                        <div className="flex items-center justify-between gap-2">
                                            <p className="text-xs text-cyan-200 font-semibold">{lane.label || lane.owner}</p>
                                            <p className="text-[11px] text-gray-400">
                                                A:{lane.active} · R:{lane.ready} · B:{lane.blocked} · D:{lane.done}
                                            </p>
                                        </div>
                                        <div className="mt-2 space-y-1.5 max-h-[180px] overflow-auto pr-1">
                                            {(lane.items || []).map((item) => (
                                                <div key={`${lane.owner}:${item.id}`} className="rounded border border-[#334155] bg-[#111827] px-2 py-1.5">
                                                    <div className="flex items-center justify-between gap-2">
                                                        <p className="text-xs text-gray-100">{shortText(item.title || "-", 56)}</p>
                                                        <span className={`inline-flex items-center rounded border px-1 py-0.5 text-[10px] ${statusTone(item.status)}`}>
                                                            {statusLabel(item.status)}
                                                        </span>
                                                    </div>
                                                    <p className="mt-0.5 text-[11px] text-gray-500">
                                                        scope:{item.scope || "project"} · phase:{item.phase_step || "-"} · review:{item.review_state || "unknown"}
                                                    </p>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                ) : null}

                {!props.overviewUnlocked ? (
                    <p className="text-[11px] text-amber-200/80 mt-3">
                        Focus 모드 기준 요약입니다. 더 많은 기록은 상단에서 Overview를 열어 확인할 수 있습니다.
                    </p>
                ) : null}
            </div>
        </div>
    );
}
