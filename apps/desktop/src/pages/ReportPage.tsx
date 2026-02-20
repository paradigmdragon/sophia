import { useEffect, useState } from "react";

import { ControlPanel } from "./report/ControlPanel";
import { DetailPanel } from "./report/DetailPanel";
import { ExplorerPanel } from "./report/ExplorerPanel";
import { useReportController } from "./report/useReportController";

export function ReportPage() {
    const controller = useReportController();
    const [showTools, setShowTools] = useState(false);
    const [overviewArmUntil, setOverviewArmUntil] = useState<number>(0);
    const overviewUnlocked = controller.canopyView === "overview";
    const generatedAt = controller.canopyData?.generated_at || "";
    const syncStatus = controller.canopyData?.sync_status;
    const syncRouteVariant = String(syncStatus?.route_type || "").trim();
    const syncLabel = String(syncStatus?.label || "미동기화");
    const syncDetail = [String(syncStatus?.step || "").trim(), String(syncStatus?.message || "").trim()]
        .filter((row) => row.length > 0)
        .join(" · ");
    const currentSelection = controller.selectedWork
        ? String(controller.selectedWork.title || controller.selectedWork.label || controller.selectedWork.id || "작업")
        : controller.selectedQuestion
          ? String(controller.selectedQuestion.description || controller.selectedQuestion.cluster_id || "질문")
          : controller.rootMode
            ? "소피아 (문서/계획 워크스페이스)"
            : String(controller.selectedModuleMeta?.label || controller.selectedModule || "모듈");

    const syncTone = (() => {
        const state = String(syncStatus?.state || "unknown").toLowerCase();
        if (state === "ok") return "border-emerald-400/50 bg-emerald-900/20 text-emerald-100";
        if (state === "warning") return "border-amber-400/50 bg-amber-900/20 text-amber-100";
        if (state === "blocked") return "border-rose-400/50 bg-rose-900/20 text-rose-100";
        return "border-[#334155] bg-[#0b1220] text-gray-300";
    })();

    useEffect(() => {
        if (!overviewArmUntil) return;
        const timer = window.setTimeout(() => setOverviewArmUntil(0), Math.max(0, overviewArmUntil - Date.now()));
        return () => window.clearTimeout(timer);
    }, [overviewArmUntil]);

    const onToggleOverview = () => {
        if (overviewUnlocked) {
            controller.setCanopyView("focus");
            setOverviewArmUntil(0);
            return;
        }
        const now = Date.now();
        if (overviewArmUntil > now) {
            controller.setCanopyView("overview");
            setOverviewArmUntil(0);
            return;
        }
        setOverviewArmUntil(now + 10000);
    };

    return (
        <div className="h-full w-full bg-[#0b1020] text-gray-200 flex flex-col">
            <div className="px-4 py-3 border-b border-[#263246] bg-[#111827] flex items-center justify-between gap-3">
                <div>
                    <h1 className="text-sm font-semibold text-gray-100">Sophia Forest · 현황판</h1>
                    <p className="text-xs text-gray-400 mt-0.5">지금 해야 할 일과 현재 상태를 먼저 확인하세요.</p>
                    <p className="text-[11px] text-gray-500 mt-1 truncate">현재 선택: {currentSelection}</p>
                    {showTools ? (
                        <p className="text-[11px] text-gray-500 mt-1">
                            최신 스냅샷: {generatedAt || "N/A"}
                            {syncStatus?.last_at ? ` · 동기화 ${syncStatus.last_at}` : ""}
                        </p>
                    ) : null}
                </div>
                <div className={`px-2.5 py-1 rounded-md border text-[11px] ${syncTone}`}>
                    동기화 {syncLabel}
                    {showTools && syncDetail ? ` · ${syncDetail}` : ""}
                </div>
                {controller.lastRoadmapRecordSummary ? (
                    <div className="px-2.5 py-1 rounded-md border border-cyan-400/40 bg-cyan-900/20 text-[11px] text-cyan-100">
                        {controller.lastRoadmapRecordSummary}
                    </div>
                ) : null}
                {controller.runtimeContract && !controller.runtimeContract.roadmapRecord ? (
                    <div className="px-2.5 py-1 rounded-md border border-amber-400/50 bg-amber-900/20 text-[11px] text-amber-100">
                        서버 구버전: roadmap 기록 API 없음
                    </div>
                ) : null}
                {showTools && syncRouteVariant ? (
                    <div className="px-2.5 py-1 rounded-md border border-[#334155] bg-[#0b1220] text-[11px] text-cyan-200">
                        경로 {syncRouteVariant}
                    </div>
                ) : null}
                <div className="flex items-center gap-2">
                    <button
                        onClick={controller.refreshCanopy}
                        className="px-3 py-1.5 text-xs rounded-md border border-[#334155] bg-[#1f2937] hover:bg-[#273449]"
                    >
                        현황판 새로고침
                    </button>
                    {showTools ? (
                        <button
                            onClick={controller.recordRoadmapSnapshot}
                            disabled={controller.roadmapRecordBusy}
                            className={`px-3 py-1.5 text-xs rounded-md border ${
                                controller.roadmapRecordBusy
                                    ? "border-cyan-400 bg-cyan-900/25 text-cyan-100 opacity-80"
                                    : "border-cyan-400 bg-cyan-900/15 text-cyan-100 hover:bg-cyan-900/30"
                            }`}
                        >
                            {controller.roadmapRecordBusy ? "기록 중..." : "기록"}
                        </button>
                    ) : null}
                    <button
                        onClick={() => setShowTools((prev) => !prev)}
                        className={`px-3 py-1.5 text-xs rounded-md border ${
                            showTools
                                ? "border-cyan-400 bg-cyan-900/25 text-cyan-100"
                                : "border-[#334155] bg-[#1f2937] hover:bg-[#273449]"
                        }`}
                    >
                        {showTools ? "고급 닫기" : "고급"}
                    </button>
                </div>
            </div>

            {showTools ? (
                <div className="border-b border-[#1f2a3d] bg-[#0d1426]">
                    <div className="px-4 py-2 border-b border-[#1f2a3d] flex items-center gap-2 text-xs">
                        <button
                            onClick={() => controller.setRecordedOnly(!controller.recordedOnly)}
                            className={`px-2 py-1 rounded border ${
                                controller.recordedOnly
                                    ? "border-emerald-400 bg-emerald-900/20 text-emerald-100"
                                    : "border-[#334155] bg-[#111827] text-gray-300"
                            }`}
                        >
                            {controller.recordedOnly ? "기록 전용 ON" : "기록 전용 OFF"}
                        </button>
                        <button
                            onClick={onToggleOverview}
                            className={`px-2 py-1 rounded border ${
                                overviewUnlocked
                                    ? "border-amber-400 bg-amber-900/20 text-amber-100"
                                    : overviewArmUntil > Date.now()
                                      ? "border-amber-400 bg-amber-900/20 text-amber-100"
                                      : "border-[#334155] bg-[#111827] text-gray-300"
                            }`}
                        >
                            {overviewUnlocked
                                ? "Focus 복귀"
                                : overviewArmUntil > Date.now()
                                  ? "다시 눌러 Overview"
                                  : "Overview(2단계)"}
                        </button>
                        <span className="text-gray-500">
                            표시 {controller.visibleWorkNodesCount}/{controller.totalWorkNodesCount}
                            {controller.hiddenWorkNodesCount > 0 ? ` · 숨김 ${controller.hiddenWorkNodesCount}` : ""}
                        </span>
                        {controller.recordedOnly && controller.recordedOnlyHint ? (
                            <span className="text-gray-500">· {controller.recordedOnlyHint}</span>
                        ) : null}
                    </div>
                    <ControlPanel
                        projectName={controller.projectName}
                        onProjectNameChange={controller.setProjectName}
                        riskThreshold={controller.riskThreshold}
                        onRiskThresholdChange={controller.setRiskThreshold}
                        moduleSort={controller.moduleSort}
                        onModuleSortChange={controller.setModuleSort}
                        eventFilter={controller.eventFilter}
                        onEventFilterChange={controller.setEventFilter}
                        serverModuleFilter={controller.serverModuleFilter}
                        onServerModuleFilterChange={controller.setServerModuleFilter}
                        sourcePath={controller.sourcePath}
                        onSourcePathChange={controller.setSourcePath}
                        target={controller.target}
                        onTargetChange={controller.setTarget}
                        change={controller.change}
                        onChangeTextChange={controller.setChange}
                        scope={controller.scope}
                        onScopeChange={controller.setScope}
                        onAnalyzeByPath={controller.runAnalyzeByPath}
                        onAnalyzeTodayEditorFile={controller.runAnalyzeTodayEditorFile}
                        onAnalyzeByUpload={controller.runAnalyzeByUpload}
                        onSyncProjectStatus={controller.syncProjectStatus}
                        modeColor={controller.modeColor}
                        message={controller.message}
                        pageStatusText={controller.pageStatusText}
                        canGoPrevPage={controller.canGoPrevPage}
                        canGoNextPage={controller.canGoNextPage}
                        onPrevPage={controller.goPrevPage}
                        onNextPage={controller.goNextPage}
                    />
                </div>
            ) : null}

            <div className="flex-1 min-h-0 grid grid-cols-[minmax(380px,30%)_minmax(0,1fr)] bg-[#0f172a]">
                <ExplorerPanel
                    projectName={controller.projectName}
                    projectOptions={controller.projectOptions}
                    includeArchivedProjects={controller.includeArchivedProjects}
                    onToggleIncludeArchived={(value) => controller.setIncludeArchivedProjects(value)}
                    onSelectProject={controller.selectProject}
                    onCreateProject={controller.createProject}
                    createProjectBusy={controller.createProjectBusy}
                    projectActionBusyName={controller.projectActionBusyName}
                    onArchiveProject={controller.archiveProject}
                    onUnarchiveProject={controller.unarchiveProject}
                    inventorySeedBusy={controller.inventorySeedBusy}
                    onSeedWorkFromInventory={controller.seedWorkFromInventory}
                    projectInitStatusByName={controller.projectInitStatusByName}
                    selectedPhaseStepFilter={controller.selectedPhaseStepFilter}
                    onSelectPhaseStep={(phaseStep) =>
                        controller.setSelectedPhaseStepFilter(
                            controller.selectedPhaseStepFilter === phaseStep ? "" : phaseStep,
                        )
                    }
                    moduleOverview={controller.visibleModuleOverview}
                    selectedModule={controller.selectedModule}
                    onSelectModule={controller.selectModule}
                    filteredWorkNodes={controller.filteredWorkNodes}
                    selectedWorkId={controller.selectedWorkId}
                    onSelectWork={controller.selectWork}
                    questionQueue={controller.visibleQuestionQueue}
                    selectedClusterId={controller.selectedClusterId}
                    onSelectQuestion={controller.selectQuestion}
                    editorSourceOptions={controller.editorSourceOptions}
                    selectedEditorSourcePath={controller.selectedEditorSourcePath}
                    onSelectEditorSourcePath={controller.setSelectedEditorSourcePath}
                    onRefreshEditorSourceOptions={controller.refreshEditorSourceOptions}
                    onAnalyzeSelectedEditorFile={controller.runAnalyzeSelectedEditorFile}
                    onAnalyzeByUpload={controller.runAnalyzeByUpload}
                    sourceActionMode={controller.mode}
                    sourceActionMessage={controller.message}
                    rootMode={controller.rootMode}
                    onSelectRoot={controller.selectRoot}
                />
                <DetailPanel
                    moduleOverview={controller.visibleModuleOverview}
                    systemInventory={controller.canopyData?.system_inventory || []}
                    moduleWorkNodes={controller.filteredWorkNodes}
                    allWorkNodes={controller.visibleWorkNodes}
                    selectedModuleId={controller.selectedModule}
                    selectedModuleMeta={controller.selectedModuleMeta}
                    selectedWork={controller.selectedWork}
                    selectedQuestion={controller.selectedQuestion}
                    questionQueue={controller.visibleQuestionQueue}
                    bitmapSummary={controller.bitmapSummary}
                    selectedBitmapCandidateId={controller.selectedBitmapCandidateId}
                    selectedBitmapCandidate={controller.selectedBitmapCandidate}
                    selectedBitmapTimeline={controller.selectedBitmapTimeline}
                    bitmapTimelineLoading={controller.bitmapTimelineLoading}
                    bitmapActionBusyId={controller.bitmapActionBusyId}
                    workActionBusyId={controller.workActionBusyId}
                    bitmapEventHighlight={controller.bitmapEventHighlight}
                    onCreateWorkFromQuestion={controller.createWorkFromQuestion}
                    onCreateWorkFromCluster={controller.createWorkFromCluster}
                    onAcknowledgeWork={controller.acknowledgeWorkPackage}
                    onCompleteWork={controller.completeWorkPackage}
                    onSelectWorkNode={controller.selectWork}
                    onSelectModuleNode={controller.selectModule}
                    onSelectQuestionNode={controller.selectQuestion}
                    onSelectBitmapCandidate={controller.selectBitmapCandidate}
                    onAdoptBitmapCandidate={controller.adoptBitmapCandidate}
                    onRejectBitmapCandidate={controller.rejectBitmapCandidate}
                    moduleBottlenecks={controller.moduleBottlenecks}
                    roadmap={controller.canopyData?.roadmap ?? null}
                    progressSync={controller.canopyData?.progress_sync ?? null}
                    recentEvents={controller.canopyData?.recent_events || []}
                    topologyNodes={controller.canopyData?.topology?.nodes || []}
                    topologyEdges={controller.canopyData?.topology?.edges || []}
                    focus={controller.canopyData?.focus || null}
                    roadmapJournal={controller.canopyData?.roadmap_journal || null}
                    parallelWorkboard={controller.canopyData?.parallel_workboard || null}
                    specIndex={controller.specIndex}
                    selectedSpecPath={controller.selectedSpecPath}
                    selectedSpecContent={controller.selectedSpecContent}
                    specLoading={controller.specLoading}
                    specUploadBusy={controller.specUploadBusy}
                    specReviewBusy={controller.specReviewBusy}
                    onSelectSpecPath={controller.selectSpecPath}
                    onRequestSpecReview={controller.requestSpecReview}
                    onSetSpecStatus={controller.setSpecStatus}
                    onUploadSpecByFile={controller.uploadSpecByFile}
                    todoItems={controller.todoItems}
                    todoBusy={controller.todoBusy}
                    onUpsertTodo={controller.upsertTodo}
                    onSetTodoStatus={controller.setTodoStatus}
                    rootMode={controller.rootMode}
                    mindWorkstream={controller.canopyData?.mind_workstream || null}
                    handoffSummary={controller.handoffSummary}
                    applePlan={controller.applePlan}
                    applePlanBusy={controller.applePlanBusy}
                    onSyncApplePlan={controller.syncApplePlan}
                    humanView={controller.canopyData?.human_view || null}
                    overviewUnlocked={overviewUnlocked}
                    selectedPhaseStepFilter={controller.selectedPhaseStepFilter}
                    onClearPhaseStepFilter={() => controller.setSelectedPhaseStepFilter("")}
                    onSelectPhaseStep={(phaseStep) => controller.setSelectedPhaseStepFilter(phaseStep)}
                    snapshotDiff={controller.snapshotDiff}
                    syncDigestLine={controller.syncDigestLine}
                    syncHistory={controller.syncHistory}
                    lastRoadmapRecordSummary={controller.lastRoadmapRecordSummary}
                    recordedOnlyHint={controller.recordedOnlyHint}
                    recordedOnlyHiddenSamples={controller.recordedOnlyHiddenSamples}
                />
            </div>
        </div>
    );
}
