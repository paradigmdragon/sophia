import { type ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";

import { API_BASE, apiUrl } from "../../lib/apiBase";
import { noteService } from "../../lib/noteService";
import type {
    AnalyzeMode,
    CanopyDataResponse,
    EventFilter,
    ModuleOverview,
    ModuleSort,
    QuestionRow,
    WorkNode,
} from "./types";
import { inferModuleFromNode, parseErrorText } from "./utils";

type FocusKind = "module" | "work" | "question";
const DEFAULT_PROJECT = "sophia";
const DEFAULT_CANOPY_LIMIT = 50;

export type ReportController = {
    projectName: string;
    setProjectName: (value: string) => void;
    riskThreshold: string;
    setRiskThreshold: (value: string) => void;
    moduleSort: ModuleSort;
    setModuleSort: (value: ModuleSort) => void;
    eventFilter: EventFilter;
    setEventFilter: (value: EventFilter) => void;
    sourcePath: string;
    setSourcePath: (value: string) => void;
    target: string;
    setTarget: (value: string) => void;
    change: string;
    setChange: (value: string) => void;
    scope: string;
    setScope: (value: string) => void;
    modeColor: string;
    message: string;
    dashboardSrc: string;
    canopyData: CanopyDataResponse | null;
    selectedModule: string;
    selectedWorkId: string;
    selectedClusterId: string;
    filteredWorkNodes: WorkNode[];
    questionQueue: QuestionRow[];
    selectedModuleMeta: ModuleOverview | null;
    selectedWork: WorkNode | null;
    linkedQuestions: QuestionRow[];
    selectedQuestion: QuestionRow | null;
    moduleBottlenecks: WorkNode[];
    refreshCanopy: () => Promise<void>;
    runAnalyzeByPath: () => Promise<void>;
    runAnalyzeTodayEditorFile: () => Promise<void>;
    runAnalyzeByUpload: (event: ChangeEvent<HTMLInputElement>) => Promise<void>;
    selectModule: (moduleId: string) => void;
    selectWork: (workId: string) => void;
    selectQuestion: (clusterId: string) => void;
    createWorkFromQuestion: () => Promise<void>;
};

export function useReportController(): ReportController {
    const [projectName, setProjectName] = useState(DEFAULT_PROJECT);
    const [riskThreshold, setRiskThreshold] = useState("0.8");
    const [moduleSort, setModuleSort] = useState<ModuleSort>("importance");
    const [eventFilter, setEventFilter] = useState<EventFilter>("all");
    const [sourcePath, setSourcePath] = useState("");
    const [target, setTarget] = useState("spec-module");
    const [change, setChange] = useState("문서 변경 검토");
    const [scope, setScope] = useState("");
    const [mode, setMode] = useState<AnalyzeMode>("idle");
    const [message, setMessage] = useState("현황판 준비됨");
    const [refreshSeed, setRefreshSeed] = useState(Date.now());

    const [canopyData, setCanopyData] = useState<CanopyDataResponse | null>(null);
    const [canopyOffset, setCanopyOffset] = useState(0);
    const [selectedModule, setSelectedModule] = useState<string>("");
    const [selectedWorkId, setSelectedWorkId] = useState<string>("");
    const [selectedClusterId, setSelectedClusterId] = useState<string>("");
    const [activeFocus, setActiveFocus] = useState<{ kind: FocusKind; id: string } | null>(null);

    const highlightKey = useMemo(() => {
        if (!activeFocus?.id) return "";
        if (activeFocus.kind === "module") return `module:${activeFocus.id}`;
        if (activeFocus.kind === "work") return `work:${activeFocus.id}`;
        return `question:${activeFocus.id}`;
    }, [activeFocus]);

    const dashboardSrc = useMemo(() => {
        const base = `${API_BASE}/dashboard/?t=${refreshSeed}`;
        if (!highlightKey) return base;
        return `${base}&highlight=${encodeURIComponent(highlightKey)}`;
    }, [refreshSeed, highlightKey]);

    const query = useMemo(() => {
        const threshold = Number.parseFloat(riskThreshold);
        const queryParts: string[] = [];
        if (Number.isFinite(threshold)) queryParts.push(`risk_threshold=${threshold}`);
        queryParts.push(`module_sort=${moduleSort}`);
        queryParts.push(`event_filter=${eventFilter}`);
        queryParts.push(`limit=${DEFAULT_CANOPY_LIMIT}`);
        queryParts.push(`offset=${canopyOffset}`);
        queryParts.push("module=all");
        return queryParts.length > 0 ? `?${queryParts.join("&")}` : "";
    }, [riskThreshold, moduleSort, eventFilter, canopyOffset]);

    useEffect(() => {
        setCanopyOffset(0);
    }, [projectName, riskThreshold, moduleSort, eventFilter]);

    const loadCanopyData = useCallback(async () => {
        const endpoint = apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/canopy/data${query}`);
        const response = await fetch(endpoint);
        if (!response.ok) {
            const errText = await response.text();
            throw new Error(parseErrorText(errText));
        }
        const body = (await response.json()) as CanopyDataResponse;
        setCanopyData(body);

        const modules = Array.isArray(body.module_overview) ? body.module_overview : [];
        const defaultModule = modules[0]?.module ?? "";
        setSelectedModule((prev) => {
            if (prev && modules.some((row) => row.module === prev)) return prev;
            return defaultModule;
        });

        const questions = Array.isArray(body.question_queue) ? body.question_queue : [];
        const defaultCluster = questions[0]?.cluster_id ?? "";
        setSelectedClusterId((prev) => {
            if (prev && questions.some((row) => row.cluster_id === prev)) return prev;
            return defaultCluster;
        });
    }, [projectName, query]);

    const refreshCanopy = useCallback(async () => {
        setMode("running");
        setMessage("현황판 내보내기 실행 중...");
        const endpoint = apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/canopy/export${query}`);
        try {
            const response = await fetch(endpoint, { method: "POST" });
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(parseErrorText(errText));
            }
            setRefreshSeed(Date.now());
            await loadCanopyData();
            setMode("success");
            setMessage("현황판 갱신 완료");
        } catch (error) {
            setMode("error");
            setMessage(`현황판 갱신 실패: ${String(error)}`);
        }
    }, [projectName, query, loadCanopyData]);

    useEffect(() => {
        void refreshCanopy();
    }, [refreshCanopy]);

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

    const runAnalyzeTodayEditorFile = useCallback(async () => {
        const todayPath = noteService.getTodayFileName();
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

    const workNodes = useMemo(() => {
        const rows = Array.isArray(canopyData?.nodes) ? canopyData.nodes : [];
        return rows.filter((row): row is WorkNode => row?.type === "work") as WorkNode[];
    }, [canopyData]);

    const filteredWorkNodes = useMemo(() => {
        if (!selectedModule) return workNodes;
        return workNodes.filter((row) => String(row.module || "") === selectedModule);
    }, [workNodes, selectedModule]);

    useEffect(() => {
        if (!filteredWorkNodes.length) {
            setSelectedWorkId("");
            return;
        }
        if (!filteredWorkNodes.some((row) => row.id === selectedWorkId)) {
            setSelectedWorkId(filteredWorkNodes[0].id);
        }
    }, [filteredWorkNodes, selectedWorkId]);

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

    useEffect(() => {
        if (!activeFocus || activeFocus.kind !== "question") return;
        if (!selectedClusterId) return;
        const stillExists = questionQueue.some((row) => row.cluster_id === activeFocus.id);
        if (!stillExists) {
            setActiveFocus({ kind: "question", id: selectedClusterId });
        }
    }, [activeFocus, selectedClusterId, questionQueue]);

    const selectedQuestion = useMemo(
        () => questionQueue.find((row) => row.cluster_id === selectedClusterId) || null,
        [questionQueue, selectedClusterId],
    );

    const linkedQuestions = useMemo(() => {
        if (!selectedWork?.linked_node) return [];
        const linked = String(selectedWork.linked_node).trim().toLowerCase();
        if (!linked) return [];
        return questionQueue.filter((row) =>
            (Array.isArray(row.linked_nodes) ? row.linked_nodes : []).some(
                (node) => String(node).trim().toLowerCase() === linked,
            ),
        );
    }, [selectedWork, questionQueue]);

    const selectedModuleMeta = useMemo(
        () => (Array.isArray(canopyData?.module_overview) ? canopyData.module_overview.find((row) => row.module === selectedModule) || null : null),
        [canopyData, selectedModule],
    );

    const moduleBottlenecks = useMemo(() => {
        if (!selectedModule) return [];
        return workNodes
            .filter((row) => row.module === selectedModule && (row.status === "BLOCKED" || row.status === "FAILED"))
            .sort((left, right) => {
                const leftRisk = Number(left.linked_risk || 0);
                const rightRisk = Number(right.linked_risk || 0);
                if (rightRisk !== leftRisk) return rightRisk - leftRisk;
                return Number(right.priority_score || 0) - Number(left.priority_score || 0);
            })
            .slice(0, 5);
    }, [workNodes, selectedModule]);

    const selectModule = useCallback((moduleId: string) => {
        setSelectedModule(moduleId);
        setActiveFocus({ kind: "module", id: moduleId });
    }, []);

    const selectWork = useCallback((workId: string) => {
        setSelectedWorkId(workId);
        setActiveFocus({ kind: "work", id: workId });
    }, []);

    const selectQuestion = useCallback((clusterId: string) => {
        setSelectedClusterId(clusterId);
        setActiveFocus({ kind: "question", id: clusterId });
    }, []);

    const createWorkFromQuestion = useCallback(async () => {
        if (!selectedQuestion) {
            setMode("error");
            setMessage("워크 패키지로 만들 질문 클러스터를 먼저 선택해주세요.");
            return;
        }
        setMode("running");
        setMessage(`질문 ${selectedQuestion.cluster_id} 기반 워크 패키지 생성 중...`);
        const endpoint = apiUrl(`/forest/projects/${encodeURIComponent(projectName)}/work/generate`);
        const issue = selectedQuestion.description?.trim()
            ? selectedQuestion.description
            : `${selectedQuestion.cluster_id} 검토`;
        try {
            const response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    kind: "REVIEW",
                    context_tag: "work",
                    linked_node: selectedQuestion.linked_nodes?.[0] || null,
                    title: `Q:${selectedQuestion.cluster_id}`,
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
                setSelectedModule(inferModuleFromNode(selectedQuestion.linked_nodes?.[0]));
                setSelectedWorkId(workId);
                setActiveFocus({ kind: "work", id: workId });
                setMessage(`워크 패키지 생성 완료: ${workId}`);
            } else {
                setMessage("워크 패키지 생성 완료");
            }
            setMode("success");
        } catch (error) {
            setMode("error");
            setMessage(`워크 패키지 생성 실패: ${String(error)}`);
        }
    }, [selectedQuestion, projectName, refreshCanopy]);

    return {
        projectName,
        setProjectName,
        riskThreshold,
        setRiskThreshold,
        moduleSort,
        setModuleSort,
        eventFilter,
        setEventFilter,
        sourcePath,
        setSourcePath,
        target,
        setTarget,
        change,
        setChange,
        scope,
        setScope,
        modeColor,
        message,
        dashboardSrc,
        canopyData,
        selectedModule,
        selectedWorkId,
        selectedClusterId,
        filteredWorkNodes,
        questionQueue,
        selectedModuleMeta,
        selectedWork,
        linkedQuestions,
        selectedQuestion,
        moduleBottlenecks,
        refreshCanopy,
        runAnalyzeByPath,
        runAnalyzeTodayEditorFile,
        runAnalyzeByUpload,
        selectModule,
        selectWork,
        selectQuestion,
        createWorkFromQuestion,
    };
}
