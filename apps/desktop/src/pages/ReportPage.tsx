import { ControlPanel } from "./report/ControlPanel";
import { DetailPanel } from "./report/DetailPanel";
import { ExplorerPanel } from "./report/ExplorerPanel";
import { useReportController } from "./report/useReportController";

export function ReportPage() {
    const controller = useReportController();

    return (
        <div className="h-full w-full bg-[#0b1020] text-gray-200 flex flex-col">
            <div className="px-4 py-3 border-b border-[#263246] bg-[#111827] flex items-center justify-between gap-3">
                <div>
                    <h1 className="text-sm font-semibold text-gray-100">Sophia Forest · 현황판</h1>
                    <p className="text-xs text-gray-400 mt-0.5">설계 검토(SonE) 기반 진행 상태 관제</p>
                </div>
                <button
                    onClick={controller.refreshCanopy}
                    className="px-3 py-1.5 text-xs rounded-md border border-[#334155] bg-[#1f2937] hover:bg-[#273449]"
                >
                    현황판 새로고침
                </button>
            </div>

            <div className="flex-1 min-h-0 grid grid-cols-[340px_minmax(0,1fr)] gap-0">
                <ControlPanel
                    projectName={controller.projectName}
                    onProjectNameChange={controller.setProjectName}
                    riskThreshold={controller.riskThreshold}
                    onRiskThresholdChange={controller.setRiskThreshold}
                    moduleSort={controller.moduleSort}
                    onModuleSortChange={controller.setModuleSort}
                    eventFilter={controller.eventFilter}
                    onEventFilterChange={controller.setEventFilter}
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
                    modeColor={controller.modeColor}
                    message={controller.message}
                />

                <div className="min-w-0 min-h-0 bg-[#0b1020] grid grid-rows-[minmax(0,58%)_minmax(0,42%)]">
                    <iframe
                        src={controller.dashboardSrc}
                        className="w-full h-full border-none"
                        title="Sophia Forest Dashboard"
                    />

                    <div className="border-t border-[#263246] bg-[#0f172a] min-h-0 grid grid-cols-[380px_minmax(0,1fr)]">
                        <ExplorerPanel
                            moduleOverview={controller.canopyData?.module_overview || []}
                            selectedModule={controller.selectedModule}
                            onSelectModule={controller.selectModule}
                            filteredWorkNodes={controller.filteredWorkNodes}
                            selectedWorkId={controller.selectedWorkId}
                            onSelectWork={controller.selectWork}
                            questionQueue={controller.questionQueue}
                            selectedClusterId={controller.selectedClusterId}
                            onSelectQuestion={controller.selectQuestion}
                        />
                        <DetailPanel
                            selectedModuleMeta={controller.selectedModuleMeta}
                            selectedWork={controller.selectedWork}
                            linkedQuestions={controller.linkedQuestions}
                            selectedQuestion={controller.selectedQuestion}
                            onCreateWorkFromQuestion={controller.createWorkFromQuestion}
                            moduleBottlenecks={controller.moduleBottlenecks}
                            roadmap={controller.canopyData?.roadmap ?? null}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
