import { type ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { API_BASE, apiUrl } from "../../lib/apiBase";
import { noteService, type FileNode as NoteFileNode } from "../../lib/noteService";
import type {
    AnalyzeMode,
    BitmapAuditResponse,
    BitmapCandidateRow,
    BitmapCandidateTimelineResponse,
    BitmapSummaryResponse,
    BitmapTimelineEvent,
    CanopyDataResponse,
    EventFilter,
    ForestProjectInfo,
    ForestModule,
    ApplePlanResponse,
    ModuleOverview,
    ModuleSort,
    HandoffSummaryResponse,
    SpecDocSummary,
    SpecIndexResponse,
    SpecReadResponse,
    TodoItem,
    TodoListResponse,
    QuestionRow,
    WorkNode,
} from "./types";
import { inferModuleFromNode, parseErrorText } from "./utils";

type FocusKind = "module" | "work" | "question";
type OptimisticWorkStatusEntry = { status: string; expiresAt: number };
type SyncHistoryItem = { at: string; text: string; tone: "info" | "ok" | "warn" | "error" };
type EditorSourceOption = { label: string; path: string };
type SnapshotDiff = {
    recordedAt: string;
    statusChanges: Array<{ status: string; delta: number }>;
    maxRiskDelta: number;
    highlights: string[];
    changed: boolean;
};
type ProjectInitStatus = {
    bootstrapRecorded: number;
    inventorySeedStatus: string;
    inventoryCreated: number;
    inventorySkipped: number;
    syncStatus: string;
    error: string;
    at: string;
};
const DEFAULT_PROJECT = "sophia";
const DEFAULT_CANOPY_LIMIT = 50;
const DEFAULT_CANOPY_VIEW = "focus";
const RECORDED_ONLY_STORAGE_KEY = "sophia.forest.recorded_only";
const OPTIMISTIC_WORK_STATUS_TTL_MS = 12_000;
const ROOT_MODULE_ID = "__root__";

function toSingleLine(value: string, max: number = 96): string {
    const normalized = String(value || "").replace(/\s+/g, " ").trim();
    if (normalized.length <= max) return normalized;
    return `${normalized.slice(0, Math.max(1, max - 1))}…`;
}

function normWorkStatus(value: string): string {
    return String(value || "").trim().toUpperCase();
}

function buildSnapshotDiff(prev: CanopyDataResponse | null, next: CanopyDataResponse): SnapshotDiff | null {
    if (!prev) return null;
    const prevSummary = prev.status_summary || {};
    const nextSummary = next.status_summary || {};
    const keys = Array.from(new Set([...Object.keys(prevSummary), ...Object.keys(nextSummary)]));
    const statusChanges = keys
        .map((status) => ({
            status,
            delta: Number(nextSummary[status] || 0) - Number(prevSummary[status] || 0),
        }))
        .filter((row) => row.delta !== 0)
        .sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta));
    const prevRisk = Number(prev.risk?.max_risk_score || 0);
    const nextRisk = Number(next.risk?.max_risk_score || 0);
    const maxRiskDelta = Number((nextRisk - prevRisk).toFixed(2));
    const highlights: string[] = [];
    if (maxRiskDelta > 0) highlights.push(`최대 리스크 +${maxRiskDelta.toFixed(2)}`);
    if (maxRiskDelta < 0) highlights.push(`최대 리스크 ${maxRiskDelta.toFixed(2)}`);
    statusChanges.slice(0, 3).forEach((row) => {
        const sign = row.delta > 0 ? "+" : "";
        highlights.push(`${row.status} ${sign}${row.delta}`);
    });
    return {
        recordedAt: String(next.generated_at || "").trim(),
        statusChanges,
        maxRiskDelta,
        highlights,
        changed: statusChanges.length > 0 || maxRiskDelta !== 0,
    };
}

export type ReportController = {
    projectName: string;
    projectOptions: ForestProjectInfo[];
    includeArchivedProjects: boolean;
    setIncludeArchivedProjects: (value: boolean) => void;
    setProjectName: (value: string) => void;
    selectProject: (value: string) => void;
    createProjectBusy: boolean;
    createProject: (name: string) => Promise<void>;
    projectActionBusyName: string;
    archiveProject: (projectName: string) => Promise<void>;
    unarchiveProject: (projectName: string) => Promise<void>;
    inventorySeedBusy: boolean;
    seedWorkFromInventory: () => Promise<void>;
    projectInitStatusByName: Record<string, ProjectInitStatus>;
    selectedPhaseStepFilter: string;
    setSelectedPhaseStepFilter: (value: string) => void;
    riskThreshold: string;
    setRiskThreshold: (value: string) => void;
    moduleSort: ModuleSort;
    setModuleSort: (value: ModuleSort) => void;
    eventFilter: EventFilter;
    setEventFilter: (value: EventFilter) => void;
    serverModuleFilter: ForestModule;
    setServerModuleFilter: (value: ForestModule) => void;
    canopyView: "focus" | "overview";
    setCanopyView: (value: "focus" | "overview") => void;
    recordedOnly: boolean;
    setRecordedOnly: (value: boolean) => void;
    totalWorkNodesCount: number;
    visibleWorkNodesCount: number;
    hiddenWorkNodesCount: number;
    recordedOnlyHint: string;
    recordedOnlyHiddenSamples: string[];
    syncDigestLine: string;
    snapshotDiff: SnapshotDiff | null;
    syncHistory: SyncHistoryItem[];
    runtimeContract: {
        roadmapRecord: boolean;
    } | null;
    lastRoadmapRecordSummary: string;
    handoffSummary: HandoffSummaryResponse | null;
    applePlan: ApplePlanResponse | null;
    applePlanBusy: boolean;
    syncApplePlan: () => Promise<void>;
    editorSourceOptions: EditorSourceOption[];
    selectedEditorSourcePath: string;
    setSelectedEditorSourcePath: (value: string) => void;
    sourcePath: string;
    setSourcePath: (value: string) => void;
    target: string;
    setTarget: (value: string) => void;
    change: string;
    setChange: (value: string) => void;
    scope: string;
    setScope: (value: string) => void;
    mode: AnalyzeMode;
    modeColor: string;
    message: string;
    pageStatusText: string;
    canGoPrevPage: boolean;
    canGoNextPage: boolean;
    goPrevPage: () => void;
    goNextPage: () => void;
    dashboardSrc: string;
    canopyData: CanopyDataResponse | null;
    bitmapSummary: BitmapSummaryResponse | null;
    bitmapAudit: BitmapAuditResponse | null;
    bitmapActionBusyId: string;
    workActionBusyId: string;
    bitmapEventHighlight: { eventType: string; candidateId: string } | null;
    bitmapHighlightModuleId: string | null;
    selectedBitmapCandidateId: string;
    selectedBitmapCandidate: BitmapCandidateRow | null;
    selectedBitmapTimeline: BitmapTimelineEvent[];
    bitmapTimelineLoading: boolean;
    selectedModule: string;
    rootMode: boolean;
    selectRoot: () => void;
    selectedWorkId: string;
    selectedClusterId: string;
    visibleModuleOverview: ModuleOverview[];
    visibleQuestionQueue: QuestionRow[];
    visibleWorkNodes: WorkNode[];
    filteredWorkNodes: WorkNode[];
    questionQueue: QuestionRow[];
    selectedModuleMeta: ModuleOverview | null;
    selectedWork: WorkNode | null;
    linkedQuestions: QuestionRow[];
    selectedQuestion: QuestionRow | null;
    moduleBottlenecks: WorkNode[];
    roadmapRecordBusy: boolean;
    specReviewBusy: boolean;
    refreshCanopy: () => Promise<void>;
    recordRoadmapSnapshot: () => Promise<void>;
    specIndex: SpecDocSummary[];
    selectedSpecPath: string;
    selectedSpecContent: SpecReadResponse | null;
    specLoading: boolean;
    specUploadBusy: boolean;
    selectSpecPath: (path: string) => void;
    requestSpecReview: (path?: string) => Promise<void>;
    setSpecStatus: (path: string, status: "pending" | "review" | "confirmed", note?: string) => Promise<void>;
    uploadSpecByFile: (event: ChangeEvent<HTMLInputElement>) => Promise<void>;
    todoItems: TodoItem[];
    todoBusy: boolean;
    upsertTodo: (payload: {
        id?: string;
        title: string;
        detail?: string;
        priority_weight?: number;
        category?: string;
        lane?: string;
        spec_ref?: string;
        status?: "todo" | "doing" | "done";
    }) => Promise<void>;
    setTodoStatus: (itemId: string, status: "todo" | "doing" | "done", checked?: boolean) => Promise<void>;
    syncProjectStatus: () => Promise<void>;
    runAnalyzeByPath: () => Promise<void>;
    refreshEditorSourceOptions: () => Promise<void>;
    runAnalyzeSelectedEditorFile: () => Promise<void>;
    runAnalyzeTodayEditorFile: () => Promise<void>;
    runAnalyzeByUpload: (event: ChangeEvent<HTMLInputElement>) => Promise<void>;
    selectModule: (moduleId: string) => void;
    selectWork: (workId: string) => void;
    selectQuestion: (clusterId: string) => void;
    createWorkFromQuestion: () => Promise<void>;
    createWorkFromCluster: (clusterId?: string) => Promise<void>;
    acknowledgeWorkPackage: (workId?: string) => Promise<void>;
    completeWorkPackage: (workId?: string) => Promise<void>;
    selectBitmapCandidate: (candidateId: string) => void;
    adoptBitmapCandidate: (candidateId: string, episodeId: string) => Promise<void>;
    rejectBitmapCandidate: (candidateId: string, episodeId: string, reason?: string) => Promise<void>;
};

export function useReportController(): ReportController {
    const [projectName, setProjectName] = useState(DEFAULT_PROJECT);
    const [projectOptions, setProjectOptions] = useState<ForestProjectInfo[]>([]);
    const [includeArchivedProjects, setIncludeArchivedProjects] = useState(false);
    const [createProjectBusy, setCreateProjectBusy] = useState(false);
    const [projectActionBusyName, setProjectActionBusyName] = useState("");
    const [inventorySeedBusy, setInventorySeedBusy] = useState(false);
    const [projectInitStatusByName, setProjectInitStatusByName] = useState<Record<string, ProjectInitStatus>>({});
    const [selectedPhaseStepFilter, setSelectedPhaseStepFilter] = useState("");
    const [riskThreshold, setRiskThreshold] = useState("0.8");
    const [moduleSort, setModuleSort] = useState<ModuleSort>("importance");
    const [eventFilter, setEventFilter] = useState<EventFilter>("all");
    const [serverModuleFilter, setServerModuleFilter] = useState<ForestModule>("all");
    const [canopyView, setCanopyView] = useState<"focus" | "overview">("focus");
    const [recordedOnly, setRecordedOnly] = useState<boolean>(() => {
        if (typeof window === "undefined") return false;
        try {
            return window.localStorage.getItem(RECORDED_ONLY_STORAGE_KEY) === "1";
        } catch {
            return false;
        }
    });
    const [sourcePath, setSourcePath] = useState("");
    const [target, setTarget] = useState("spec-module");
    const [change, setChange] = useState("문서 변경 검토");
    const [scope, setScope] = useState("");
    const [mode, setMode] = useState<AnalyzeMode>("idle");
    const [message, setMessage] = useState("현황판 준비됨");
    const [refreshSeed, setRefreshSeed] = useState(Date.now());

    const [canopyData, setCanopyData] = useState<CanopyDataResponse | null>(null);
    const [bitmapSummary, setBitmapSummary] = useState<BitmapSummaryResponse | null>(null);
    const [bitmapAudit, setBitmapAudit] = useState<BitmapAuditResponse | null>(null);
    const [bitmapActionBusyId, setBitmapActionBusyId] = useState<string>("");
    const [workActionBusyId, setWorkActionBusyId] = useState<string>("");
    const [optimisticWorkStatusById, setOptimisticWorkStatusById] = useState<Record<string, OptimisticWorkStatusEntry>>({});
    const [bitmapEventHighlight, setBitmapEventHighlight] = useState<{ eventType: string; candidateId: string } | null>(
        null,
    );
    const [selectedBitmapCandidateId, setSelectedBitmapCandidateId] = useState<string>("");
    const [selectedBitmapTimeline, setSelectedBitmapTimeline] = useState<BitmapTimelineEvent[]>([]);
    const [bitmapTimelineLoading, setBitmapTimelineLoading] = useState(false);
    const [roadmapRecordBusy, setRoadmapRecordBusy] = useState(false);
    const [lastRoadmapRecordSummary, setLastRoadmapRecordSummary] = useState("");
    const [specReviewBusy, setSpecReviewBusy] = useState(false);
    const [specIndex, setSpecIndex] = useState<SpecDocSummary[]>([]);
    const [selectedSpecPath, setSelectedSpecPath] = useState("");
    const [selectedSpecContent, setSelectedSpecContent] = useState<SpecReadResponse | null>(null);
    const [specLoading, setSpecLoading] = useState(false);
    const [specUploadBusy, setSpecUploadBusy] = useState(false);
    const [todoItems, setTodoItems] = useState<TodoItem[]>([]);
    const [todoBusy, setTodoBusy] = useState(false);
    const [syncHistory, setSyncHistory] = useState<SyncHistoryItem[]>([]);
    const [snapshotDiff, setSnapshotDiff] = useState<SnapshotDiff | null>(null);
    const [runtimeContract, setRuntimeContract] = useState<{ roadmapRecord: boolean } | null>(null);
    const [handoffSummary, setHandoffSummary] = useState<HandoffSummaryResponse | null>(null);
    const [applePlan, setApplePlan] = useState<ApplePlanResponse | null>(null);
    const [applePlanBusy, setApplePlanBusy] = useState(false);
    const applePlanAutoSyncRef = useRef<Record<string, boolean>>({});
    const [canopyOffset, setCanopyOffset] = useState(0);
    const [editorSourceOptions, setEditorSourceOptions] = useState<EditorSourceOption[]>([]);
    const [selectedEditorSourcePath, setSelectedEditorSourcePath] = useState("");
    const [selectedModule, setSelectedModule] = useState<string>("");
    const [selectedWorkId, setSelectedWorkId] = useState<string>("");
    const [selectedClusterId, setSelectedClusterId] = useState<string>("");
    const [activeFocus, setActiveFocus] = useState<{ kind: FocusKind; id: string } | null>(null);
    const previousCanopyRef = useRef<CanopyDataResponse | null>(null);

    const pushSyncHistory = useCallback((text: string, tone: SyncHistoryItem["tone"] = "info") => {
        const row: SyncHistoryItem = {
            at: new Date().toISOString(),
            text: toSingleLine(text, 96),
            tone,
        };
        setSyncHistory((prev) => [row, ...prev].slice(0, 3));
    }, []);

    const highlightKey = useMemo(() => {
        if (!activeFocus?.id) return "";
        if (activeFocus.kind === "module") return `module:${activeFocus.id}`;
        if (activeFocus.kind === "work") return `work:${activeFocus.id}`;
        return `question:${activeFocus.id}`;
    }, [activeFocus]);

    const dashboardSrc = useMemo(() => {
        const safeProject = encodeURIComponent((projectName || DEFAULT_PROJECT).trim() || DEFAULT_PROJECT);
        const base = `${API_BASE}/dashboard/${safeProject}/dashboard/?t=${refreshSeed}`;
        if (!highlightKey) return base;
        return `${base}&highlight=${encodeURIComponent(highlightKey)}`;
    }, [refreshSeed, highlightKey, projectName]);

    useEffect(() => {
        setCanopyOffset(0);
    }, [projectName, riskThreshold, moduleSort, eventFilter, serverModuleFilter, canopyView]);

    const loadCanopyData = useCallback(
        async (options?: { eventFilter?: EventFilter }) => {
            const threshold = Number.parseFloat(riskThreshold);
            const effectiveEventFilter = options?.eventFilter ?? eventFilter;
            const queryParts: string[] = [];
            queryParts.push(`view=${canopyView || DEFAULT_CANOPY_VIEW}`);
            if (Number.isFinite(threshold)) queryParts.push(`risk_threshold=${threshold}`);
            queryParts.push(`module_sort=${moduleSort}`);
            queryParts.push(`event_filter=${effectiveEventFilter}`);
            queryParts.push(`limit=${DEFAULT_CANOPY_LIMIT}`);
            queryParts.push(`offset=${canopyOffset}`);
            queryParts.push(`module=${serverModuleFilter}`);
            const canopyQuery = `?${queryParts.join("&")}`;
            const endpoint = apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/canopy/data${canopyQuery}&_ts=${Date.now()}`);
            const response = await fetch(endpoint, { cache: "no-store" });
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(parseErrorText(errText));
            }
            const body = (await response.json()) as CanopyDataResponse;
            const nextDiff = buildSnapshotDiff(previousCanopyRef.current, body);
            setSnapshotDiff(nextDiff);
            setCanopyData(body);
            previousCanopyRef.current = body;

            const modules = Array.isArray(body.module_overview) ? body.module_overview : [];
            const defaultModule = modules[0]?.module ?? "";
            setSelectedModule((prev) => {
                if (prev === ROOT_MODULE_ID) return prev;
                if (prev && modules.some((row) => row.module === prev)) return prev;
                return defaultModule;
            });

            const questions = Array.isArray(body.question_queue) ? body.question_queue : [];
            const defaultCluster = questions[0]?.cluster_id ?? "";
            setSelectedClusterId((prev) => {
                if (prev && questions.some((row) => row.cluster_id === prev)) return prev;
                return defaultCluster;
            });

            const works = Array.isArray(body.nodes)
                ? (body.nodes.filter((row) => row?.type === "work") as WorkNode[])
                : [];
            const missionId = String(body?.focus?.current_mission_id || "").trim();
            const preferredWorkId = missionId && works.some((row) => row.id === missionId) ? missionId : works[0]?.id || "";
            setSelectedWorkId((prev) => {
                if (prev && works.some((row) => row.id === prev)) return prev;
                return preferredWorkId;
            });
        },
        [projectName, riskThreshold, moduleSort, eventFilter, canopyOffset, serverModuleFilter, canopyView],
    );

    const loadBitmapSummary = useCallback(async () => {
        const endpoint = apiUrl("/mind/bitmap?days=7");
        const response = await fetch(endpoint, { cache: "no-store" });
        if (!response.ok) {
            const errText = await response.text();
            throw new Error(parseErrorText(errText));
        }
        const body = (await response.json()) as BitmapSummaryResponse;
        setBitmapSummary(body);
    }, []);

    const loadBitmapAudit = useCallback(async () => {
        const endpoint = apiUrl("/mind/bitmap/audit?days=30&limit=20&reason_limit=8");
        const response = await fetch(endpoint, { cache: "no-store" });
        if (!response.ok) {
            const errText = await response.text();
            throw new Error(parseErrorText(errText));
        }
        const body = (await response.json()) as BitmapAuditResponse;
        setBitmapAudit(body);
    }, []);

    const checkRuntimeContract = useCallback(async () => {
        try {
            const response = await fetch(apiUrl(`/openapi.json?_ts=${Date.now()}`), { cache: "no-store" });
            if (!response.ok) {
                setRuntimeContract({ roadmapRecord: false });
                pushSyncHistory("서버 계약 확인 실패: openapi 접근 불가", "warn");
                return;
            }
            const body = (await response.json()) as { paths?: Record<string, unknown> };
            const hasRoadmapRecord = Boolean(body?.paths?.["/forest/projects/{project_name}/roadmap/record"]);
            setRuntimeContract({ roadmapRecord: hasRoadmapRecord });
            if (!hasRoadmapRecord) {
                pushSyncHistory("구버전 서버 감지: roadmap/record API 없음", "warn");
            }
        } catch {
            setRuntimeContract({ roadmapRecord: false });
            pushSyncHistory("서버 계약 확인 실패: 네트워크/런타임 확인 필요", "warn");
        }
    }, [pushSyncHistory]);

    const flattenEditorFiles = useCallback((nodes: NoteFileNode[], bucket: EditorSourceOption[] = []): EditorSourceOption[] => {
        for (const node of nodes) {
            if (node.isDirectory) {
                if (Array.isArray(node.children) && node.children.length > 0) {
                    flattenEditorFiles(node.children as NoteFileNode[], bucket);
                }
                continue;
            }
            const path = String(node.path || "").trim();
            const name = String(node.name || "").trim();
            if (!path || !name) continue;
            const lower = name.toLowerCase();
            if (!(lower.endsWith(".md") || lower.endsWith(".markdown") || lower.endsWith(".txt"))) continue;
            bucket.push({ label: name, path });
        }
        return bucket;
    }, []);

    const loadEditorSourceOptions = useCallback(async () => {
        try {
            const tree = await noteService.listNotes();
            const flat = flattenEditorFiles(Array.isArray(tree) ? (tree as NoteFileNode[]) : []);
            flat.sort((a, b) => a.label.localeCompare(b.label));
            setEditorSourceOptions(flat);
            setSelectedEditorSourcePath((prev) => {
                if (prev && flat.some((row) => row.path === prev)) return prev;
                return flat[0]?.path || "";
            });
        } catch {
            setEditorSourceOptions([]);
            setSelectedEditorSourcePath("");
        }
    }, [flattenEditorFiles]);

    const loadProjectOptions = useCallback(async () => {
        try {
            const response = await fetch(
                apiUrl(
                    `/forest/projects?include_archived=${includeArchivedProjects ? "true" : "false"}&_ts=${Date.now()}`,
                ),
                { cache: "no-store" },
            );
            if (!response.ok) {
                throw new Error(parseErrorText(await response.text()));
            }
            const body = (await response.json()) as { projects?: ForestProjectInfo[] };
            const rows = Array.isArray(body.projects) ? body.projects : [];
            setProjectOptions(rows);
            setProjectName((prev) => {
                if (rows.some((row) => String(row.project_name || "").trim() === prev)) return prev;
                return String(rows[0]?.project_name || DEFAULT_PROJECT);
            });
        } catch {
            setProjectOptions((prev) => {
                if (prev.length > 0) return prev;
                return [
                    {
                        project_name: DEFAULT_PROJECT,
                        progress_pct: 0,
                        remaining_work: 0,
                        blocked_count: 0,
                        unverified_count: 0,
                        updated_at: "",
                    },
                ];
            });
        }
    }, [includeArchivedProjects]);

    const loadSpecIndex = useCallback(async () => {
        try {
            const endpoint = apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/spec/index?_ts=${Date.now()}`);
            const response = await fetch(endpoint, { cache: "no-store" });
            if (!response.ok) {
                throw new Error(parseErrorText(await response.text()));
            }
            const body = (await response.json()) as SpecIndexResponse;
            const rows = Array.isArray(body.items) ? body.items : [];
            setSpecIndex(rows);
            setSelectedSpecPath((prev) => {
                if (prev && rows.some((row) => row.path === prev)) return prev;
                return rows[0]?.path || "";
            });
        } catch {
            setSpecIndex([]);
            setSelectedSpecPath("");
        }
    }, [projectName]);

    const loadTodoItems = useCallback(async () => {
        try {
            const endpoint = apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/todo?_ts=${Date.now()}`);
            const response = await fetch(endpoint, { cache: "no-store" });
            if (!response.ok) {
                throw new Error(parseErrorText(await response.text()));
            }
            const body = (await response.json()) as TodoListResponse;
            const rows = Array.isArray(body.items) ? body.items : [];
            rows.sort((left, right) => {
                const statusRank = (value: string) => {
                    const raw = String(value || "").toLowerCase();
                    if (raw === "doing") return 0;
                    if (raw === "todo") return 1;
                    return 2;
                };
                const p = Number(right.priority_weight || 0) - Number(left.priority_weight || 0);
                if (p !== 0) return p;
                const s = statusRank(String(left.status || "")) - statusRank(String(right.status || ""));
                if (s !== 0) return s;
                return String(left.title || "").localeCompare(String(right.title || ""));
            });
            setTodoItems(rows);
        } catch {
            setTodoItems([]);
        }
    }, [projectName]);

    const loadHandoffSummary = useCallback(async () => {
        try {
            const endpoint = apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/handoff?_ts=${Date.now()}`);
            const response = await fetch(endpoint, { cache: "no-store" });
            if (!response.ok) {
                throw new Error(parseErrorText(await response.text()));
            }
            const body = (await response.json()) as HandoffSummaryResponse;
            setHandoffSummary(body);
        } catch {
            setHandoffSummary(null);
        }
    }, [projectName]);

    const loadApplePlan = useCallback(async () => {
        try {
            const endpoint = apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/apple/status-plan?_ts=${Date.now()}`);
            const response = await fetch(endpoint, { cache: "no-store" });
            if (!response.ok) {
                throw new Error(parseErrorText(await response.text()));
            }
            const body = (await response.json()) as ApplePlanResponse;
            setApplePlan(body);
        } catch {
            setApplePlan(null);
        }
    }, [projectName]);

    const loadSpecContent = useCallback(
        async (path: string) => {
            const target = String(path || "").trim();
            if (!target) {
                setSelectedSpecContent(null);
                return;
            }
            setSpecLoading(true);
            try {
                const endpoint = apiUrl(
                    `/forest/projects/${encodeURIComponent(projectName)}/spec/read?path=${encodeURIComponent(target)}&_ts=${Date.now()}`,
                );
                const response = await fetch(endpoint, { cache: "no-store" });
                if (!response.ok) {
                    throw new Error(parseErrorText(await response.text()));
                }
                const body = (await response.json()) as SpecReadResponse;
                setSelectedSpecContent(body);
            } catch {
                setSelectedSpecContent(null);
            } finally {
                setSpecLoading(false);
            }
        },
        [projectName],
    );

    useEffect(() => {
        const rows = bitmapSummary?.candidates || [];
        if (!rows.length) {
            setSelectedBitmapCandidateId("");
            return;
        }
        setSelectedBitmapCandidateId((prev) => {
            if (prev && rows.some((row) => row.id === prev)) return prev;
            const pending = rows.find((row) => String(row.status || "").toUpperCase() === "PENDING");
            return (pending?.id || rows[0]?.id || "").trim();
        });
    }, [bitmapSummary]);

    useEffect(() => {
        void loadEditorSourceOptions();
    }, [loadEditorSourceOptions]);

    useEffect(() => {
        void loadProjectOptions();
    }, [loadProjectOptions]);

    useEffect(() => {
        void loadSpecIndex();
    }, [loadSpecIndex]);

    useEffect(() => {
        void loadTodoItems();
    }, [loadTodoItems]);

    useEffect(() => {
        void loadHandoffSummary();
    }, [loadHandoffSummary]);

    useEffect(() => {
        void loadApplePlan();
    }, [loadApplePlan]);

    useEffect(() => {
        void loadSpecContent(selectedSpecPath);
    }, [selectedSpecPath, loadSpecContent]);

    const refreshCanopy = useCallback(async () => {
        setMode("running");
        setMessage("진행상태/현황판 동기화 중...");
        const queryParts: string[] = [];
        const threshold = Number.parseFloat(riskThreshold);
        queryParts.push(`view=${canopyView || DEFAULT_CANOPY_VIEW}`);
        if (Number.isFinite(threshold)) queryParts.push(`risk_threshold=${threshold}`);
        queryParts.push(`module_sort=${moduleSort}`);
        queryParts.push(`event_filter=${eventFilter}`);
        queryParts.push("export_canopy=true");
        const endpoint = apiUrl(
            `/forest/projects/${encodeURIComponent(projectName)}/status/sync?${queryParts.join("&")}&_ts=${Date.now()}`,
        );
        try {
            const response = await fetch(endpoint, { method: "POST", cache: "no-store" });
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(parseErrorText(errText));
            }
            setRefreshSeed(Date.now());
            await Promise.all([
                loadCanopyData(),
                loadBitmapSummary(),
                loadBitmapAudit(),
                loadSpecIndex(),
                loadTodoItems(),
                loadHandoffSummary(),
                loadApplePlan(),
            ]);
            await loadProjectOptions();
            setMode("success");
            setMessage("진행상태 동기화 완료");
            pushSyncHistory("진행상태 동기화 완료", "ok");
        } catch (error) {
            setMode("error");
            setMessage(`진행상태 동기화 실패: ${String(error)}`);
            pushSyncHistory(`진행상태 동기화 실패: ${String(error)}`, "error");
        }
    }, [
        projectName,
        riskThreshold,
        moduleSort,
        eventFilter,
        canopyView,
        loadCanopyData,
        loadBitmapSummary,
        loadBitmapAudit,
        loadSpecIndex,
        loadTodoItems,
        loadHandoffSummary,
        loadApplePlan,
        loadProjectOptions,
        pushSyncHistory,
    ]);

    const recordRoadmapSnapshot = useCallback(async () => {
        if (roadmapRecordBusy) return;
        setRoadmapRecordBusy(true);
        setMode("running");
        setMessage("로드맵 스냅샷 기록 중...");
        try {
            const focus = canopyData?.focus || {};
            const humanView = canopyData?.human_view || {};
            const summaryCards = Array.isArray((humanView as { summary_cards?: unknown[] }).summary_cards)
                ? ((humanView as { summary_cards?: Array<{ text?: string }> }).summary_cards || [])
                : [];
            const mission = (focus as { current_mission?: { label?: string; kind?: string; status?: string } }).current_mission;
            const missionLabel = String(mission?.label || "").trim();
            const missionKind = String(mission?.kind || "").toUpperCase();
            const missionStatus = String(mission?.status || "").toUpperCase();
            const summaryText = summaryCards
                .map((card) => toSingleLine(card?.text || "", 40))
                .filter((text) => Boolean(text))
                .slice(0, 2)
                .join(" | ");
            const nowProblem = toSingleLine(summaryCards[0]?.text || "", 40);
            const category =
                missionStatus === "BLOCKED" || missionStatus === "FAILED" || nowProblem.includes("문제")
                    ? "PROBLEM_FIX"
                    : missionKind === "IMPLEMENT" || missionKind === "MIGRATE"
                      ? "FEATURE_ADD"
                      : "SYSTEM_CHANGE";
            const roadmapNow = (humanView as { roadmap_now?: { phase?: string; phase_step?: string } }).roadmap_now;
            const phase = String(roadmapNow?.phase || "1").trim() || "1";
            const phaseStep =
                String(roadmapNow?.phase_step || "").trim() ||
                (category === "SYSTEM_CHANGE" ? `${phase}.1` : category === "PROBLEM_FIX" ? `${phase}.2` : `${phase}.3`);
            const payload = {
                note: "",
                title: missionLabel ? toSingleLine(`${missionLabel} 진행 기록`, 72) : "focus snapshot",
                summary: summaryText || "focus snapshot",
                category,
                phase,
                phase_step: phaseStep,
                phase_title: "Forest 항법/현황판 고도화",
                tags: ["manual", "focus", `phase:${phase}`, `phase_step:${phaseStep}`],
                owner: "codex",
                lane: "codex",
                scope: "project",
            };
            const endpoint = apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/roadmap/record?_ts=${Date.now()}`);
            const response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                cache: "no-store",
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(parseErrorText(errText));
            }
            const body = (await response.json()) as {
                recorded?: number;
                skipped?: number;
                skipped_items?: Array<{ reason?: string }>;
            };
            setMode("success");
            if (Number(body?.recorded || 0) > 0) {
                setMessage(`로드맵 기록 완료 (${category})`);
                setLastRoadmapRecordSummary(toSingleLine(`로드맵 기록: Phase ${phase}/${phaseStep} · ${category} 1건`));
                pushSyncHistory(`로드맵 기록 완료 (${category})`, "ok");
            } else {
                const reason = String(body?.skipped_items?.[0]?.reason || "policy_skip");
                setMessage(`로드맵 기록 스킵 (${reason})`);
                setLastRoadmapRecordSummary(toSingleLine(`로드맵 스킵: ${reason}`));
                pushSyncHistory(`로드맵 기록 스킵 (${reason})`, "warn");
            }
            await Promise.all([loadCanopyData(), loadSpecIndex(), loadTodoItems(), loadHandoffSummary(), loadApplePlan()]);
            await loadProjectOptions();
        } catch (error) {
            setMode("error");
            setMessage(`로드맵 기록 실패: ${String(error)}`);
            setLastRoadmapRecordSummary("로드맵 기록 실패");
            pushSyncHistory(`로드맵 기록 실패: ${String(error)}`, "error");
        } finally {
            setRoadmapRecordBusy(false);
        }
    }, [projectName, roadmapRecordBusy, loadCanopyData, canopyData, pushSyncHistory, loadProjectOptions, loadSpecIndex, loadTodoItems, loadHandoffSummary, loadApplePlan]);

    useEffect(() => {
        void refreshCanopy();
    }, [refreshCanopy]);

    useEffect(() => {
        void checkRuntimeContract();
    }, [checkRuntimeContract]);

    const syncProjectStatus = useCallback(async () => {
        setMode("running");
        setMessage("진행상태/로드맵 동기화 중...");

        const queryParts: string[] = [];
        const threshold = Number.parseFloat(riskThreshold);
        queryParts.push(`view=${canopyView || DEFAULT_CANOPY_VIEW}`);
        if (Number.isFinite(threshold)) queryParts.push(`risk_threshold=${threshold}`);
        queryParts.push(`module_sort=${moduleSort}`);
        queryParts.push(`event_filter=${eventFilter}`);
        queryParts.push("export_canopy=true");
        const endpoint = apiUrl(
            `/forest/projects/${encodeURIComponent(projectName)}/status/sync?${queryParts.join("&")}&_ts=${Date.now()}`,
        );
        try {
            const response = await fetch(endpoint, { method: "POST", cache: "no-store" });
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(parseErrorText(errText));
            }
            setRefreshSeed(Date.now());
            await Promise.all([
                loadCanopyData(),
                loadBitmapSummary(),
                loadBitmapAudit(),
                loadSpecIndex(),
                loadTodoItems(),
                loadHandoffSummary(),
                loadApplePlan(),
            ]);
            await loadProjectOptions();
            setMode("success");
            setMessage("진행상태 동기화 완료");
            pushSyncHistory("진행상태 동기화 완료", "ok");
        } catch (error) {
            setMode("error");
            setMessage(`진행상태 동기화 실패: ${String(error)}`);
            pushSyncHistory(`진행상태 동기화 실패: ${String(error)}`, "error");
        }
    }, [
        projectName,
        riskThreshold,
        moduleSort,
        eventFilter,
        loadCanopyData,
        loadBitmapSummary,
        loadBitmapAudit,
        loadSpecIndex,
        loadTodoItems,
        loadHandoffSummary,
        loadApplePlan,
        loadProjectOptions,
        canopyView,
        pushSyncHistory,
    ]);

    const requestSpecReview = useCallback(
        async (path?: string) => {
            const targetPath = String(path || selectedSpecPath || "").trim();
            if (!targetPath || specReviewBusy) return;
            setSpecReviewBusy(true);
            setMode("running");
            setMessage(`명세 SonE 검토 실행 중: ${targetPath}`);
            try {
                const response = await fetch(
                    apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/spec/review-run`),
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            path: targetPath,
                            owner: "codex",
                            lane: "codex",
                            note: "사용자 검토 요청 기준 SonE 검토 실행",
                            target: target.trim() || "spec-module",
                            change: change.trim() || "명세 검토",
                            scope: scope.trim() || null,
                        }),
                    },
                );
                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error(parseErrorText(errText));
                }
                await Promise.all([loadCanopyData(), loadSpecIndex(), loadSpecContent(targetPath), loadHandoffSummary()]);
                setMode("success");
                setMessage("명세 SonE 검토 완료");
                pushSyncHistory("명세 SonE 검토 완료", "ok");
            } catch (error) {
                const errorText = error instanceof Error ? error.message : String(error);
                setMode("error");
                setMessage(`명세 SonE 검토 실패: ${errorText}`);
                pushSyncHistory(`명세 SonE 검토 실패: ${errorText}`, "error");
            } finally {
                setSpecReviewBusy(false);
            }
        },
        [
            projectName,
            selectedSpecPath,
            specReviewBusy,
            loadCanopyData,
            loadSpecIndex,
            loadSpecContent,
            loadHandoffSummary,
            pushSyncHistory,
            target,
            change,
            scope,
        ],
    );

    const setSpecStatus = useCallback(
        async (path: string, status: "pending" | "review" | "confirmed", note?: string) => {
            const targetPath = String(path || "").trim();
            if (!targetPath || specReviewBusy) return;
            setSpecReviewBusy(true);
            setMode("running");
            setMessage(`문서 상태 변경 중: ${status}`);
            try {
                const response = await fetch(
                    apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/spec/status`),
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            path: targetPath,
                            status,
                            owner: "user",
                            lane: "user",
                            note: String(note || "").trim() || `문서 상태 변경: ${status}`,
                        }),
                    },
                );
                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error(parseErrorText(errText));
                }
                await Promise.all([loadCanopyData(), loadSpecIndex(), loadSpecContent(targetPath), loadHandoffSummary()]);
                setMode("success");
                setMessage(`문서 상태 변경 완료: ${status}`);
                pushSyncHistory(`문서 상태 변경 완료: ${status}`, "ok");
            } catch (error) {
                const errorText = error instanceof Error ? error.message : String(error);
                setMode("error");
                setMessage(`문서 상태 변경 실패: ${errorText}`);
                pushSyncHistory(`문서 상태 변경 실패: ${errorText}`, "error");
            } finally {
                setSpecReviewBusy(false);
            }
        },
        [projectName, specReviewBusy, loadCanopyData, loadSpecIndex, loadSpecContent, loadHandoffSummary, pushSyncHistory],
    );

    const uploadSpecByFile = useCallback(
        async (event: ChangeEvent<HTMLInputElement>) => {
            const file = event.target.files?.[0];
            if (!file) return;
            setSpecUploadBusy(true);
            setMode("running");
            setMessage(`문서 업로드 중: ${file.name}`);
            try {
                const content = await file.text();
                const lower = file.name.toLowerCase();
                const docType: "constitution" | "plan" | "spec" | "guide" =
                    lower.includes("constitution") || lower.includes("헌법")
                        ? "constitution"
                        : lower.includes("plan") || lower.includes("roadmap") || lower.includes("계획")
                          ? "plan"
                          : lower.includes("guide") || lower.includes("workflow")
                            ? "guide"
                            : "spec";
                const response = await fetch(
                    apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/spec/upload`),
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            file_name: file.name,
                            content,
                            doc_type: docType,
                            owner: "user",
                            lane: "user",
                            note: "사용자 업로드",
                        }),
                    },
                );
                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error(parseErrorText(errText));
                }
                await Promise.all([loadCanopyData(), loadSpecIndex(), loadHandoffSummary()]);
                setMode("success");
                setMessage("문서 업로드 완료");
                pushSyncHistory("문서 업로드 완료", "ok");
            } catch (error) {
                const errorText = error instanceof Error ? error.message : String(error);
                setMode("error");
                setMessage(`문서 업로드 실패: ${errorText}`);
                pushSyncHistory(`문서 업로드 실패: ${errorText}`, "error");
            } finally {
                setSpecUploadBusy(false);
                event.target.value = "";
            }
        },
        [projectName, loadCanopyData, loadSpecIndex, loadHandoffSummary, pushSyncHistory],
    );

    const upsertTodo = useCallback(
        async (payload: {
            id?: string;
            title: string;
            detail?: string;
            priority_weight?: number;
            category?: string;
            lane?: string;
            spec_ref?: string;
            status?: "todo" | "doing" | "done";
        }) => {
            const title = String(payload.title || "").trim();
            if (!title) return;
            setTodoBusy(true);
            setMode("running");
            setMessage(`TODO 저장 중: ${title}`);
            try {
                const response = await fetch(
                    apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/todo/upsert`),
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            id: payload.id,
                            title,
                            detail: String(payload.detail || "").trim() || null,
                            priority_weight: Number(payload.priority_weight || 50),
                            category: String(payload.category || "").trim() || "general",
                            lane: String(payload.lane || "").trim() || "general",
                            spec_ref: String(payload.spec_ref || "").trim() || null,
                            status: payload.status || "todo",
                        }),
                    },
                );
                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error(parseErrorText(errText));
                }
                await loadTodoItems();
                await Promise.all([loadCanopyData(), loadHandoffSummary()]);
                setMode("success");
                setMessage("TODO 저장 완료");
                pushSyncHistory("TODO 저장 완료", "ok");
            } catch (error) {
                const errorText = error instanceof Error ? error.message : String(error);
                setMode("error");
                setMessage(`TODO 저장 실패: ${errorText}`);
                pushSyncHistory(`TODO 저장 실패: ${errorText}`, "error");
            } finally {
                setTodoBusy(false);
            }
        },
        [projectName, loadTodoItems, loadCanopyData, loadHandoffSummary, pushSyncHistory],
    );

    const setTodoStatus = useCallback(
        async (itemId: string, status: "todo" | "doing" | "done", checked?: boolean) => {
            const id = String(itemId || "").trim();
            if (!id) return;
            setTodoBusy(true);
            setMode("running");
            setMessage(`TODO 상태 변경 중: ${id}`);
            try {
                const response = await fetch(
                    apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/todo/${encodeURIComponent(id)}/status`),
                    {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            status,
                            checked: typeof checked === "boolean" ? checked : status === "done",
                        }),
                    },
                );
                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error(parseErrorText(errText));
                }
                await loadTodoItems();
                await Promise.all([loadCanopyData(), loadHandoffSummary()]);
                setMode("success");
                setMessage(`TODO 상태 변경 완료: ${id}`);
                pushSyncHistory(`TODO 상태 변경 완료: ${id}`, "ok");
            } catch (error) {
                const errorText = error instanceof Error ? error.message : String(error);
                setMode("error");
                setMessage(`TODO 상태 변경 실패: ${errorText}`);
                pushSyncHistory(`TODO 상태 변경 실패: ${errorText}`, "error");
            } finally {
                setTodoBusy(false);
            }
        },
        [projectName, loadTodoItems, loadCanopyData, loadHandoffSummary, pushSyncHistory],
    );

    const syncApplePlan = useCallback(async () => {
        if (applePlanBusy) return;
        setApplePlanBusy(true);
        setMode("running");
        setMessage("Apple Intelligence 구현계획 동기화 중...");
        try {
            const response = await fetch(
                apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/apple/plan/sync`),
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ owner: "codex", lane: "codex", force: false }),
                },
            );
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(parseErrorText(errText));
            }
            await Promise.all([
                loadApplePlan(),
                loadTodoItems(),
                loadCanopyData(),
                loadHandoffSummary(),
                loadProjectOptions(),
            ]);
            setMode("success");
            setMessage("Apple Intelligence 구현계획 동기화 완료");
            pushSyncHistory("Apple 구현계획 동기화 완료", "ok");
        } catch (error) {
            const errorText = error instanceof Error ? error.message : String(error);
            setMode("error");
            setMessage(`Apple 구현계획 동기화 실패: ${errorText}`);
            pushSyncHistory(`Apple 구현계획 동기화 실패: ${errorText}`, "error");
        } finally {
            setApplePlanBusy(false);
        }
    }, [
        applePlanBusy,
        projectName,
        loadApplePlan,
        loadTodoItems,
        loadCanopyData,
        loadHandoffSummary,
        loadProjectOptions,
        pushSyncHistory,
    ]);

    useEffect(() => {
        const project = String(projectName || "").trim();
        if (!project) return;
        if (!applePlan || applePlanBusy) return;
        const unsyncedCount = Number(applePlan.todo_unsynced_count || 0);
        if (unsyncedCount <= 0) return;
        if (applePlanAutoSyncRef.current[project]) return;
        applePlanAutoSyncRef.current[project] = true;
        void syncApplePlan();
    }, [projectName, applePlan, applePlanBusy, syncApplePlan]);

    const runAnalyzeByPath = useCallback(async () => {
        const trimmedPath = sourcePath.trim();
        if (!trimmedPath) {
            setMode("error");
            setMessage("분석할 파일 경로를 입력해주세요.");
            return;
        }

        setMode("running");
        setMessage("파일 기반 SonE 분석 실행 중...");
        const endpoint = apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/grove/analyze/path`);
        const payload = {
            path: trimmedPath,
            target: target.trim() || "spec-module",
            change: change.trim() || "문서 변경 검토",
            scope: scope.trim() || null,
        };

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(parseErrorText(errText));
            }
            setMode("success");
            setMessage("파일 SonE 검증 완료. 현황판 갱신 중...");
            await refreshCanopy();
        } catch (error) {
            setMode("error");
            setMessage(`파일 분석 실패: ${String(error)}`);
        }
    }, [sourcePath, projectName, target, change, scope, refreshCanopy]);

    const runAnalyzeSelectedEditorFile = useCallback(async () => {
        const selectedPath = selectedEditorSourcePath.trim();
        if (!selectedPath) {
            setMode("error");
            setMessage("선택된 에디터 파일이 없습니다.");
            return;
        }
        const exists = await noteService.exists(selectedPath);
        if (!exists) {
            setMode("error");
            setMessage(`선택 파일이 존재하지 않습니다: ${selectedPath}`);
            return;
        }
        setSourcePath(selectedPath);
        setMode("running");
        setMessage(`선택 파일 분석 중: ${selectedPath}`);

        const endpoint = apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/grove/analyze/path`);
        const payload = {
            path: selectedPath,
            target: target.trim() || "spec-module",
            change: change.trim() || "문서 변경 검토",
            scope: scope.trim() || null,
        };

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(parseErrorText(errText));
            }
            setMode("success");
            setMessage("선택 파일 SonE 검증 완료. 현황판 갱신 중...");
            await refreshCanopy();
        } catch (error) {
            setMode("error");
            setMessage(`선택 파일 분석 실패: ${String(error)}`);
        }
    }, [selectedEditorSourcePath, projectName, target, change, scope, refreshCanopy]);

    const runAnalyzeTodayEditorFile = useCallback(async () => {
        const todayPath = noteService.getTodayFileName();
        const exists = await noteService.exists(todayPath);
        if (!exists) {
            setMode("error");
            setMessage(`오늘 파일이 없습니다. 에디터에서 먼저 저장하세요: ${todayPath}`);
            return;
        }
        setSourcePath(todayPath);
        setMode("running");
        setMessage(`오늘 에디터 파일 분석 준비: ${todayPath}`);

        const endpoint = apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/grove/analyze/path`);
        const payload = {
            path: todayPath,
            target: target.trim() || "spec-module",
            change: change.trim() || "문서 변경 검토",
            scope: scope.trim() || null,
        };

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(parseErrorText(errText));
            }
            setMode("success");
            setMessage("에디터 파일 SonE 검증 완료. 현황판 갱신 중...");
            await refreshCanopy();
        } catch (error) {
            setMode("error");
            setMessage(`에디터 파일 분석 실패: ${String(error)}`);
        }
    }, [projectName, target, change, scope, refreshCanopy]);

    const runAnalyzeByUpload = useCallback(
        async (event: ChangeEvent<HTMLInputElement>) => {
            const file = event.target.files?.[0];
            if (!file) return;

            setMode("running");
            setMessage(`업로드 파일 분석 중: ${file.name}`);

            try {
                const content = await file.text();
                const endpoint = apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/grove/analyze`);
                const response = await fetch(endpoint, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        doc_name: file.name,
                        content,
                        target: target.trim() || "spec-module",
                        change: change.trim() || "문서 변경 검토",
                        scope: scope.trim() || null,
                    }),
                });
                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error(parseErrorText(errText));
                }
                setMode("success");
                setMessage("업로드 문서 SonE 검증 완료. 현황판 갱신 중...");
                await refreshCanopy();
            } catch (error) {
                setMode("error");
                setMessage(`업로드 분석 실패: ${String(error)}`);
            } finally {
                event.target.value = "";
            }
        },
        [projectName, target, change, scope, refreshCanopy],
    );

    const modeColor =
        mode === "error"
            ? "text-red-300"
            : mode === "success"
              ? "text-emerald-300"
              : mode === "running"
                ? "text-amber-300"
                : "text-gray-300";

    const pageMeta = canopyData?.pagination?.nodes;
    const canGoPrevPage = canopyOffset > 0;
    const canGoNextPage = Boolean(pageMeta?.has_more);
    const pageStatusText = useMemo(() => {
        const total = Number(pageMeta?.total || 0);
        const returned = Number(pageMeta?.returned || 0);
        const start = total === 0 ? 0 : canopyOffset + 1;
        const end = total === 0 ? 0 : canopyOffset + returned;
        return `${start}-${end} / ${total}`;
    }, [canopyOffset, pageMeta]);

    const goPrevPage = useCallback(() => {
        setCanopyOffset((prev) => Math.max(0, prev - DEFAULT_CANOPY_LIMIT));
    }, []);

    const goNextPage = useCallback(() => {
        setCanopyOffset((prev) => prev + DEFAULT_CANOPY_LIMIT);
    }, []);

    const workNodes = useMemo(() => {
        const rows = Array.isArray(canopyData?.nodes) ? canopyData.nodes : [];
        return (rows.filter((row): row is WorkNode => row?.type === "work") as WorkNode[]).map((row) => {
            const id = String(row.id || "").trim();
            if (!id) return row;
            const optimistic = optimisticWorkStatusById[id]?.status;
            if (!optimistic) return row;
            return { ...row, status: optimistic };
        });
    }, [canopyData, optimisticWorkStatusById]);

    useEffect(() => {
        if (!canopyData || Object.keys(optimisticWorkStatusById).length === 0) return;
        const serverRows = Array.isArray(canopyData.nodes)
            ? (canopyData.nodes.filter((row): row is WorkNode => row?.type === "work") as WorkNode[])
            : [];
        const serverStatusById = new Map<string, string>();
        serverRows.forEach((row) => {
            const id = String(row.id || "").trim();
            if (!id) return;
            serverStatusById.set(id, normWorkStatus(String(row.status || "")));
        });
        setOptimisticWorkStatusById((prev) => {
            const keys = Object.keys(prev);
            if (keys.length === 0) return prev;
            const now = Date.now();
            let changed = false;
            const next: Record<string, OptimisticWorkStatusEntry> = { ...prev };
            keys.forEach((id) => {
                const optimistic = normWorkStatus(String(prev[id]?.status || ""));
                const server = serverStatusById.get(id);
                if (server === optimistic) {
                    delete next[id];
                    changed = true;
                    return;
                }
                if (Number(prev[id]?.expiresAt || 0) <= now) {
                    delete next[id];
                    changed = true;
                }
            });
            return changed ? next : prev;
        });
    }, [canopyData, optimisticWorkStatusById]);

    useEffect(() => {
        if (Object.keys(optimisticWorkStatusById).length === 0) return;
        const timer = setTimeout(() => {
            setOptimisticWorkStatusById((prev) => {
                const keys = Object.keys(prev);
                if (keys.length === 0) return prev;
                const now = Date.now();
                let changed = false;
                const next: Record<string, OptimisticWorkStatusEntry> = { ...prev };
                keys.forEach((id) => {
                    if (Number(prev[id]?.expiresAt || 0) <= now) {
                        delete next[id];
                        changed = true;
                    }
                });
                return changed ? next : prev;
            });
        }, 1500);
        return () => clearTimeout(timer);
    }, [optimisticWorkStatusById]);

    const recordedWorkIds = useMemo(() => {
        const work = canopyData?.progress_sync?.work;
        const buckets = [
            ...(Array.isArray(work?.in_progress) ? work.in_progress : []),
            ...(Array.isArray(work?.pending) ? work.pending : []),
            ...(Array.isArray(work?.done_recent) ? work.done_recent : []),
        ];
        const ids = buckets
            .map((row) => String((row as { id?: string } | undefined)?.id || "").trim())
            .filter((id) => Boolean(id));
        return new Set(ids);
    }, [canopyData]);

    const visibleWorkNodes = useMemo(() => {
        if (!recordedOnly) return workNodes;
        if (recordedWorkIds.size === 0) return [];
        return workNodes.filter((row) => recordedWorkIds.has(String(row.id || "").trim()));
    }, [recordedOnly, workNodes, recordedWorkIds]);

    useEffect(() => {
        if (typeof window === "undefined") return;
        try {
            window.localStorage.setItem(RECORDED_ONLY_STORAGE_KEY, recordedOnly ? "1" : "0");
        } catch {
            // ignore storage errors
        }
    }, [recordedOnly]);

    const filteredWorkNodes = useMemo(() => {
        if (!selectedModule || selectedModule === ROOT_MODULE_ID) return visibleWorkNodes;
        return visibleWorkNodes.filter((row) => String(row.module || "") === selectedModule);
    }, [visibleWorkNodes, selectedModule]);

    const visibleModuleOverview = useMemo(() => {
        const rows = Array.isArray(canopyData?.module_overview) ? canopyData.module_overview : [];
        if (!recordedOnly) return rows;
        const moduleSet = new Set(
            visibleWorkNodes.map((row) => String(row.module || "").trim()).filter((row) => Boolean(row)),
        );
        if (moduleSet.size === 0) return [];
        return rows.filter((row) => moduleSet.has(String(row.module || "").trim()));
    }, [canopyData, recordedOnly, visibleWorkNodes]);

    useEffect(() => {
        if (selectedModule === ROOT_MODULE_ID) return;
        if (!filteredWorkNodes.length) {
            setSelectedWorkId("");
            return;
        }
        if (!filteredWorkNodes.some((row) => row.id === selectedWorkId)) {
            setSelectedWorkId(filteredWorkNodes[0].id);
        }
    }, [filteredWorkNodes, selectedWorkId, selectedModule]);

    useEffect(() => {
        if (selectedModule === ROOT_MODULE_ID) return;
        if (!visibleModuleOverview.length) {
            setSelectedModule("");
            return;
        }
        if (!visibleModuleOverview.some((row) => row.module === selectedModule)) {
            setSelectedModule(String(visibleModuleOverview[0]?.module || ""));
        }
    }, [visibleModuleOverview, selectedModule]);

    useEffect(() => {
        if (!activeFocus) {
            if (selectedWorkId) {
                setActiveFocus({ kind: "work", id: selectedWorkId });
                return;
            }
            if (selectedClusterId) {
                setActiveFocus({ kind: "question", id: selectedClusterId });
                return;
            }
            if (selectedModule) {
                setActiveFocus({ kind: "module", id: selectedModule });
            }
        }
    }, [activeFocus, selectedWorkId, selectedClusterId, selectedModule]);

    useEffect(() => {
        if (!activeFocus || activeFocus.kind !== "work") return;
        if (!selectedWorkId) return;
        const stillExists = filteredWorkNodes.some((row) => row.id === activeFocus.id);
        if (!stillExists) {
            setActiveFocus({ kind: "work", id: selectedWorkId });
        }
    }, [activeFocus, selectedWorkId, filteredWorkNodes]);

    const selectedWork = useMemo(
        () => filteredWorkNodes.find((row) => row.id === selectedWorkId) || null,
        [filteredWorkNodes, selectedWorkId],
    );

    const questionQueue = useMemo(() => (Array.isArray(canopyData?.question_queue) ? canopyData.question_queue : []), [canopyData]);

    const visibleQuestionQueue = useMemo(() => {
        if (!recordedOnly) return questionQueue;
        const moduleSet = new Set(
            visibleWorkNodes.map((row) => String(row.module || "").trim()).filter((row) => Boolean(row)),
        );
        if (moduleSet.size === 0) return [];
        return questionQueue.filter((row) => {
            const linkedNodes = Array.isArray(row.linked_nodes) ? row.linked_nodes : [];
            if (linkedNodes.length === 0) return moduleSet.has("forest");
            return linkedNodes.some((node) => moduleSet.has(inferModuleFromNode(String(node))));
        });
    }, [recordedOnly, questionQueue, visibleWorkNodes]);

    useEffect(() => {
        if (selectedModule === ROOT_MODULE_ID) return;
        if (!visibleQuestionQueue.length) {
            setSelectedClusterId("");
            return;
        }
        if (!visibleQuestionQueue.some((row) => row.cluster_id === selectedClusterId)) {
            setSelectedClusterId(String(visibleQuestionQueue[0]?.cluster_id || ""));
        }
    }, [visibleQuestionQueue, selectedClusterId, selectedModule]);

    useEffect(() => {
        if (!activeFocus || activeFocus.kind !== "question") return;
        if (!selectedClusterId) return;
        const stillExists = visibleQuestionQueue.some((row) => row.cluster_id === activeFocus.id);
        if (!stillExists) {
            setActiveFocus({ kind: "question", id: selectedClusterId });
        }
    }, [activeFocus, selectedClusterId, visibleQuestionQueue]);

    const selectedQuestion = useMemo(
        () => visibleQuestionQueue.find((row) => row.cluster_id === selectedClusterId) || null,
        [visibleQuestionQueue, selectedClusterId],
    );

    const selectedBitmapCandidate = useMemo(
        () => (bitmapSummary?.candidates || []).find((row) => row.id === selectedBitmapCandidateId) || null,
        [bitmapSummary, selectedBitmapCandidateId],
    );

    const loadBitmapTimeline = useCallback(async (candidateId: string) => {
        const id = String(candidateId || "").trim();
        if (!id) {
            setSelectedBitmapTimeline([]);
            return;
        }
        setBitmapTimelineLoading(true);
        try {
            const endpoint = apiUrl(`/mind/bitmap/candidates/${encodeURIComponent(id)}/timeline?days=30&limit=50`);
            const response = await fetch(endpoint);
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(parseErrorText(errText));
            }
            const body = (await response.json()) as BitmapCandidateTimelineResponse;
            setSelectedBitmapTimeline(Array.isArray(body.events) ? body.events : []);
        } catch (error) {
            setSelectedBitmapTimeline([]);
            setMode("error");
            setMessage(`bitmap timeline 조회 실패: ${String(error)}`);
        } finally {
            setBitmapTimelineLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadBitmapTimeline(selectedBitmapCandidateId);
    }, [selectedBitmapCandidateId, loadBitmapTimeline]);

    const bitmapHighlightModuleId = useMemo(() => {
        if (!selectedBitmapCandidateId) return null;
        const hasForest = (canopyData?.module_overview || []).some((row) => row.module === "forest");
        return hasForest ? "forest" : null;
    }, [selectedBitmapCandidateId, canopyData]);

    const linkedQuestions = useMemo(() => {
        if (!selectedWork?.linked_node) return [];
        const linked = String(selectedWork.linked_node).trim().toLowerCase();
        if (!linked) return [];
        return visibleQuestionQueue.filter((row) =>
            (Array.isArray(row.linked_nodes) ? row.linked_nodes : []).some(
                (node) => String(node).trim().toLowerCase() === linked,
            ),
        );
    }, [selectedWork, visibleQuestionQueue]);

    const selectedModuleMeta = useMemo(
        () =>
            selectedModule === ROOT_MODULE_ID
                ? null
                : visibleModuleOverview.find((row) => row.module === selectedModule) || null,
        [visibleModuleOverview, selectedModule],
    );

    const moduleBottlenecks = useMemo(() => {
        if (!selectedModule) return [];
        return visibleWorkNodes
            .filter((row) => row.module === selectedModule && (row.status === "BLOCKED" || row.status === "FAILED"))
            .sort((left, right) => {
                const leftRisk = Number(left.linked_risk || 0);
                const rightRisk = Number(right.linked_risk || 0);
                if (rightRisk !== leftRisk) return rightRisk - leftRisk;
                return Number(right.priority_score || 0) - Number(left.priority_score || 0);
            })
            .slice(0, 5);
    }, [visibleWorkNodes, selectedModule]);

    const totalWorkNodesCount = workNodes.length;
    const visibleWorkNodesCount = visibleWorkNodes.length;
    const hiddenWorkNodesCount = Math.max(0, totalWorkNodesCount - visibleWorkNodesCount);
    const recordedOnlyHiddenSamples = useMemo(() => {
        if (!recordedOnly) return [];
        const hidden = workNodes.filter((row) => !recordedWorkIds.has(row.id));
        return hidden
            .map((row) => toSingleLine(row.label || row.id || "", 28))
            .filter((label) => Boolean(label))
            .slice(0, 2);
    }, [recordedOnly, workNodes, recordedWorkIds]);
    const recordedOnlyHint = useMemo(() => {
        if (!recordedOnly) return "";
        if (totalWorkNodesCount === 0) return "표시할 작업이 없습니다.";
        if (recordedWorkIds.size === 0) return "기록 기준이 아직 없습니다. 동기화/기록 후 다시 확인하세요.";
        if (hiddenWorkNodesCount > 0) {
            const sampleText =
                recordedOnlyHiddenSamples.length > 0 ? ` (예: ${recordedOnlyHiddenSamples.join(", ")})` : "";
            return `기록 기준에 없는 작업 ${hiddenWorkNodesCount}건 숨김${sampleText}`;
        }
        return "모든 작업이 기록 기준과 일치합니다.";
    }, [recordedOnly, totalWorkNodesCount, recordedWorkIds, hiddenWorkNodesCount, recordedOnlyHiddenSamples]);

    const syncDigestLine = useMemo(() => {
        const sync = canopyData?.sync_status;
        if (!sync) return "동기화 상태: 확인 필요";
        const label = String(sync.label || "미동기화").trim();
        const step = String(sync.step || "none").trim();
        const recorded = Number(sync.recorded || 0);
        const skipped = Number(sync.skipped || 0);
        const mismatch = Number(sync.mismatch_count || 0);
        const parts = [`동기화 ${label}`, step !== "none" ? `단계 ${step}` : "", `기록 ${recorded}`, `스킵 ${skipped}`];
        if (mismatch > 0) parts.push(`불일치 ${mismatch}`);
        return toSingleLine(parts.filter((row) => Boolean(row)).join(" · "), 100);
    }, [canopyData]);
    const rootMode = selectedModule === ROOT_MODULE_ID;

    const selectModule = useCallback((moduleId: string) => {
        setSelectedModule(moduleId);
        setActiveFocus({ kind: "module", id: moduleId });
    }, []);

    const selectRoot = useCallback(() => {
        setSelectedModule(ROOT_MODULE_ID);
        setSelectedWorkId("");
        setSelectedClusterId("");
        setActiveFocus({ kind: "module", id: ROOT_MODULE_ID });
    }, []);

    const selectProject = useCallback((value: string) => {
        const next = String(value || "").trim() || DEFAULT_PROJECT;
        setProjectName(next);
        setSnapshotDiff(null);
        previousCanopyRef.current = null;
        setSelectedPhaseStepFilter("");
        setSelectedModule(ROOT_MODULE_ID);
        setSelectedWorkId("");
        setSelectedClusterId("");
        setActiveFocus({ kind: "module", id: ROOT_MODULE_ID });
    }, []);

    const createProject = useCallback(
        async (name: string) => {
            const project = String(name || "").trim();
            if (!project) {
                setMode("error");
                setMessage("프로젝트 이름을 입력해주세요.");
                return;
            }
            setCreateProjectBusy(true);
            setMode("running");
            setMessage(`프로젝트 생성 중: ${project}`);
            try {
                const response = await fetch(apiUrl("/forest/projects/init"), {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ project_name: project }),
                });
                if (!response.ok) {
                    throw new Error(parseErrorText(await response.text()));
                }
                const initBody = (await response.json()) as {
                    bootstrap?: { recorded?: number; skipped?: number; error?: string };
                    inventory_seed?: {
                        status?: string;
                        created_count?: number;
                        skipped_existing?: number;
                        skipped_limit?: number;
                        error?: string;
                    };
                    status_sync?: { status?: string };
                };
                const bootstrapRecorded = Number(initBody?.bootstrap?.recorded || 0);
                const inventoryCreated = Number(initBody?.inventory_seed?.created_count || 0);
                const inventorySkipped = Number(initBody?.inventory_seed?.skipped_existing || 0);
                const inventoryStatus = String(initBody?.inventory_seed?.status || "").trim() || "unknown";
                const syncStatus = String(initBody?.status_sync?.status || "").trim() || "skipped";
                const bootstrapError = String(initBody?.bootstrap?.error || "").trim();
                const inventoryError = String(initBody?.inventory_seed?.error || "").trim();
                const initError = [bootstrapError, inventoryError].filter((row) => row.length > 0).join(" | ");
                setProjectInitStatusByName((prev) => ({
                    ...prev,
                    [project]: {
                        bootstrapRecorded,
                        inventorySeedStatus: inventoryStatus,
                        inventoryCreated,
                        inventorySkipped,
                        syncStatus,
                        error: initError,
                        at: new Date().toISOString(),
                    },
                }));
                await loadProjectOptions();
                selectProject(project);
                setMode("success");
                setMessage(
                    `프로젝트 생성/전환 완료: ${project} · bootstrap ${bootstrapRecorded}건 · seed ${inventoryCreated}건 (중복 ${inventorySkipped}) · sync ${syncStatus}`,
                );
                pushSyncHistory(
                    `프로젝트 생성 완료: ${project} · seed=${inventoryCreated} (${inventoryStatus})`,
                    "ok",
                );
            } catch (error) {
                setMode("error");
                setMessage(`프로젝트 생성 실패: ${String(error)}`);
                pushSyncHistory(`프로젝트 생성 실패: ${String(error)}`, "error");
            } finally {
                setCreateProjectBusy(false);
            }
        },
        [loadProjectOptions, selectProject, pushSyncHistory],
    );

    const archiveProject = useCallback(
        async (name: string) => {
            const target = String(name || "").trim();
            if (!target || target === DEFAULT_PROJECT) return;
            setProjectActionBusyName(target);
            try {
                const response = await fetch(
                    apiUrl(`/forest/projects/${encodeURIComponent(target)}/archive`),
                    { method: "POST" },
                );
                if (!response.ok) {
                    throw new Error(parseErrorText(await response.text()));
                }
                if (target === String(projectName || "").trim()) {
                    selectProject(DEFAULT_PROJECT);
                }
                await loadProjectOptions();
                pushSyncHistory(`프로젝트 보관 완료: ${target}`, "ok");
            } catch (error) {
                const errorText = error instanceof Error ? error.message : String(error);
                setMode("error");
                setMessage(`프로젝트 보관 실패: ${errorText}`);
                pushSyncHistory(`프로젝트 보관 실패: ${errorText}`, "error");
            } finally {
                setProjectActionBusyName("");
            }
        },
        [loadProjectOptions, projectName, pushSyncHistory, selectProject],
    );

    const unarchiveProject = useCallback(
        async (name: string) => {
            const target = String(name || "").trim();
            if (!target) return;
            setProjectActionBusyName(target);
            try {
                const response = await fetch(
                    apiUrl(`/forest/projects/${encodeURIComponent(target)}/unarchive`),
                    { method: "POST" },
                );
                if (!response.ok) {
                    throw new Error(parseErrorText(await response.text()));
                }
                await loadProjectOptions();
                pushSyncHistory(`프로젝트 복구 완료: ${target}`, "ok");
            } catch (error) {
                const errorText = error instanceof Error ? error.message : String(error);
                setMode("error");
                setMessage(`프로젝트 복구 실패: ${errorText}`);
                pushSyncHistory(`프로젝트 복구 실패: ${errorText}`, "error");
            } finally {
                setProjectActionBusyName("");
            }
        },
        [loadProjectOptions, pushSyncHistory],
    );

    const seedWorkFromInventory = useCallback(async () => {
        setInventorySeedBusy(true);
        setMode("running");
        setMessage("시스템 인벤토리 기반 작업 생성 중...");
        try {
            const response = await fetch(
                apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/work/seed-from-inventory`),
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ limit: 8 }),
                },
            );
            if (!response.ok) {
                throw new Error(parseErrorText(await response.text()));
            }
            const body = (await response.json()) as {
                created_count?: number;
                skipped_existing?: number;
                skipped_limit?: number;
            };
            const created = Number(body.created_count || 0);
            const skipped = Number(body.skipped_existing || 0);
            const skippedLimit = Number(body.skipped_limit || 0);
            await refreshCanopy();
            if (created > 0) {
                setMode("success");
                setMessage(`인벤토리 작업 ${created}건 생성 완료 (중복 ${skipped}, 제한 ${skippedLimit})`);
                pushSyncHistory(`인벤토리 작업 생성 ${created}건`, "ok");
            } else {
                setMode("success");
                setMessage(`생성할 인벤토리 작업 없음 (중복 ${skipped}, 제한 ${skippedLimit})`);
                pushSyncHistory("인벤토리 작업 생성 없음", "info");
            }
        } catch (error) {
            const errorText = error instanceof Error ? error.message : String(error);
            setMode("error");
            setMessage(`인벤토리 작업 생성 실패: ${errorText}`);
            pushSyncHistory(`인벤토리 작업 생성 실패: ${errorText}`, "error");
        } finally {
            setInventorySeedBusy(false);
        }
    }, [projectName, refreshCanopy, pushSyncHistory]);

    const selectWork = useCallback((workId: string) => {
        setSelectedWorkId(workId);
        setActiveFocus({ kind: "work", id: workId });
    }, []);

    const selectQuestion = useCallback((clusterId: string) => {
        setSelectedClusterId(clusterId);
        setActiveFocus({ kind: "question", id: clusterId });
    }, []);

    const createWorkFromCluster = useCallback(
        async (clusterId?: string) => {
            const preferredId = String(clusterId || selectedQuestion?.cluster_id || selectedClusterId || "").trim();
            const targetQuestion =
                (preferredId
                    ? questionQueue.find((row) => String(row.cluster_id || "").trim() === preferredId) || null
                    : null) || selectedQuestion;
            if (!targetQuestion) {
                setMode("error");
                setMessage("워크 패키지로 만들 질문 클러스터를 먼저 선택해주세요.");
                return;
            }
            setSelectedClusterId(String(targetQuestion.cluster_id || ""));
            setActiveFocus({ kind: "question", id: String(targetQuestion.cluster_id || "") });
            setMode("running");
            setMessage(`질문 ${targetQuestion.cluster_id} 기반 워크 패키지 생성 중...`);
            const endpoint = apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/work/generate`);
            const issue = targetQuestion.description?.trim()
                ? targetQuestion.description
                : `${targetQuestion.cluster_id} 검토`;
            try {
                const response = await fetch(endpoint, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        kind: "REVIEW",
                        context_tag: "work",
                        linked_node: targetQuestion.linked_nodes?.[0] || null,
                        title: `Q:${targetQuestion.cluster_id}`,
                        issue,
                        required: [
                            "질문 클러스터 원인 정리",
                            "설계 범위/성공조건 명시",
                            "return_payload.json 보고",
                        ],
                        deliverables: ["work/package_auto.md", "return_payload.json"],
                    }),
                });
                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error(parseErrorText(errText));
                }
                const body = (await response.json()) as { work_package_id?: string };
                const workId = String(body.work_package_id || "").trim();
                await refreshCanopy();
                if (workId) {
                    setSelectedModule(inferModuleFromNode(targetQuestion.linked_nodes?.[0]));
                    setSelectedWorkId(workId);
                    setActiveFocus({ kind: "work", id: workId });
                    setMessage(`워크 패키지 생성 완료: ${workId}`);
                    pushSyncHistory(`질문 기반 작업 생성 완료: ${workId}`, "ok");
                } else {
                    setMessage("워크 패키지 생성 완료");
                    pushSyncHistory("질문 기반 작업 생성 완료", "ok");
                }
                setMode("success");
            } catch (error) {
                setMode("error");
                setMessage(`워크 패키지 생성 실패: ${String(error)}`);
                pushSyncHistory(`질문 기반 작업 생성 실패: ${String(error)}`, "error");
            }
        },
        [projectName, pushSyncHistory, questionQueue, refreshCanopy, selectedClusterId, selectedQuestion],
    );

    const createWorkFromQuestion = useCallback(async () => {
        await createWorkFromCluster();
    }, [createWorkFromCluster]);

    const acknowledgeWorkPackage = useCallback(
        async (workId?: string) => {
            const id = String(workId || selectedWorkId || "").trim();
            if (!id) {
                setMode("error");
                setMessage("ACK할 작업을 먼저 선택해주세요.");
                return;
            }
            setWorkActionBusyId(id);
            setOptimisticWorkStatusById((prev) => ({
                ...prev,
                [id]: { status: "IN_PROGRESS", expiresAt: Date.now() + OPTIMISTIC_WORK_STATUS_TTL_MS },
            }));
            setMode("running");
            setMessage(`작업 ACK 처리 중: ${id}`);
            pushSyncHistory(`작업 ACK 처리 중: ${id}`, "info");
            try {
                const response = await fetch(apiUrl(`/work/packages/${encodeURIComponent(id)}/ack`), { method: "POST" });
                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error(parseErrorText(errText));
                }
                await refreshCanopy();
                setSelectedWorkId(id);
                setActiveFocus({ kind: "work", id });
                setMode("success");
                setMessage(`작업 ACK 완료: ${id}`);
                pushSyncHistory(`작업 ACK 완료: ${id}`, "ok");
            } catch (error) {
                setOptimisticWorkStatusById((prev) => {
                    if (!prev[id]) return prev;
                    const next = { ...prev };
                    delete next[id];
                    return next;
                });
                setMode("error");
                setMessage(`작업 ACK 실패: ${String(error)}`);
                pushSyncHistory(`작업 ACK 실패: ${id}`, "error");
            } finally {
                setWorkActionBusyId("");
            }
        },
        [selectedWorkId, refreshCanopy],
    );

    const completeWorkPackage = useCallback(
        async (workId?: string) => {
            const id = String(workId || selectedWorkId || "").trim();
            if (!id) {
                setMode("error");
                setMessage("완료 처리할 작업을 먼저 선택해주세요.");
                return;
            }
            setWorkActionBusyId(id);
            setOptimisticWorkStatusById((prev) => ({
                ...prev,
                [id]: { status: "DONE", expiresAt: Date.now() + OPTIMISTIC_WORK_STATUS_TTL_MS },
            }));
            setMode("running");
            setMessage(`작업 완료 처리 중: ${id}`);
            pushSyncHistory(`작업 완료 처리 중: ${id}`, "info");
            try {
                const response = await fetch(apiUrl(`/work/packages/${encodeURIComponent(id)}/complete`), { method: "POST" });
                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error(parseErrorText(errText));
                }
                await refreshCanopy();
                setSelectedWorkId(id);
                setActiveFocus({ kind: "work", id });
                setMode("success");
                setMessage(`작업 완료 처리 완료: ${id}`);
                pushSyncHistory(`작업 완료 처리 완료: ${id}`, "ok");
            } catch (error) {
                setOptimisticWorkStatusById((prev) => {
                    if (!prev[id]) return prev;
                    const next = { ...prev };
                    delete next[id];
                    return next;
                });
                setMode("error");
                setMessage(`작업 완료 처리 실패: ${String(error)}`);
                pushSyncHistory(`작업 완료 처리 실패: ${id}`, "error");
            } finally {
                setWorkActionBusyId("");
            }
        },
        [selectedWorkId, refreshCanopy],
    );

    const selectBitmapCandidate = useCallback((candidateId: string) => {
        const nextId = String(candidateId || "").trim();
        setSelectedBitmapCandidateId(nextId);
        if (!nextId) return;
        setBitmapEventHighlight(null);
    }, []);

    const adoptBitmapCandidate = useCallback(
        async (candidateId: string, episodeId: string) => {
            if (!candidateId || !episodeId) {
                setMode("error");
                setMessage("채택에 필요한 candidate/episode 정보가 없습니다.");
                return;
            }
            setBitmapActionBusyId(candidateId);
            setMode("running");
            setMessage(`bitmap 후보 채택 중: ${candidateId}`);
            try {
                const response = await fetch(apiUrl("/adopt"), {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ candidate_id: candidateId, episode_id: episodeId }),
                });
                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error(parseErrorText(errText));
                }
                setEventFilter("all");
                setCanopyOffset(0);
                setSelectedBitmapCandidateId(candidateId);
                setBitmapEventHighlight({ eventType: "ADOPT", candidateId });
                await Promise.all([loadBitmapSummary(), loadBitmapAudit(), loadCanopyData({ eventFilter: "all" })]);
                await loadBitmapTimeline(candidateId);
                setMode("success");
                setMessage(`bitmap 후보 채택 완료: ${candidateId}`);
            } catch (error) {
                const errorText = error instanceof Error ? error.message : String(error);
                setMode("error");
                setMessage(`bitmap 채택 실패: ${errorText}`);
            } finally {
                setBitmapActionBusyId("");
            }
        },
        [loadBitmapSummary, loadBitmapAudit, loadCanopyData, loadBitmapTimeline],
    );

    const rejectBitmapCandidate = useCallback(
        async (candidateId: string, episodeId: string, reason?: string) => {
            if (!candidateId || !episodeId) {
                setMode("error");
                setMessage("거절에 필요한 candidate/episode 정보가 없습니다.");
                return;
            }
            setBitmapActionBusyId(candidateId);
            setMode("running");
            setMessage(`bitmap 후보 거절 중: ${candidateId}`);
            try {
                const response = await fetch(apiUrl("/reject"), {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        candidate_id: candidateId,
                        episode_id: episodeId,
                        reason: String(reason || "").trim() || "manual_reject_ui",
                    }),
                });
                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error(parseErrorText(errText));
                }
                setEventFilter("all");
                setCanopyOffset(0);
                setSelectedBitmapCandidateId(candidateId);
                setBitmapEventHighlight({ eventType: "REJECT", candidateId });
                await Promise.all([loadBitmapSummary(), loadBitmapAudit(), loadCanopyData({ eventFilter: "all" })]);
                await loadBitmapTimeline(candidateId);
                setMode("success");
                setMessage(`bitmap 후보 거절 완료: ${candidateId}`);
            } catch (error) {
                const errorText = error instanceof Error ? error.message : String(error);
                setMode("error");
                setMessage(`bitmap 거절 실패: ${errorText}`);
            } finally {
                setBitmapActionBusyId("");
            }
        },
        [loadBitmapSummary, loadBitmapAudit, loadCanopyData, loadBitmapTimeline],
    );

    return {
        projectName,
        projectOptions,
        includeArchivedProjects,
        setIncludeArchivedProjects,
        setProjectName,
        selectProject,
        createProjectBusy,
        createProject,
        projectActionBusyName,
        archiveProject,
        unarchiveProject,
        inventorySeedBusy,
        seedWorkFromInventory,
        projectInitStatusByName,
        selectedPhaseStepFilter,
        setSelectedPhaseStepFilter,
        riskThreshold,
        setRiskThreshold,
        moduleSort,
        setModuleSort,
        eventFilter,
        setEventFilter,
        serverModuleFilter,
        setServerModuleFilter,
        canopyView,
        setCanopyView,
        recordedOnly,
        setRecordedOnly,
        totalWorkNodesCount,
        visibleWorkNodesCount,
        hiddenWorkNodesCount,
        recordedOnlyHint,
        recordedOnlyHiddenSamples,
        syncDigestLine,
        snapshotDiff,
        syncHistory,
        runtimeContract,
        lastRoadmapRecordSummary,
        handoffSummary,
        applePlan,
        applePlanBusy,
        syncApplePlan,
        editorSourceOptions,
        selectedEditorSourcePath,
        setSelectedEditorSourcePath,
        sourcePath,
        setSourcePath,
        target,
        setTarget,
        change,
        setChange,
        scope,
        setScope,
        mode,
        modeColor,
        message,
        pageStatusText,
        canGoPrevPage,
        canGoNextPage,
        goPrevPage,
        goNextPage,
        dashboardSrc,
        canopyData,
        bitmapSummary,
        bitmapAudit,
        bitmapActionBusyId,
        workActionBusyId,
        bitmapEventHighlight,
        bitmapHighlightModuleId,
        selectedBitmapCandidateId,
        selectedBitmapCandidate,
        selectedBitmapTimeline,
        bitmapTimelineLoading,
        selectedModule,
        rootMode,
        selectRoot,
        selectedWorkId,
        selectedClusterId,
        visibleModuleOverview,
        visibleQuestionQueue,
        visibleWorkNodes,
        filteredWorkNodes,
        questionQueue: visibleQuestionQueue,
        selectedModuleMeta,
        selectedWork,
        linkedQuestions,
        selectedQuestion,
        moduleBottlenecks,
        roadmapRecordBusy,
        specReviewBusy,
        refreshCanopy,
        recordRoadmapSnapshot,
        specIndex,
        selectedSpecPath,
        selectedSpecContent,
        specLoading,
        specUploadBusy,
        selectSpecPath: setSelectedSpecPath,
        requestSpecReview,
        setSpecStatus,
        uploadSpecByFile,
        todoItems,
        todoBusy,
        upsertTodo,
        setTodoStatus,
        syncProjectStatus,
        runAnalyzeByPath,
        refreshEditorSourceOptions: loadEditorSourceOptions,
        runAnalyzeSelectedEditorFile,
        runAnalyzeTodayEditorFile,
        runAnalyzeByUpload,
        selectModule,
        selectWork,
        selectQuestion,
        createWorkFromQuestion,
        createWorkFromCluster,
        acknowledgeWorkPackage,
        completeWorkPackage,
        selectBitmapCandidate,
        adoptBitmapCandidate,
        rejectBitmapCandidate,
    };
}
