import type { ModuleOverview, QuestionRow, WorkNode } from "./types";

type ExplorerPanelProps = {
    moduleOverview: ModuleOverview[];
    selectedModule: string;
    onSelectModule: (moduleId: string) => void;
    filteredWorkNodes: WorkNode[];
    selectedWorkId: string;
    onSelectWork: (workId: string) => void;
    questionQueue: QuestionRow[];
    selectedClusterId: string;
    onSelectQuestion: (clusterId: string) => void;
};

export function ExplorerPanel({
    moduleOverview,
    selectedModule,
    onSelectModule,
    filteredWorkNodes,
    selectedWorkId,
    onSelectWork,
    questionQueue,
    selectedClusterId,
    onSelectQuestion,
}: ExplorerPanelProps) {
    return (
        <div className="border-r border-[#263246] p-3 overflow-auto space-y-3">
            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">Module Drilldown</p>
                <div className="grid grid-cols-2 gap-2">
                    {moduleOverview.map((module) => (
                        <button
                            key={module.module}
                            onClick={() => onSelectModule(module.module)}
                            className={`text-left rounded border px-2 py-1.5 text-xs ${
                                selectedModule === module.module
                                    ? "border-blue-400 bg-[#1e3a8a]/30"
                                    : "border-[#334155] bg-[#0b1220]"
                            }`}
                        >
                            <p className="text-gray-100">{module.label}</p>
                            <p className="text-gray-400 text-[11px]">{module.progress_pct}% · 중요도 {module.importance}</p>
                        </button>
                    ))}
                </div>
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">Work Objects ({filteredWorkNodes.length})</p>
                <div className="max-h-44 overflow-auto space-y-1">
                    {filteredWorkNodes.length === 0 && <p className="text-xs text-gray-500">작업 없음</p>}
                    {filteredWorkNodes.map((work) => (
                        <button
                            key={work.id}
                            onClick={() => onSelectWork(work.id)}
                            className={`w-full text-left rounded border px-2 py-1.5 text-xs ${
                                selectedWorkId === work.id
                                    ? "border-emerald-400 bg-emerald-900/20"
                                    : "border-[#334155] bg-[#0b1220]"
                            }`}
                        >
                            <p className="text-gray-100 truncate">{work.label}</p>
                            <p className="text-gray-400 text-[11px]">
                                {work.status} · {work.kind || "WORK"} · P{work.priority_score ?? 0}
                            </p>
                        </button>
                    ))}
                </div>
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">Question Clusters ({questionQueue.length})</p>
                <div className="max-h-40 overflow-auto space-y-1">
                    {questionQueue.length === 0 && <p className="text-xs text-gray-500">질문 없음</p>}
                    {questionQueue.map((question) => (
                        <button
                            key={question.cluster_id}
                            onClick={() => onSelectQuestion(question.cluster_id)}
                            className={`w-full text-left rounded border px-2 py-1.5 text-xs ${
                                selectedClusterId === question.cluster_id
                                    ? "border-amber-400 bg-amber-900/20"
                                    : "border-[#334155] bg-[#0b1220]"
                            }`}
                        >
                            <p className="text-gray-100 truncate">{question.cluster_id}</p>
                            <p className="text-gray-400 text-[11px]">
                                risk {question.risk_score.toFixed(2)} · hit {question.hit_count}
                            </p>
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
}
