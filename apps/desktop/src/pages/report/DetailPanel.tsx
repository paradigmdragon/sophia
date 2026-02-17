import type { ModuleOverview, QuestionRow, RoadmapSummary, WorkNode } from "./types";

type DetailPanelProps = {
    selectedModuleMeta: ModuleOverview | null;
    selectedWork: WorkNode | null;
    linkedQuestions: QuestionRow[];
    selectedQuestion: QuestionRow | null;
    onCreateWorkFromQuestion: () => void;
    moduleBottlenecks: WorkNode[];
    roadmap: RoadmapSummary | null;
};

export function DetailPanel({
    selectedModuleMeta,
    selectedWork,
    linkedQuestions,
    selectedQuestion,
    onCreateWorkFromQuestion,
    moduleBottlenecks,
    roadmap,
}: DetailPanelProps) {
    return (
        <div className="p-3 overflow-auto space-y-3">
            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">Selected Module</p>
                {selectedModuleMeta ? (
                    <div className="grid grid-cols-2 gap-2 text-xs text-gray-300">
                        <p>모듈: <span className="text-gray-100">{selectedModuleMeta.label}</span></p>
                        <p>진행률: <span className="text-gray-100">{selectedModuleMeta.progress_pct}%</span></p>
                        <p>중요도: <span className="text-gray-100">{selectedModuleMeta.importance}</span></p>
                        <p>작업 수: <span className="text-gray-100">{selectedModuleMeta.work_total}</span></p>
                        <p>질문 수: <span className="text-gray-100">{selectedModuleMeta.pending_questions}</span></p>
                        <p>최대 리스크: <span className="text-gray-100">{selectedModuleMeta.max_risk_score.toFixed(2)}</span></p>
                    </div>
                ) : (
                    <p className="text-xs text-gray-500">선택된 모듈이 없습니다.</p>
                )}
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">Selected Work</p>
                {selectedWork ? (
                    <div className="space-y-1 text-xs text-gray-300">
                        <p>id: <span className="text-gray-100">{selectedWork.id}</span></p>
                        <p>title: <span className="text-gray-100">{selectedWork.label}</span></p>
                        <p>status: <span className="text-gray-100">{selectedWork.status}</span></p>
                        <p>module: <span className="text-gray-100">{selectedWork.module_label || selectedWork.module || "-"}</span></p>
                        <p>priority: <span className="text-gray-100">{selectedWork.priority_score ?? 0}</span></p>
                        <p>linked_node: <span className="text-gray-100">{selectedWork.linked_node || "-"}</span></p>
                        <p>linked_risk: <span className="text-gray-100">{Number(selectedWork.linked_risk || 0).toFixed(2)}</span></p>
                        <p>updated_at: <span className="text-gray-100">{selectedWork.updated_at || "-"}</span></p>
                    </div>
                ) : (
                    <p className="text-xs text-gray-500">선택된 작업이 없습니다.</p>
                )}
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">Linked Questions ({linkedQuestions.length})</p>
                {linkedQuestions.length === 0 && <p className="text-xs text-gray-500">연결된 질문 없음</p>}
                {linkedQuestions.length > 0 && (
                    <div className="space-y-1 text-xs">
                        {linkedQuestions.map((row) => (
                            <p key={row.cluster_id} className="text-gray-200">
                                {row.cluster_id} · risk {row.risk_score.toFixed(2)} · {row.status}
                            </p>
                        ))}
                    </div>
                )}
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">Selected Question</p>
                {selectedQuestion ? (
                    <div className="space-y-2 text-xs text-gray-300">
                        <div className="space-y-1">
                            <p>cluster: <span className="text-gray-100">{selectedQuestion.cluster_id}</span></p>
                            <p>risk: <span className="text-gray-100">{selectedQuestion.risk_score.toFixed(2)}</span></p>
                            <p>hit: <span className="text-gray-100">{selectedQuestion.hit_count}</span></p>
                            <p>status: <span className="text-gray-100">{selectedQuestion.status}</span></p>
                            <p>linked_nodes: <span className="text-gray-100">{(selectedQuestion.linked_nodes || []).join(", ") || "-"}</span></p>
                        </div>
                        <button
                            onClick={onCreateWorkFromQuestion}
                            className="px-2 py-1.5 text-xs rounded-md border border-amber-400 bg-amber-900/30 hover:bg-amber-900/50 text-amber-100"
                        >
                            선택 질문으로 Work Package 생성
                        </button>
                    </div>
                ) : (
                    <p className="text-xs text-gray-500">선택된 질문이 없습니다.</p>
                )}
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">Module Bottlenecks</p>
                {moduleBottlenecks.length === 0 ? (
                    <p className="text-xs text-gray-500">병목 없음</p>
                ) : (
                    <div className="space-y-1 text-xs">
                        {moduleBottlenecks.map((row) => (
                            <p key={row.id} className="text-gray-200">
                                {row.label} · {row.status} · risk {Number(row.linked_risk || 0).toFixed(2)}
                            </p>
                        ))}
                    </div>
                )}
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">Roadmap Snapshot</p>
                <div className="grid grid-cols-2 gap-2 text-xs text-gray-300">
                    <p>총 작업: <span className="text-gray-100">{roadmap?.total_work ?? 0}</span></p>
                    <p>남은 작업: <span className="text-gray-100">{roadmap?.remaining_work ?? 0}</span></p>
                    <p>7일 완료: <span className="text-gray-100">{roadmap?.done_last_7d ?? 0}</span></p>
                    <p>ETA: <span className="text-gray-100">{roadmap?.eta_days ?? "N/A"}</span></p>
                </div>
                <p className="text-xs text-gray-400 mt-2">{roadmap?.eta_hint || "-"}</p>
            </div>
        </div>
    );
}
