import type { CanopyDataResponse, CanopyEventRow, TopologyEdge } from "./types";

type CanopyBoardProps = {
    canopyData: CanopyDataResponse | null;
    highlightEventType?: string | null;
    highlightCandidateId?: string | null;
    highlightModuleId?: string | null;
};

function levelStyle(level?: string): string {
    const normalized = String(level || "info").toLowerCase();
    if (normalized === "error") return "border-rose-500/50 bg-rose-900/20 text-rose-100";
    if (normalized === "warning") return "border-amber-400/50 bg-amber-900/20 text-amber-100";
    return "border-[#334155] bg-[#0b1220] text-gray-200";
}

function reasonCategoryStyle(category?: string): string {
    const normalized = String(category || "").toLowerCase();
    if (normalized === "scope") return "border-amber-400/40 bg-amber-900/20 text-amber-100";
    if (normalized === "dependency") return "border-cyan-400/40 bg-cyan-900/20 text-cyan-100";
    if (normalized === "conflict") return "border-rose-400/40 bg-rose-900/20 text-rose-100";
    if (normalized === "success") return "border-emerald-400/40 bg-emerald-900/20 text-emerald-100";
    return "border-[#334155] bg-[#0b1220] text-gray-200";
}

function renderEdge(edge: TopologyEdge): string {
    return `${edge.from.replace(/^.*:/, "")} -> ${edge.to.replace(/^.*:/, "")}`;
}

function renderSummary(event: CanopyEventRow): string {
    const base = String(event.summary || "").trim();
    if (base) return base;
    const payload = event.payload;
    if (payload && typeof payload === "object" && typeof payload.summary === "string") {
        return payload.summary;
    }
    return "-";
}

export function CanopyBoard({
    canopyData,
    highlightEventType,
    highlightCandidateId,
    highlightModuleId,
}: CanopyBoardProps) {
    if (!canopyData) {
        return (
            <div className="rounded-lg border border-[#334155] bg-[#111827] p-4 text-xs text-gray-400">
                현황판 데이터를 불러오는 중입니다.
            </div>
        );
    }

    const moduleRows = canopyData.module_overview || [];
    const roadmap = canopyData.roadmap || { total_work: 0, remaining_work: 0, done_last_7d: 0, eta_days: null, eta_hint: "" };
    const inProgress = roadmap.in_progress || [];
    const pending = roadmap.pending || [];
    const doneRecent = roadmap.done_recent || [];
    const questionQueue = canopyData.question_queue || [];
    const soneSummary = canopyData.sone_summary || {};
    const missingSlots = soneSummary.missing_slots || [];
    const riskReasons = soneSummary.risk_reasons || [];
    const events = canopyData.recent_events || [];
    const recentEvents = [...events].slice(-40).reverse();
    const topologyEdges = canopyData.topology?.edges || [];
    const topQuestion = questionQueue[0] || null;
    const blockedWork = pending.find((item) => {
        const status = String(item.status || "").toUpperCase();
        return status === "BLOCKED" || status === "FAILED";
    }) || null;
    const activeWork = blockedWork || inProgress[0] || pending[0] || null;
    const latestEvent = recentEvents[0] || null;

    return (
        <div className="p-3 space-y-3 overflow-auto">
            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">관제 포커스 (지금 확인할 3가지)</p>
                <div className="grid grid-cols-3 gap-2">
                    <div className="rounded border border-rose-400/40 bg-rose-900/15 px-2 py-2">
                        <p className="text-[11px] text-rose-200 mb-1">최고 위험 질문</p>
                        {topQuestion ? (
                            <>
                                <p className="text-xs text-gray-100 truncate">{topQuestion.cluster_id}</p>
                                <p className="text-[11px] text-gray-300">
                                    risk {Number(topQuestion.risk_score || 0).toFixed(2)} · hit {Number(topQuestion.hit_count || 0)}
                                </p>
                            </>
                        ) : (
                            <p className="text-[11px] text-gray-500">없음</p>
                        )}
                    </div>
                    <div className="rounded border border-amber-400/40 bg-amber-900/15 px-2 py-2">
                        <p className="text-[11px] text-amber-200 mb-1">최우선 작업</p>
                        {activeWork ? (
                            <>
                                <p className="text-xs text-gray-100 truncate">{activeWork.label}</p>
                                <p className="text-[11px] text-gray-300">
                                    {String(activeWork.status || "READY")} · P{Number(activeWork.priority_score || 0)}
                                </p>
                            </>
                        ) : (
                            <p className="text-[11px] text-gray-500">없음</p>
                        )}
                    </div>
                    <div className="rounded border border-cyan-400/40 bg-cyan-900/15 px-2 py-2">
                        <p className="text-[11px] text-cyan-200 mb-1">최신 변경</p>
                        {latestEvent ? (
                            <>
                                <p className="text-xs text-gray-100 truncate">
                                    {String(latestEvent.event_type || "EVENT")} · {String(latestEvent.target || "-")}
                                </p>
                                <p className="text-[11px] text-gray-300 truncate">{renderSummary(latestEvent)}</p>
                            </>
                        ) : (
                            <p className="text-[11px] text-gray-500">없음</p>
                        )}
                    </div>
                </div>
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">모듈별 진행 현황</p>
                <div className="grid grid-cols-5 gap-2">
                    {moduleRows.map((module) => (
                        <div
                            key={module.module}
                            className={`rounded border px-2 py-2 ${
                                highlightModuleId && highlightModuleId === module.module
                                    ? "border-cyan-300/80 ring-1 ring-cyan-300 bg-[#0b1220]"
                                    : "border-[#334155] bg-[#0b1220]"
                            }`}
                        >
                            <p className="text-xs text-gray-100 font-medium">{module.label}</p>
                            <p className="text-[11px] text-cyan-200 mt-1">진행률 {module.progress_pct}%</p>
                            <p className="text-[11px] text-amber-200">중요도 {module.importance}</p>
                            <p className="text-[11px] text-gray-400">
                                작업 {module.work_total} · 질문 {module.pending_questions}
                            </p>
                        </div>
                    ))}
                </div>
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">로드맵 진행</p>
                <div className="grid grid-cols-3 gap-2 text-xs mb-2">
                    <div className="rounded border border-[#334155] bg-[#0b1220] px-2 py-2">
                        <p className="text-gray-400">총 작업</p>
                        <p className="text-gray-100 font-semibold">{roadmap.total_work}</p>
                    </div>
                    <div className="rounded border border-[#334155] bg-[#0b1220] px-2 py-2">
                        <p className="text-gray-400">남은 작업</p>
                        <p className="text-amber-100 font-semibold">{roadmap.remaining_work}</p>
                    </div>
                    <div className="rounded border border-[#334155] bg-[#0b1220] px-2 py-2">
                        <p className="text-gray-400">최근 7일 완료</p>
                        <p className="text-emerald-100 font-semibold">{roadmap.done_last_7d}</p>
                    </div>
                </div>
                <p className="text-[11px] text-gray-400 mb-2">{roadmap.eta_hint || "-"}</p>
                <div className="grid grid-cols-3 gap-2">
                    <div className="rounded border border-[#334155] bg-[#0b1220] p-2">
                        <p className="text-[11px] text-cyan-200 mb-1">IN_PROGRESS</p>
                        <div className="space-y-1">
                            {inProgress.slice(0, 5).map((item) => (
                                <p key={item.id} className="text-[11px] text-gray-200 truncate">
                                    {item.label}
                                </p>
                            ))}
                            {inProgress.length === 0 && <p className="text-[11px] text-gray-500">없음</p>}
                        </div>
                    </div>
                    <div className="rounded border border-[#334155] bg-[#0b1220] p-2">
                        <p className="text-[11px] text-amber-200 mb-1">PENDING/BLOCKED</p>
                        <div className="space-y-1">
                            {pending.slice(0, 5).map((item) => (
                                <p key={item.id} className="text-[11px] text-gray-200 truncate">
                                    {item.label}
                                </p>
                            ))}
                            {pending.length === 0 && <p className="text-[11px] text-gray-500">없음</p>}
                        </div>
                    </div>
                    <div className="rounded border border-[#334155] bg-[#0b1220] p-2">
                        <p className="text-[11px] text-emerald-200 mb-1">DONE(RECENT)</p>
                        <div className="space-y-1">
                            {doneRecent.slice(0, 5).map((item) => (
                                <p key={item.id} className="text-[11px] text-gray-200 truncate">
                                    {item.label}
                                </p>
                            ))}
                            {doneRecent.length === 0 && <p className="text-[11px] text-gray-500">없음</p>}
                        </div>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                    <p className="text-xs text-gray-400 mb-2">질문 큐 (리스크 순)</p>
                    <div className="space-y-1 max-h-56 overflow-auto">
                        {questionQueue.slice(0, 20).map((row) => (
                            <div key={row.cluster_id} className="rounded border border-[#334155] bg-[#0b1220] px-2 py-1.5">
                                <p className="text-xs text-gray-100 truncate">{row.cluster_id}</p>
                                <p className="text-[11px] text-gray-400">
                                    risk {row.risk_score.toFixed(2)} · hit {row.hit_count} · {row.status}
                                </p>
                            </div>
                        ))}
                        {questionQueue.length === 0 && <p className="text-[11px] text-gray-500">질문 항목 없음</p>}
                    </div>
                </div>

                <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                    <p className="text-xs text-gray-400 mb-2">모듈 연결 맵 (간략)</p>
                    <div className="space-y-1 max-h-56 overflow-auto font-mono text-[11px]">
                        {topologyEdges.slice(0, 30).map((edge, idx) => (
                            <p key={`${edge.from}-${edge.to}-${idx}`} className="text-gray-300">
                                {renderEdge(edge)}
                            </p>
                        ))}
                        {topologyEdges.length === 0 && <p className="text-gray-500">연결 데이터 없음</p>}
                    </div>
                </div>
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">SonE 검증 이유 카드</p>
                <div className="grid grid-cols-2 gap-3">
                    <div className="rounded border border-[#334155] bg-[#0b1220] p-2">
                        <p className="text-[11px] text-amber-200 mb-1">누락 슬롯 (Missing)</p>
                        <div className="space-y-1.5 max-h-52 overflow-auto">
                            {missingSlots.slice(0, 8).map((slot, idx) => (
                                <div
                                    key={`${slot.target}-${slot.status}-${idx}`}
                                    className="rounded border border-amber-500/30 bg-amber-900/10 px-2 py-1.5"
                                >
                                    <p className="text-xs text-gray-100 truncate">{slot.target || "-"}</p>
                                    <p className="text-[11px] text-amber-100">
                                        {slot.reason_code || "SONE_UNKNOWN"} · {slot.status || "missing"}
                                    </p>
                                    <p className="text-[11px] text-gray-400 truncate">
                                        {slot.reason_description || slot.evidence || "-"}
                                    </p>
                                </div>
                            ))}
                            {missingSlots.length === 0 && <p className="text-[11px] text-gray-500">누락 슬롯 없음</p>}
                        </div>
                    </div>
                    <div className="rounded border border-[#334155] bg-[#0b1220] p-2">
                        <p className="text-[11px] text-rose-200 mb-1">리스크 이유 (Risk Reasons)</p>
                        <div className="space-y-1.5 max-h-52 overflow-auto">
                            {riskReasons.slice(0, 8).map((reason, idx) => (
                                <div
                                    key={`${reason.cluster_id}-${reason.reason_code}-${idx}`}
                                    className={`rounded border px-2 py-1.5 ${reasonCategoryStyle(reason.category)}`}
                                >
                                    <p className="text-xs text-gray-100 truncate">{reason.cluster_id || "-"}</p>
                                    <p className="text-[11px]">
                                        {reason.reason_code || "SONE_UNKNOWN"} · risk{" "}
                                        {Number(reason.risk_score || 0).toFixed(2)}
                                    </p>
                                    <p className="text-[11px] text-gray-300 truncate">
                                        {reason.reason_description || reason.description || "-"}
                                    </p>
                                    {reason.evidence ? (
                                        <p className="text-[11px] text-gray-400 truncate">evidence: {reason.evidence}</p>
                                    ) : null}
                                </div>
                            ))}
                            {riskReasons.length === 0 && <p className="text-[11px] text-gray-500">리스크 이유 없음</p>}
                        </div>
                    </div>
                </div>
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">최근 변경 이벤트</p>
                <div className="space-y-1 max-h-56 overflow-auto">
                    {recentEvents.map((event, idx) => {
                        const payload = event.payload || {};
                        const payloadCandidate = typeof payload.candidate_id === "string" ? payload.candidate_id : "";
                        const summary = renderSummary(event);
                        const eventTypeMatch =
                            !highlightEventType ||
                            String(event.event_type || "").toUpperCase() === String(highlightEventType || "").toUpperCase();
                        const candidateMatch =
                            !!highlightCandidateId &&
                            (String(event.target || "").includes(String(highlightCandidateId)) ||
                                String(payloadCandidate || "").includes(String(highlightCandidateId)) ||
                                summary.includes(String(highlightCandidateId)));
                        const isHighlight = eventTypeMatch && candidateMatch;
                        return (
                            <div
                                key={`${event.timestamp || "ts"}-${event.event_type || "evt"}-${idx}`}
                                className={`rounded border px-2 py-1.5 text-[11px] ${levelStyle(event.level)} ${
                                    isHighlight ? "ring-1 ring-cyan-300 border-cyan-300/70" : ""
                                }`}
                            >
                                <p className="text-gray-300">
                                    {event.timestamp || "-"} · {event.event_type || "-"} · {event.target || "-"}
                                </p>
                                <p className="text-gray-100">{summary}</p>
                            </div>
                        );
                    })}
                    {events.length === 0 && <p className="text-[11px] text-gray-500">최근 이벤트 없음</p>}
                </div>
            </div>
        </div>
    );
}
