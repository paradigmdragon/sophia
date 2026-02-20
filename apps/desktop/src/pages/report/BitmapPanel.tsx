import { useState } from "react";

import type { BitmapAuditResponse, BitmapSummaryResponse } from "./types";

type BitmapPanelProps = {
    bitmapSummary: BitmapSummaryResponse | null;
    bitmapAudit: BitmapAuditResponse | null;
    bitmapActionBusyId: string;
    selectedCandidateId: string;
    onSelectCandidate: (candidateId: string) => void;
    onAdopt: (candidateId: string, episodeId: string) => void;
    onReject: (candidateId: string, episodeId: string, reason?: string) => void;
};

function pct(value: number): string {
    return `${(value * 100).toFixed(0)}%`;
}

export function BitmapPanel({
    bitmapSummary,
    bitmapAudit,
    bitmapActionBusyId,
    selectedCandidateId,
    onSelectCandidate,
    onAdopt,
    onReject,
}: BitmapPanelProps) {
    const [rejectReason, setRejectReason] = useState("");

    if (!bitmapSummary) {
        return (
            <div className="border-l border-[#263246] p-3 overflow-auto">
                <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                    <p className="text-xs text-gray-400">Bitmap Lifecycle</p>
                    <p className="text-xs text-gray-500 mt-2">bitmap 상태 로딩 중</p>
                </div>
            </div>
        );
    }

    const metrics = bitmapSummary.metrics || {};
    const lifecycle = bitmapSummary.lifecycle || {
        window_days: 7,
        candidate_status_counts: {},
        event_counts: {},
        invalid_reason_counts: {},
        adoption_rate: 0,
        pending_count: 0,
        recent_transitions: [],
    };

    const statusCounts = lifecycle.candidate_status_counts || {};
    const eventCounts = lifecycle.event_counts || {};
    const invalidReasons = lifecycle.invalid_reason_counts || {};
    const transitions = lifecycle.recent_transitions || [];
    const auditTotals = bitmapAudit?.totals || {
        candidate_total: 0,
        status_counts: {},
        event_counts: {},
    };
    const auditTransitions = bitmapAudit?.candidate_transitions || [];
    const auditReasons = bitmapAudit?.top_failure_reasons || [];

    return (
        <div className="border-l border-[#263246] p-3 overflow-auto space-y-3">
            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">Pending Candidates</p>
                <label className="text-[11px] text-gray-400 mb-1 block">Reject Reason (optional)</label>
                <input
                    value={rejectReason}
                    onChange={(event) => setRejectReason(event.target.value)}
                    placeholder="manual_reject_ui"
                    className="w-full rounded bg-[#0b1220] border border-[#334155] px-2 py-1 text-[11px] text-gray-200 mb-2"
                />
                <div className="space-y-1 max-h-44 overflow-auto">
                    {(bitmapSummary.candidates || [])
                        .filter((row) => String(row.status || "").toUpperCase() === "PENDING")
                        .slice(0, 20)
                        .map((row) => {
                            const isBusy = bitmapActionBusyId === row.id;
                            return (
                                <button
                                    key={row.id}
                                    onClick={() => onSelectCandidate(row.id)}
                                    className={`w-full text-left rounded border px-2 py-1.5 ${
                                        selectedCandidateId === row.id
                                            ? "border-cyan-300/80 ring-1 ring-cyan-300 bg-[#0b1220]"
                                            : "border-[#334155] bg-[#0b1220]"
                                    }`}
                                >
                                    <p className="text-[11px] text-gray-100 truncate">{row.id}</p>
                                    <p className="text-[11px] text-gray-400 truncate">{row.note || "-"}</p>
                                    <div className="mt-1 flex gap-1" onClick={(event) => event.stopPropagation()}>
                                        <button
                                            onClick={() => onAdopt(row.id, row.episode_id)}
                                            disabled={isBusy}
                                            className="px-1.5 py-0.5 text-[10px] rounded border border-emerald-500/70 bg-emerald-900/20 text-emerald-100 disabled:opacity-40"
                                        >
                                            채택
                                        </button>
                                        <button
                                            onClick={() => onReject(row.id, row.episode_id, rejectReason)}
                                            disabled={isBusy}
                                            className="px-1.5 py-0.5 text-[10px] rounded border border-rose-500/70 bg-rose-900/20 text-rose-100 disabled:opacity-40"
                                        >
                                            거절
                                        </button>
                                    </div>
                                </button>
                            );
                        })}
                    {(bitmapSummary.candidates || []).filter((row) => String(row.status || "").toUpperCase() === "PENDING").length === 0 && (
                        <p className="text-[11px] text-gray-500">PENDING 후보 없음</p>
                    )}
                </div>
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">Bitmap Lifecycle ({lifecycle.window_days}d)</p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="rounded border border-[#334155] bg-[#0b1220] px-2 py-1.5">
                        <p className="text-gray-400">채택률</p>
                        <p className="text-emerald-200 font-semibold">{pct(Number(lifecycle.adoption_rate || 0))}</p>
                    </div>
                    <div className="rounded border border-[#334155] bg-[#0b1220] px-2 py-1.5">
                        <p className="text-gray-400">PENDING</p>
                        <p className="text-amber-200 font-semibold">{Number(lifecycle.pending_count || 0)}</p>
                    </div>
                    <div className="rounded border border-[#334155] bg-[#0b1220] px-2 py-1.5">
                        <p className="text-gray-400">INVALID</p>
                        <p className="text-rose-200 font-semibold">{Number(metrics.invalid_count_7d || 0)}</p>
                    </div>
                    <div className="rounded border border-[#334155] bg-[#0b1220] px-2 py-1.5">
                        <p className="text-gray-400">CONFLICT</p>
                        <p className="text-rose-200 font-semibold">{Number(metrics.conflict_mark_count_7d || 0)}</p>
                    </div>
                </div>
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">Transition Audit ({bitmapAudit?.window_days ?? 30}d)</p>
                <div className="grid grid-cols-2 gap-2 text-xs mb-2">
                    <div className="rounded border border-[#334155] bg-[#0b1220] px-2 py-1.5">
                        <p className="text-gray-400">Candidate Total</p>
                        <p className="text-gray-100 font-semibold">{Number(auditTotals.candidate_total || 0)}</p>
                    </div>
                    <div className="rounded border border-[#334155] bg-[#0b1220] px-2 py-1.5">
                        <p className="text-gray-400">PENDING/ADOPTED/REJECTED</p>
                        <p className="text-gray-100 font-semibold">
                            {Number(auditTotals.status_counts?.PENDING || 0)}/
                            {Number(auditTotals.status_counts?.ADOPTED || 0)}/
                            {Number(auditTotals.status_counts?.REJECTED || 0)}
                        </p>
                    </div>
                    <div className="rounded border border-[#334155] bg-[#0b1220] px-2 py-1.5">
                        <p className="text-gray-400">PROPOSE/ADOPT/REJECT</p>
                        <p className="text-gray-100 font-semibold">
                            {Number(auditTotals.event_counts?.PROPOSE || 0)}/
                            {Number(auditTotals.event_counts?.ADOPT || 0)}/
                            {Number(auditTotals.event_counts?.REJECT || 0)}
                        </p>
                    </div>
                    <div className="rounded border border-[#334155] bg-[#0b1220] px-2 py-1.5">
                        <p className="text-gray-400">INVALID/CONFLICT</p>
                        <p className="text-gray-100 font-semibold">
                            {Number(auditTotals.event_counts?.BITMAP_INVALID || 0)}/
                            {Number(auditTotals.event_counts?.CONFLICT_MARK || 0)}
                        </p>
                    </div>
                </div>
                <p className="text-[11px] text-gray-400 mb-1">Top Failure Reasons</p>
                <div className="space-y-1 mb-2">
                    {auditReasons.length === 0 && <p className="text-[11px] text-gray-500">데이터 없음</p>}
                    {auditReasons.slice(0, 5).map((row) => (
                        <p key={row.reason} className="text-[11px] text-rose-200">
                            {row.reason}: {Number(row.count || 0)}
                        </p>
                    ))}
                </div>
                <p className="text-[11px] text-gray-400 mb-1">Top Candidate Transitions</p>
                <div className="space-y-1 max-h-28 overflow-auto">
                    {auditTransitions.length === 0 && <p className="text-[11px] text-gray-500">데이터 없음</p>}
                    {auditTransitions.slice(0, 8).map((row) => (
                        <p key={row.candidate_id} className="text-[11px] text-gray-200">
                            {row.candidate_id} · {row.transition_count} · {row.current_status}
                        </p>
                    ))}
                </div>
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">Candidate Status</p>
                <div className="space-y-1 text-xs">
                    {Object.keys(statusCounts).length === 0 && <p className="text-gray-500">데이터 없음</p>}
                    {Object.entries(statusCounts).map(([key, value]) => (
                        <p key={key} className="text-gray-200">
                            {key}: <span className="text-gray-100">{Number(value || 0)}</span>
                        </p>
                    ))}
                </div>
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">Event Counts</p>
                <div className="space-y-1 text-xs">
                    {Object.keys(eventCounts).length === 0 && <p className="text-gray-500">데이터 없음</p>}
                    {Object.entries(eventCounts).map(([key, value]) => (
                        <p key={key} className="text-gray-200">
                            {key}: <span className="text-gray-100">{Number(value || 0)}</span>
                        </p>
                    ))}
                </div>
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">Invalid Reasons</p>
                <div className="space-y-1 text-xs">
                    {Object.keys(invalidReasons).length === 0 && <p className="text-gray-500">데이터 없음</p>}
                    {Object.entries(invalidReasons).map(([key, value]) => (
                        <p key={key} className="text-gray-200">
                            {key}: <span className="text-rose-200">{Number(value || 0)}</span>
                        </p>
                    ))}
                </div>
            </div>

            <div className="rounded-lg border border-[#334155] bg-[#111827] p-3">
                <p className="text-xs text-gray-400 mb-2">Recent Transitions</p>
                <div className="space-y-1 text-[11px] max-h-40 overflow-auto">
                    {transitions.length === 0 && <p className="text-gray-500">전이 로그 없음</p>}
                    {transitions.slice(0, 20).map((row, idx) => (
                        <div key={`${row.event_type}-${row.at}-${idx}`} className="rounded border border-[#334155] bg-[#0b1220] px-2 py-1">
                            <p className="text-gray-200">
                                {row.event_type} · {row.candidate_id || "-"}
                            </p>
                            <p className="text-gray-400">{row.at || "-"}</p>
                            {row.reason ? <p className="text-rose-200">{row.reason}</p> : null}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
