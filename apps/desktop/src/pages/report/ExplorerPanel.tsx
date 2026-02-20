import { type ChangeEvent, useMemo, useState } from "react";

import type { ForestProjectInfo, ModuleOverview, QuestionRow, WorkNode } from "./types";
import { inferModuleFromNode } from "./utils";

type ExplorerPanelProps = {
    projectName: string;
    projectOptions: ForestProjectInfo[];
    includeArchivedProjects: boolean;
    onToggleIncludeArchived: (value: boolean) => void;
    onSelectProject: (projectName: string) => void;
    onCreateProject: (projectName: string) => Promise<void>;
    createProjectBusy: boolean;
    projectActionBusyName: string;
    onArchiveProject: (projectName: string) => Promise<void>;
    onUnarchiveProject: (projectName: string) => Promise<void>;
    inventorySeedBusy: boolean;
    onSeedWorkFromInventory: () => Promise<void>;
    projectInitStatusByName: Record<
        string,
        {
            bootstrapRecorded: number;
            inventorySeedStatus: string;
            inventoryCreated: number;
            inventorySkipped: number;
            syncStatus: string;
            error: string;
            at: string;
        }
    >;
    selectedPhaseStepFilter: string;
    onSelectPhaseStep: (phaseStep: string) => void;
    moduleOverview: ModuleOverview[];
    selectedModule: string;
    onSelectModule: (moduleId: string) => void;
    filteredWorkNodes: WorkNode[];
    selectedWorkId: string;
    onSelectWork: (workId: string) => void;
    questionQueue: QuestionRow[];
    selectedClusterId: string;
    onSelectQuestion: (clusterId: string) => void;
    editorSourceOptions: Array<{ label: string; path: string }>;
    selectedEditorSourcePath: string;
    onSelectEditorSourcePath: (path: string) => void;
    onRefreshEditorSourceOptions: () => Promise<void>;
    onAnalyzeSelectedEditorFile: () => Promise<void>;
    onAnalyzeByUpload: (event: ChangeEvent<HTMLInputElement>) => Promise<void>;
    sourceActionMode: "idle" | "running" | "success" | "error";
    sourceActionMessage: string;
    rootMode: boolean;
    onSelectRoot: () => void;
};

const WORK_STATUS_RANK: Record<string, number> = {
    FAILED: 0,
    BLOCKED: 1,
    IN_PROGRESS: 2,
    READY: 3,
    DONE: 4,
};

function moduleState(module: ModuleOverview): "danger" | "warning" | "progress" | "ok" | "idle" {
    if (Number(module.max_risk_score || 0) >= 0.9) return "danger";
    if (Number(module.max_risk_score || 0) >= 0.8 || Number(module.pending_questions || 0) > 0) return "warning";
    if (Number(module.progress_pct || 0) >= 95 && Number(module.work_total || 0) > 0) return "ok";
    if (Number(module.work_total || 0) > 0) return "progress";
    return "idle";
}

function stateTone(state: ReturnType<typeof moduleState>): string {
    if (state === "danger") return "bg-rose-500";
    if (state === "warning") return "bg-amber-400";
    if (state === "ok") return "bg-emerald-400";
    if (state === "progress") return "bg-cyan-400";
    return "bg-gray-500";
}

function moduleBadge(state: ReturnType<typeof moduleState>): { label: string; tone: string } {
    if (state === "danger") return { label: "문제", tone: "border-rose-400/50 bg-rose-900/20 text-rose-100" };
    if (state === "ok" || state === "idle") {
        return { label: "정상", tone: "border-emerald-400/50 bg-emerald-900/20 text-emerald-100" };
    }
    return { label: "개발중", tone: "border-cyan-400/50 bg-cyan-900/20 text-cyan-100" };
}

function projectState(project: ForestProjectInfo): "danger" | "warning" | "progress" | "ok" | "idle" {
    const blocked = Number(project.blocked_count || 0);
    const unverified = Number(project.unverified_count || 0);
    const progress = Number(project.progress_pct || 0);
    if (blocked > 0) return "danger";
    if (unverified > 0) return "warning";
    if (progress >= 100) return "ok";
    if (progress > 0) return "progress";
    return "idle";
}

function workBadge(status: string): { label: string; tone: string } {
    const normalized = String(status || "").toUpperCase();
    if (normalized === "FAILED" || normalized === "BLOCKED") {
        return { label: "문제", tone: "border-rose-400/50 bg-rose-900/20 text-rose-100" };
    }
    if (normalized === "DONE") {
        return { label: "정상", tone: "border-emerald-400/50 bg-emerald-900/20 text-emerald-100" };
    }
    return { label: "개발중", tone: "border-cyan-400/50 bg-cyan-900/20 text-cyan-100" };
}

function isActionableQuestion(status: string): boolean {
    const normalized = String(status || "").toLowerCase();
    return normalized === "collecting" || normalized === "ready_to_ask" || normalized === "pending";
}

function questionBadge(riskScore: number, status: string): { label: string; tone: string } {
    const normalized = String(status || "").toLowerCase();
    if (normalized === "resolved") {
        return { label: "정상", tone: "border-emerald-400/50 bg-emerald-900/20 text-emerald-100" };
    }
    if (normalized === "acknowledged" || normalized === "read") {
        return { label: "확인", tone: "border-amber-400/50 bg-amber-900/20 text-amber-100" };
    }
    if (riskScore >= 0.8) return { label: "문제", tone: "border-rose-400/50 bg-rose-900/20 text-rose-100" };
    return { label: "개발중", tone: "border-cyan-400/50 bg-cyan-900/20 text-cyan-100" };
}

function workPriorityBadge(priorityScore: number): { label: string; tone: string } {
    const score = Number(priorityScore || 0);
    if (score >= 90) return { label: "P0", tone: "border-rose-400/50 bg-rose-900/20 text-rose-100" };
    if (score >= 60) return { label: "P1", tone: "border-amber-400/50 bg-amber-900/20 text-amber-100" };
    return { label: "P2", tone: "border-cyan-400/50 bg-cyan-900/20 text-cyan-100" };
}

function questionPriorityBadge(riskScore: number): { label: string; tone: string } {
    const risk = Number(riskScore || 0);
    if (risk >= 0.9) return { label: "P0", tone: "border-rose-400/50 bg-rose-900/20 text-rose-100" };
    if (risk >= 0.8) return { label: "P1", tone: "border-amber-400/50 bg-amber-900/20 text-amber-100" };
    return { label: "P2", tone: "border-cyan-400/50 bg-cyan-900/20 text-cyan-100" };
}

function questionBelongsToModule(question: QuestionRow, moduleId: string): boolean {
    const linkedNodes = Array.isArray(question.linked_nodes) ? question.linked_nodes : [];
    if (linkedNodes.length === 0) return moduleId === "forest";
    return linkedNodes.some((node) => inferModuleFromNode(String(node)) === moduleId);
}

function questionDisplayLabel(row: QuestionRow): string {
    const desc = String(row.description || "").trim();
    if (desc.length > 0) {
        return desc.length > 24 ? `${desc.slice(0, 23)}…` : desc;
    }
    const fallback = String(row.cluster_id || "").trim();
    return fallback.length > 24 ? `${fallback.slice(0, 23)}…` : fallback;
}

function riskLevelText(score: number): string {
    const value = Number(score || 0);
    if (value >= 0.9) return "위험 높음";
    if (value >= 0.8) return "위험";
    if (value >= 0.6) return "주의";
    return "관찰";
}

function compactModuleMetrics(module: ModuleOverview): string {
    const total = Number(module.work_total || 0);
    if (total <= 0) return "개발 준비";
    const devProgress = Number(module.dev_progress_pct || 0);
    if (devProgress <= 0) {
        const operational = Number(module.progress_pct || 0);
        if (operational > 0) return `개발 ${operational}%`;
    }
    return `개발 ${devProgress}%`;
}

function projectInitRecoveryGuide(errorText: string): string {
    const normalized = String(errorText || "").toLowerCase();
    if (!normalized) return "";
    if (normalized.includes("roadmap") && normalized.includes("api")) {
        return "복구 가이드: 서버 계약이 구버전입니다. API 서버를 최신 코드로 재시작한 뒤 현황판 새로고침을 실행하세요.";
    }
    if (normalized.includes("openapi") || normalized.includes("404")) {
        return "복구 가이드: 라우트가 누락되었습니다. 서버 재시작 후 `/openapi.json`에 forest 라우트가 있는지 확인하세요.";
    }
    if (normalized.includes("timeout") || normalized.includes("network")) {
        return "복구 가이드: 네트워크/서버 응답 지연입니다. 잠시 후 재시도하고 실패가 반복되면 API 로그를 확인하세요.";
    }
    return "복구 가이드: 초기화 실패 원인을 확인한 뒤 프로젝트를 다시 생성하거나 현황판 동기화를 다시 실행하세요.";
}

export function ExplorerPanel({
    projectName,
    projectOptions,
    includeArchivedProjects,
    onToggleIncludeArchived,
    onSelectProject,
    onCreateProject,
    createProjectBusy,
    projectActionBusyName,
    onArchiveProject,
    onUnarchiveProject,
    inventorySeedBusy,
    onSeedWorkFromInventory,
    projectInitStatusByName,
    selectedPhaseStepFilter,
    onSelectPhaseStep,
    moduleOverview,
    selectedModule,
    onSelectModule,
    filteredWorkNodes,
    selectedWorkId,
    onSelectWork,
    questionQueue,
    selectedClusterId,
    onSelectQuestion,
    editorSourceOptions,
    selectedEditorSourcePath,
    onSelectEditorSourcePath,
    onRefreshEditorSourceOptions,
    onAnalyzeSelectedEditorFile,
    onAnalyzeByUpload,
    sourceActionMode,
    sourceActionMessage,
    rootMode,
    onSelectRoot,
}: ExplorerPanelProps) {
    const [quickTab, setQuickTab] = useState<"risk" | "blocked" | "plan">("plan");
    const [sourceAddOpen, setSourceAddOpen] = useState(false);
    const [initErrorOpenProject, setInitErrorOpenProject] = useState("");
    const [newProjectName, setNewProjectName] = useState("");

    const projectDisplayName = useMemo(() => {
        const normalized = String(projectName || "").trim().toLowerCase();
        if (normalized === "sophia") return "소피아숲";
        if (!normalized) return "프로젝트";
        return String(projectName).trim();
    }, [projectName]);
    const projectRows = useMemo(() => {
        if (projectOptions.length > 0) {
            const rows = [...projectOptions];
            rows.sort((left, right) => {
                const leftName = String(left.project_name || "").trim();
                const rightName = String(right.project_name || "").trim();
                if (leftName === "sophia" && rightName !== "sophia") return -1;
                if (rightName === "sophia" && leftName !== "sophia") return 1;
                const leftSeverity = projectState(left) === "danger" ? 3 : projectState(left) === "warning" ? 2 : 1;
                const rightSeverity = projectState(right) === "danger" ? 3 : projectState(right) === "warning" ? 2 : 1;
                if (rightSeverity !== leftSeverity) return rightSeverity - leftSeverity;
                if (Number(right.progress_pct || 0) !== Number(left.progress_pct || 0)) {
                    return Number(right.progress_pct || 0) - Number(left.progress_pct || 0);
                }
                return leftName.localeCompare(rightName);
            });
            return rows;
        }
        return [
            {
                project_name: projectName || "sophia",
                progress_pct: 0,
                remaining_work: 0,
                blocked_count: 0,
                unverified_count: 0,
                updated_at: "",
            },
        ];
    }, [projectOptions, projectName]);

    const modules = useMemo(
        () =>
            [...moduleOverview].sort((left, right) => {
                if (right.importance !== left.importance) return right.importance - left.importance;
                if (right.max_risk_score !== left.max_risk_score) return right.max_risk_score - left.max_risk_score;
                return right.progress_pct - left.progress_pct;
            }),
        [moduleOverview],
    );
    const moduleRows = modules.filter((row) => {
        const moduleId = String(row.module || "").trim().toLowerCase();
        const label = String(row.label || "").trim().toLowerCase();
        if (moduleId === "forest") return false;
        if (moduleId === String(projectName || "").trim().toLowerCase()) return false;
        if (label === String(projectDisplayName || "").trim().toLowerCase()) return false;
        return true;
    });

    const selectedModuleQuestions = useMemo(
        () =>
            [...questionQueue]
                .filter((row) => questionBelongsToModule(row, selectedModule))
                .sort((left, right) => {
                    const leftActive = isActionableQuestion(left.status) ? 1 : 0;
                    const rightActive = isActionableQuestion(right.status) ? 1 : 0;
                    if (rightActive !== leftActive) return rightActive - leftActive;
                    if (right.risk_score !== left.risk_score) return right.risk_score - left.risk_score;
                    return right.hit_count - left.hit_count;
                }),
        [questionQueue, selectedModule],
    );

    const selectedModuleWorks = useMemo(
        () =>
            [...filteredWorkNodes].sort((left, right) => {
                const leftRank = WORK_STATUS_RANK[String(left.status || "").toUpperCase()] ?? 99;
                const rightRank = WORK_STATUS_RANK[String(right.status || "").toUpperCase()] ?? 99;
                if (leftRank !== rightRank) return leftRank - rightRank;
                return Number(right.priority_score || 0) - Number(left.priority_score || 0);
            }),
        [filteredWorkNodes],
    );

    const totalWork = modules.reduce((acc, row) => acc + Number(row.work_total || 0), 0);
    const totalDone = modules.reduce((acc, row) => acc + Number(row.done || 0), 0);
    const highRiskCount = questionQueue.filter(
        (row) => isActionableQuestion(row.status) && Number(row.risk_score || 0) >= 0.8,
    ).length;
    const selectedProjectMeta = useMemo(
        () => projectRows.find((row) => String(row.project_name).trim() === String(projectName).trim()) || null,
        [projectRows, projectName],
    );
    const rootProgressPct = selectedProjectMeta
        ? Number(selectedProjectMeta.progress_pct || 0)
        : totalWork > 0
          ? Math.max(0, Math.min(100, Math.round((totalDone / totalWork) * 100)))
          : 0;
    const rootState: "danger" | "warning" | "progress" | "ok" | "idle" =
        Number(selectedProjectMeta?.blocked_count || 0) > 0 || highRiskCount > 0
            ? "warning"
            : rootProgressPct >= 100
              ? "ok"
              : totalWork > 0
                ? "progress"
                : "idle";
    const blockedTop = useMemo(
        () =>
            [...filteredWorkNodes]
                .filter((row) => {
                    const status = String(row.status || "").toUpperCase();
                    return status === "BLOCKED" || status === "FAILED";
                })
                .sort((left, right) => Number(right.priority_score || 0) - Number(left.priority_score || 0))
                .slice(0, 4),
        [filteredWorkNodes],
    );
    const planTop = useMemo(
        () =>
            [...filteredWorkNodes]
                .filter((row) => String(row.status || "").toUpperCase() === "READY")
                .sort((left, right) => Number(right.priority_score || 0) - Number(left.priority_score || 0))
                .slice(0, 4),
        [filteredWorkNodes],
    );
    const riskTop = useMemo(
        () =>
            [...questionQueue]
                .filter((row) => isActionableQuestion(row.status) && Number(row.risk_score || 0) >= 0.8)
                .sort((left, right) => right.risk_score - left.risk_score)
                .slice(0, 4),
        [questionQueue],
    );

    return (
        <div className="border-r border-[#263246] p-3 h-full min-h-0 overflow-hidden flex flex-col gap-3">
            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3 basis-[70%] min-h-0 flex flex-col">
                <p className="text-xs text-gray-400 mb-2">Finder Tree · 프로젝트 폴더</p>
                <div className="space-y-1 flex-1 min-h-0 overflow-auto">
                    <div className="rounded border border-[#334155] bg-[#0b1220]">
                        <div className="px-2 py-1.5 border-b border-[#334155]">
                            <button onClick={onSelectRoot} className="w-full text-left">
                                <div className="flex items-center justify-between gap-2">
                                    <p className="text-gray-100 text-xs truncate">
                                        <span className="mr-1">📁</span>소피아
                                    </p>
                                    <div className="flex items-center gap-1">
                                        {rootMode ? (
                                            <span className="inline-flex rounded border px-1.5 py-0.5 text-[10px] border-cyan-400/60 bg-cyan-900/25 text-cyan-100">
                                                선택
                                            </span>
                                        ) : null}
                                        <span className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] ${moduleBadge(rootState).tone}`}>
                                            대분류
                                        </span>
                                    </div>
                                </div>
                            </button>
                        </div>
                        <div className="px-2 py-1.5 border-b border-[#334155] bg-[#0d1527]">
                            <div className="flex items-center justify-between gap-2">
                                <p className="text-gray-200 text-[11px] truncate">
                                    └ 📂 프로젝트 ({projectRows.length})
                                </p>
                                <button
                                    onClick={() => onToggleIncludeArchived(!includeArchivedProjects)}
                                    className={`rounded border px-1.5 py-0.5 text-[10px] ${
                                        includeArchivedProjects
                                            ? "border-amber-400/50 bg-amber-900/20 text-amber-100"
                                            : "border-[#334155] bg-[#111827] text-gray-400"
                                    }`}
                                >
                                    {includeArchivedProjects ? "보관 포함" : "보관 숨김"}
                                </button>
                            </div>
                        </div>
                        {selectedPhaseStepFilter ? (
                            <div className="px-2 py-1 border-b border-[#334155] bg-violet-950/20 flex items-center justify-between gap-2">
                                <p className="text-[10px] text-violet-100 truncate">phase 필터: {selectedPhaseStepFilter}</p>
                                <button
                                    onClick={() => onSelectPhaseStep(selectedPhaseStepFilter)}
                                    className="rounded border border-violet-400/50 px-1.5 py-0.5 text-[10px] text-violet-100 hover:bg-violet-900/35"
                                >
                                    해제
                                </button>
                            </div>
                        ) : null}
                        <div className="px-2 py-1.5 border-b border-[#334155] bg-[#0f172a]">
                            <button onClick={onSelectRoot} className="w-full text-left">
                                <div className="flex items-center justify-between gap-2">
                                    <p className="text-gray-100 text-[11px] truncate">
                                        &nbsp;&nbsp;└ 📁 {projectDisplayName}
                                    </p>
                                    <div className="flex items-center gap-1">
                                        {rootMode ? (
                                            <span className="inline-flex rounded border px-1.5 py-0.5 text-[10px] border-cyan-400/60 bg-cyan-900/25 text-cyan-100">
                                                문서/계획
                                            </span>
                                        ) : null}
                                        <span className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] ${moduleBadge(rootState).tone}`}>
                                            {moduleBadge(rootState).label}
                                        </span>
                                    </div>
                                </div>
                                <p className="mt-1 text-[10px] text-gray-300">
                                    &nbsp;&nbsp;&nbsp;&nbsp;잔여 {Number(selectedProjectMeta?.remaining_work || 0)} · phase{" "}
                                    {String(selectedProjectMeta?.current_phase_step || "-")}
                                </p>
                            </button>
                        </div>
                        <div className="px-2 py-2 border-b border-[#334155] bg-[#0f172a] space-y-1">
                            {projectRows.map((project) => {
                                const name = String(project.project_name || "").trim();
                                const selected = name === String(projectName || "").trim();
                                const state = projectState(project);
                                const badge = moduleBadge(state);
                                const archived = Boolean(project.archived);
                                const isBusy = projectActionBusyName === name;
                                const initStatus = projectInitStatusByName[name];
                                const hasInitError = Boolean(String(initStatus?.error || "").trim());
                                const phaseStep = String(project.current_phase_step || "").trim();
                                const phaseStepSelected = Boolean(phaseStep && phaseStep === selectedPhaseStepFilter);
                                return (
                                    <div
                                        key={name}
                                        className={`w-full rounded border px-2 py-1 text-left text-[11px] ${
                                            selected
                                                ? "border-cyan-400 bg-cyan-900/20 text-cyan-100"
                                                : "border-[#334155] bg-[#0b1220] text-gray-200"
                                        }`}
                                    >
                                        <button
                                            onClick={() => onSelectProject(name)}
                                            className="w-full text-left"
                                        >
                                            <div className="flex items-center justify-between gap-2">
                                                <span className="truncate">
                                                    &nbsp;&nbsp;&nbsp;&nbsp;└ {name === "sophia" ? "소피아숲" : name}
                                                </span>
                                                <div className="flex items-center gap-1">
                                                    {archived ? (
                                                        <span className="inline-flex rounded border px-1.5 py-0.5 text-[10px] border-amber-400/50 bg-amber-900/20 text-amber-100">
                                                            보관
                                                        </span>
                                                    ) : null}
                                                    <span className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] ${badge.tone}`}>
                                                        {badge.label}
                                                    </span>
                                                    {phaseStep ? (
                                                        <button
                                                            onClick={(event) => {
                                                                event.stopPropagation();
                                                                onSelectPhaseStep(phaseStep);
                                                            }}
                                                            className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] ${
                                                                phaseStepSelected
                                                                    ? "border-violet-300 bg-violet-800/35 text-violet-50"
                                                                    : "border-violet-400/40 bg-violet-900/20 text-violet-100 hover:bg-violet-900/35"
                                                            }`}
                                                            title="클릭하면 해당 phase_step 기준으로 구현 계획이 필터링됩니다."
                                                        >
                                                            phase {phaseStep}
                                                        </button>
                                                    ) : null}
                                                </div>
                                            </div>
                                        </button>
                                        {initStatus ? (
                                            <div className="mt-1 flex items-center gap-1 flex-wrap">
                                                <span className="inline-flex rounded border px-1.5 py-0.5 text-[10px] border-cyan-400/40 bg-cyan-900/15 text-cyan-100">
                                                    초기시드 {Number(initStatus.inventoryCreated || 0)}건
                                                </span>
                                                <span className="inline-flex rounded border px-1.5 py-0.5 text-[10px] border-[#334155] bg-[#111827] text-gray-300">
                                                    sync {String(initStatus.syncStatus || "unknown")}
                                                </span>
                                                {hasInitError ? (
                                                    <button
                                                        onClick={() =>
                                                            setInitErrorOpenProject((prev) => (prev === name ? "" : name))
                                                        }
                                                        className="inline-flex rounded border px-1.5 py-0.5 text-[10px] border-rose-400/50 bg-rose-900/20 text-rose-100 hover:bg-rose-900/30"
                                                    >
                                                        초기화 경고
                                                    </button>
                                                ) : null}
                                            </div>
                                        ) : null}
                                        {hasInitError && initErrorOpenProject === name ? (
                                            <div className="mt-1 rounded border border-rose-400/40 bg-rose-950/20 px-2 py-1 text-[10px] text-rose-100 whitespace-pre-wrap break-words space-y-1">
                                                <p>{String(initStatus?.error || "").trim()}</p>
                                                <p className="text-rose-200/90">
                                                    {projectInitRecoveryGuide(String(initStatus?.error || "").trim())}
                                                </p>
                                            </div>
                                        ) : null}
                                        {name !== "sophia" ? (
                                            <div className="mt-1 flex justify-end">
                                                <button
                                                    disabled={isBusy}
                                                    onClick={() =>
                                                        archived
                                                            ? void onUnarchiveProject(name)
                                                            : void onArchiveProject(name)
                                                    }
                                                    className={`rounded border px-1.5 py-0.5 text-[10px] ${
                                                        isBusy
                                                            ? "border-[#334155] bg-[#111827] text-gray-500"
                                                            : archived
                                                              ? "border-emerald-400/50 bg-emerald-900/20 text-emerald-100"
                                                              : "border-amber-400/50 bg-amber-900/20 text-amber-100"
                                                    }`}
                                                >
                                                    {isBusy ? "처리중" : archived ? "복구" : "보관"}
                                                </button>
                                            </div>
                                        ) : null}
                                    </div>
                                );
                            })}
                            <div className="pt-1 space-y-1.5">
                                <div className="rounded border border-[#334155] bg-[#0b1220] p-1.5">
                                    <p className="text-[10px] text-gray-400 mb-1">프로젝트 관리</p>
                                    <div className="grid grid-cols-[1fr_auto] gap-1">
                                        <input
                                            value={newProjectName}
                                            onChange={(event) => setNewProjectName(event.target.value)}
                                            placeholder="새 프로젝트 이름"
                                            className="rounded border border-[#334155] bg-[#111827] px-2 py-1 text-[11px] text-gray-200"
                                        />
                                        <button
                                            onClick={() => {
                                                const next = newProjectName.trim();
                                                if (!next) return;
                                                void onCreateProject(next).then(() => setNewProjectName(""));
                                            }}
                                            disabled={createProjectBusy}
                                            className={`rounded border px-2 py-1 text-[11px] ${
                                                createProjectBusy
                                                    ? "border-[#334155] bg-[#0f172a] text-gray-500"
                                                    : "border-cyan-400/60 bg-cyan-900/20 text-cyan-100 hover:bg-cyan-900/30"
                                            }`}
                                        >
                                            {createProjectBusy ? "생성중" : "새 프로젝트"}
                                        </button>
                                    </div>
                                    <button
                                        onClick={() => void onSeedWorkFromInventory()}
                                        disabled={inventorySeedBusy}
                                        className={`w-full mt-1 rounded border px-2 py-1 text-[11px] ${
                                            inventorySeedBusy
                                                ? "border-[#334155] bg-[#0f172a] text-gray-500"
                                                : "border-emerald-400/60 bg-emerald-900/20 text-emerald-100 hover:bg-emerald-900/30"
                                        }`}
                                    >
                                        {inventorySeedBusy ? "작업 생성중..." : "구현항목 자동 생성"}
                                    </button>
                                </div>

                                <div className="rounded border border-[#334155] bg-[#0b1220] p-1.5">
                                    <button
                                        onClick={() => setSourceAddOpen((prev) => !prev)}
                                        className="w-full rounded border border-cyan-400/40 bg-cyan-900/15 px-2 py-1 text-left text-[11px] text-cyan-100 hover:bg-cyan-900/25"
                                    >
                                        + 소스자료 추가
                                    </button>
                                    {sourceAddOpen ? (
                                        <div className="mt-1.5 space-y-1.5">
                                            <select
                                                value={selectedEditorSourcePath}
                                                onChange={(event) => onSelectEditorSourcePath(event.target.value)}
                                                className="w-full rounded border border-[#334155] bg-[#111827] px-2 py-1 text-[11px] text-gray-200"
                                            >
                                                <option value="">에디터 파일 선택</option>
                                                {editorSourceOptions.map((row) => (
                                                    <option key={row.path} value={row.path}>
                                                        {row.label}
                                                    </option>
                                                ))}
                                            </select>
                                            <button
                                                onClick={() => void onRefreshEditorSourceOptions()}
                                                className="w-full rounded border border-[#334155] bg-[#111827] px-2 py-1 text-[11px] text-gray-200 hover:bg-[#1f2937]"
                                            >
                                                파일 목록 새로고침
                                            </button>
                                            <button
                                                onClick={() => void onAnalyzeSelectedEditorFile()}
                                                disabled={!selectedEditorSourcePath}
                                                className={`w-full rounded border px-2 py-1 text-[11px] ${
                                                    selectedEditorSourcePath
                                                        ? "border-cyan-400/60 bg-cyan-900/20 text-cyan-100 hover:bg-cyan-900/30"
                                                        : "border-[#334155] bg-[#111827] text-gray-500"
                                                }`}
                                            >
                                                선택 파일 적용
                                            </button>
                                            <label className="block cursor-pointer rounded border border-[#334155] bg-[#111827] px-2 py-1 text-[11px] text-gray-200 hover:bg-[#1f2937]">
                                                파일 업로드 적용
                                                <input
                                                    type="file"
                                                    accept=".md,.markdown,.txt"
                                                    className="hidden"
                                                    onChange={(event) => void onAnalyzeByUpload(event)}
                                                />
                                            </label>
                                            <div
                                                className={`rounded border px-2 py-1 text-[10px] ${
                                                    sourceActionMode === "error"
                                                        ? "border-rose-400/40 bg-rose-900/20 text-rose-100"
                                                        : sourceActionMode === "success"
                                                          ? "border-emerald-400/40 bg-emerald-900/20 text-emerald-100"
                                                          : sourceActionMode === "running"
                                                            ? "border-amber-400/40 bg-amber-900/20 text-amber-100"
                                                            : "border-[#334155] bg-[#111827] text-gray-400"
                                                }`}
                                            >
                                                {sourceActionMode === "idle"
                                                    ? "선택 파일 또는 업로드 파일로 SonE 분석을 실행합니다."
                                                    : sourceActionMessage}
                                            </div>
                                        </div>
                                    ) : null}
                                </div>
                            </div>
                        </div>
                    </div>
                    {moduleRows.map((module, index) => {
                        const selected =
                            selectedModule.length > 0 ? selectedModule === module.module : index === 0;
                        const state = moduleState(module);
                        return (
                            <div key={module.module} className="rounded border border-[#334155] bg-[#0b1220]">
                                <button
                                    onClick={() => onSelectModule(module.module)}
                                    className={`w-full text-left px-2 py-1.5 text-xs ${
                                        selected ? "bg-cyan-900/25 border-l-2 border-cyan-300" : ""
                                    }`}
                                >
                                    <div className="flex items-center justify-between gap-2">
                                        <p className="text-gray-100 truncate">
                                            <span className="mr-1">&nbsp;&nbsp;·</span>
                                            {module.label}
                                            <span className={`inline-block w-2 h-2 rounded-full ml-2 align-middle ${stateTone(state)}`} />
                                        </p>
                                        <span className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] ${moduleBadge(state).tone}`}>
                                            {moduleBadge(state).label}
                                        </span>
                                    </div>
                                    <p className="mt-1 text-[10px] text-gray-300 truncate">
                                        {compactModuleMetrics(module)}
                                    </p>
                                </button>
                                {selected ? (
                                    <div className="px-2 pb-2 space-y-2">
                                        <div className="space-y-1">
                                            {selectedModuleWorks.slice(0, 5).map((work) => (
                                                <button
                                                    key={work.id}
                                                    onClick={() => onSelectWork(work.id)}
                                                    className={`w-full text-left rounded border px-2 py-1 text-[11px] ${
                                                        selectedWorkId === work.id
                                                            ? "border-cyan-400 bg-cyan-900/20"
                                                            : "border-[#334155] bg-[#0f172a]"
                                                    }`}
                                                >
                                                    <div className="flex items-center justify-between gap-2">
                                                        <p className="text-gray-100 truncate">· {work.label}</p>
                                                        <div className="flex items-center gap-1">
                                                            <span
                                                                className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] ${
                                                                    workPriorityBadge(Number(work.priority_score || 0)).tone
                                                                }`}
                                                            >
                                                                {workPriorityBadge(Number(work.priority_score || 0)).label}
                                                            </span>
                                                            <span
                                                                className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] ${
                                                                    workBadge(work.status).tone
                                                                }`}
                                                            >
                                                                {workBadge(work.status).label}
                                                            </span>
                                                        </div>
                                                    </div>
                                                </button>
                                            ))}
                                            {selectedModuleWorks.length === 0 && (
                                                <p className="text-[11px] text-gray-600">작업 없음</p>
                                            )}
                                        </div>
                                        {selectedModuleQuestions[0] ? (
                                            <button
                                                onClick={() => onSelectQuestion(selectedModuleQuestions[0].cluster_id)}
                                                className={`w-full text-left rounded border px-2 py-1 text-[11px] ${
                                                    selectedClusterId === selectedModuleQuestions[0].cluster_id
                                                        ? "border-cyan-400 bg-cyan-900/20"
                                                        : "border-[#334155] bg-[#0f172a]"
                                                }`}
                                            >
                                                질문 확인: {questionDisplayLabel(selectedModuleQuestions[0])}
                                            </button>
                                        ) : null}
                                    </div>
                                ) : null}
                            </div>
                        );
                    })}
                    {moduleRows.length === 0 ? (
                        <div className="rounded border border-[#334155] bg-[#0b1220] px-2 py-2 text-[11px] text-gray-500">
                            표시할 하위 모듈이 없습니다.
                        </div>
                    ) : null}
                </div>
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3 basis-[30%] min-h-0 flex flex-col">
                <div className="flex items-center justify-between mb-2">
                    <p className="text-xs text-gray-400">빠른 접근</p>
                    <span className="text-[11px] text-gray-500">
                        모듈 {modules.length} · 작업 {totalWork} · 위험 {highRiskCount}
                    </span>
                </div>
                <div className="mb-2 grid grid-cols-3 gap-1">
                    <button
                        onClick={() => setQuickTab("risk")}
                        className={`rounded border px-1.5 py-1 text-[11px] ${
                            quickTab === "risk"
                                ? "border-rose-400/60 bg-rose-900/25 text-rose-100"
                                : "border-[#334155] bg-[#0b1220] text-gray-300"
                        }`}
                    >
                        위험 ({riskTop.length})
                    </button>
                    <button
                        onClick={() => setQuickTab("blocked")}
                        className={`rounded border px-1.5 py-1 text-[11px] ${
                            quickTab === "blocked"
                                ? "border-amber-400/60 bg-amber-900/25 text-amber-100"
                                : "border-[#334155] bg-[#0b1220] text-gray-300"
                        }`}
                    >
                        문제 ({blockedTop.length})
                    </button>
                    <button
                        onClick={() => setQuickTab("plan")}
                        className={`rounded border px-1.5 py-1 text-[11px] ${
                            quickTab === "plan"
                                ? "border-cyan-400/60 bg-cyan-900/25 text-cyan-100"
                                : "border-[#334155] bg-[#0b1220] text-gray-300"
                        }`}
                    >
                        계획 ({planTop.length})
                    </button>
                </div>
                <div className="space-y-1 flex-1 min-h-0 overflow-auto">
                    {quickTab === "risk" &&
                        riskTop.map((row) => (
                            <button
                                key={row.cluster_id}
                                onClick={() => onSelectQuestion(row.cluster_id)}
                                className={`w-full text-left rounded border px-2 py-1 text-xs ${
                                    selectedClusterId === row.cluster_id
                                        ? "border-cyan-400 bg-cyan-900/20"
                                        : "border-[#334155] bg-[#0b1220]"
                                }`}
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <p className="text-gray-100 truncate">{questionDisplayLabel(row)}</p>
                                    <div className="flex items-center gap-1">
                                        <span
                                            className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] ${
                                                questionPriorityBadge(Number(row.risk_score || 0)).tone
                                            }`}
                                        >
                                            {questionPriorityBadge(Number(row.risk_score || 0)).label}
                                        </span>
                                        <span
                                            className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] ${
                                                questionBadge(Number(row.risk_score || 0), row.status).tone
                                            }`}
                                        >
                                            {questionBadge(Number(row.risk_score || 0), row.status).label}
                                        </span>
                                    </div>
                                </div>
                                <p className="text-[11px] text-rose-200">
                                    {riskLevelText(row.risk_score)} ({row.risk_score.toFixed(2)})
                                </p>
                            </button>
                        ))}
                    {quickTab === "blocked" &&
                        blockedTop.map((row) => (
                            <button
                                key={row.id}
                                onClick={() => onSelectWork(row.id)}
                                className={`w-full text-left rounded border px-2 py-1 text-xs ${
                                    selectedWorkId === row.id
                                        ? "border-cyan-400 bg-cyan-900/20"
                                        : "border-[#334155] bg-[#0b1220]"
                                }`}
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <p className="text-gray-100 truncate">{row.label || row.id}</p>
                                    <div className="flex items-center gap-1">
                                        <span
                                            className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] ${
                                                workPriorityBadge(Number(row.priority_score || 0)).tone
                                            }`}
                                        >
                                            {workPriorityBadge(Number(row.priority_score || 0)).label}
                                        </span>
                                        <span className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] ${workBadge(row.status).tone}`}>
                                            {workBadge(row.status).label}
                                        </span>
                                    </div>
                                </div>
                            </button>
                        ))}
                    {quickTab === "plan" &&
                        planTop.map((row) => (
                            <button
                                key={row.id}
                                onClick={() => onSelectWork(row.id)}
                                className={`w-full text-left rounded border px-2 py-1 text-xs ${
                                    selectedWorkId === row.id
                                        ? "border-cyan-400 bg-cyan-900/20"
                                        : "border-[#334155] bg-[#0b1220]"
                                }`}
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <p className="text-gray-100 truncate">{row.label || row.id}</p>
                                    <div className="flex items-center gap-1">
                                        <span
                                            className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] ${
                                                workPriorityBadge(Number(row.priority_score || 0)).tone
                                            }`}
                                        >
                                            {workPriorityBadge(Number(row.priority_score || 0)).label}
                                        </span>
                                        <span className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] ${workBadge(row.status).tone}`}>
                                            {workBadge(row.status).label}
                                        </span>
                                    </div>
                                </div>
                            </button>
                        ))}
                    {quickTab === "risk" && riskTop.length === 0 && (
                        <div className="rounded border border-[#334155] bg-[#0b1220] px-2 py-1 text-xs text-gray-400">
                            고위험 질문 없음
                        </div>
                    )}
                    {quickTab === "blocked" && blockedTop.length === 0 && (
                        <div className="rounded border border-[#334155] bg-[#0b1220] px-2 py-1 text-xs text-gray-400">
                            문제 작업 없음
                        </div>
                    )}
                    {quickTab === "plan" && planTop.length === 0 && (
                        <div className="rounded border border-[#334155] bg-[#0b1220] px-2 py-1 text-xs text-gray-400">
                            계획 작업 없음
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
