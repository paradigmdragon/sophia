import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Calendar, ChevronRight, RefreshCw, Sparkles } from "lucide-react";

import { chatService } from "../lib/chatService";
import {
    MindDashboard,
    memoryService,
    SophiaNoteGeneratorStatus,
    SophiaSystemNote,
} from "../lib/memoryService";

const today = new Date().toISOString().split("T")[0];

function badgeClass(badge?: string): string {
    const key = (badge || "INFO").toUpperCase();
    if (key === "RISK_HIGH") return "bg-red-900/50 text-red-200 border-red-700/50";
    if (key === "QUESTION_READY") return "bg-yellow-900/50 text-yellow-200 border-yellow-700/50";
    if (key === "ACTION_SUGGESTED") return "bg-blue-900/50 text-blue-200 border-blue-700/50";
    return "bg-gray-800/70 text-gray-200 border-gray-700/60";
}

export function SophiaNotePage() {
    const [selectedDate, setSelectedDate] = useState<string>(today);
    const [availableDates, setAvailableDates] = useState<string[]>([]);
    const [notes, setNotes] = useState<SophiaSystemNote[]>([]);
    const [selectedNote, setSelectedNote] = useState<SophiaSystemNote | null>(null);
    const [generatorStatus, setGeneratorStatus] = useState<SophiaNoteGeneratorStatus>({
        last_generated_at: "",
        generator_status: "idle",
        last_trigger: "",
        empty_reasons: [],
        last_error: "",
    });
    const [loading, setLoading] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [responseText, setResponseText] = useState("");
    const [responding, setResponding] = useState(false);
    const [mind, setMind] = useState<MindDashboard>({
        focus_items: [],
        question_clusters: [],
        risk_alerts: [],
        working_log: [],
        active_tags: [],
        items: [],
    });
    const [mindBusyId, setMindBusyId] = useState<string>("");

    const canManualGenerate = useMemo(() => {
        if (typeof window === "undefined") return false;
        return window.localStorage.getItem("sophia_note_manual_generate") === "1";
    }, []);

    const loadStatusAndDates = async () => {
        const [status, dates, dashboard] = await Promise.all([
            memoryService.getSophiaNoteGeneratorStatus(),
            memoryService.listSophiaNoteDates(false),
            memoryService.getMindDashboard().catch((error) => {
                console.error("Failed to load mind dashboard:", error);
                return {
                    focus_items: [],
                    question_clusters: [],
                    risk_alerts: [],
                    working_log: [],
                    active_tags: [],
                    items: [],
                } as MindDashboard;
            }),
        ]);
        setGeneratorStatus(status);
        setAvailableDates(dates);
        setMind(dashboard);
        if (dates.length > 0 && !dates.includes(selectedDate)) {
            setSelectedDate(dates[0]);
        }
    };

    const loadNotesForDate = async (date: string) => {
        setLoading(true);
        try {
            const items = await memoryService.listSophiaNotesByDate(date, false);
            setNotes(items);
        } catch (error) {
            console.error("Failed to load Sophia notes:", error);
            setNotes([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void loadStatusAndDates();
    }, []);

    useEffect(() => {
        if (!selectedDate) return;
        void loadNotesForDate(selectedDate);
    }, [selectedDate]);

    const handleRefresh = async () => {
        await loadStatusAndDates();
        await loadNotesForDate(selectedDate);
    };

    const handleGenerateNow = async () => {
        if (!canManualGenerate) return;
        setGenerating(true);
        try {
            await memoryService.triggerSophiaNoteGenerateNow("note_page_manual_trigger");
            await handleRefresh();
        } catch (error) {
            console.error("Failed to generate Sophia note:", error);
        } finally {
            setGenerating(false);
        }
    };

    const handleRespondToQuestion = async () => {
        if (!selectedNote?.linked_cluster_id || !responseText.trim()) return;
        setResponding(true);
        try {
            await chatService.addMessage({
                role: "user",
                content: responseText.trim(),
                context_tag: "question-queue",
                linked_cluster: selectedNote.linked_cluster_id,
                status: "normal",
            });
            setResponseText("");
            await handleRefresh();
        } catch (error) {
            console.error("Failed to send note response:", error);
        } finally {
            setResponding(false);
        }
    };

    const handleMindAction = async (
        itemId: string,
        action: "pin" | "boost" | "park" | "done",
    ) => {
        setMindBusyId(itemId);
        try {
            await memoryService.adjustMindItem(itemId, action);
            await handleRefresh();
        } catch (error) {
            console.error(`Failed to apply mind action (${action})`, error);
        } finally {
            setMindBusyId("");
        }
    };

    return (
        <div className="h-full w-full flex flex-col bg-[#1e1e1e] text-gray-200 font-sans relative">
            <header className="px-6 py-4 border-b border-[#333] flex justify-between items-center h-14 flex-shrink-0">
                <div className="flex items-center gap-2">
                    <h1 className="text-xl font-bold text-gray-100 tracking-tight">Sophia Note</h1>
                    <span className="text-xs text-gray-500 px-2 py-0.5 border border-[#333] rounded">
                        {selectedDate === today ? "Today" : selectedDate}
                    </span>
                </div>
                <div className="flex gap-2">
                    {canManualGenerate && (
                        <button
                            onClick={handleGenerateNow}
                            className="p-2 hover:bg-[#333] rounded text-blue-300 hover:text-blue-200 transition-colors text-xs font-bold flex items-center gap-1"
                            title="Generate Now"
                        >
                            <Sparkles size={14} />
                            지금 생성
                        </button>
                    )}
                    <button
                        onClick={handleRefresh}
                        className="p-2 hover:bg-[#333] rounded text-gray-400 transition-colors"
                        title="Refresh Notes"
                    >
                        <RefreshCw size={14} className={loading || generating ? "animate-spin" : ""} />
                    </button>
                </div>
            </header>

            <section className="px-6 py-3 border-b border-[#333]/70 bg-[#1a1a1a] text-xs text-gray-300 flex flex-wrap gap-x-6 gap-y-2">
                <div>
                    마지막 생성:{" "}
                    <span className="text-gray-100">{generatorStatus.last_generated_at || "확인 필요"}</span>
                </div>
                <div>
                    생성 상태:{" "}
                    <span className={generatorStatus.generator_status === "failed" ? "text-red-300" : "text-gray-100"}>
                        {generatorStatus.generator_status}
                    </span>
                </div>
                <div>
                    최근 트리거: <span className="text-gray-100">{generatorStatus.last_trigger || "확인 필요"}</span>
                </div>
                {generatorStatus.last_error && (
                    <div className="text-red-300 flex items-center gap-1">
                        <AlertTriangle size={12} />
                        {generatorStatus.last_error}
                    </div>
                )}
            </section>

            <div className="flex-1 flex overflow-hidden">
                <main className="flex-[0.72] flex flex-col min-w-0 border-r border-[#333] bg-[#1e1e1e]">
                    <div className="px-6 py-3 border-b border-[#333]/50 text-xs font-bold text-gray-500 uppercase tracking-widest flex items-center gap-2">
                        EPISODE STREAM (SYSTEM GENERATED)
                    </div>

                    <div className="flex-1 overflow-y-auto p-6 space-y-4">
                        <section className="mb-4 bg-[#17181a] border border-[#303135] rounded p-4">
                            <div className="flex items-center justify-between mb-3">
                                <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest">Mind</h2>
                                <div className="text-[10px] text-gray-500">감독 모드: 우선순위 교정만 허용</div>
                            </div>
                            <div className="grid grid-cols-1 gap-3">
                                {(mind.items || []).slice(0, 5).map((item) => (
                                    <div key={item.id} className="border border-[#333] rounded bg-[#202124] px-3 py-2">
                                        <div className="flex items-center justify-between gap-2">
                                            <div className="text-xs font-semibold text-gray-100 truncate">{item.title}</div>
                                            <div className="text-[10px] text-gray-400">P{item.priority}</div>
                                        </div>
                                        <div className="text-[11px] text-gray-400 mt-1">{item.summary_120}</div>
                                        <div className="mt-2 flex flex-wrap gap-1">
                                            <button
                                                onClick={() => void handleMindAction(item.id, "pin")}
                                                disabled={mindBusyId === item.id}
                                                className="text-[10px] px-2 py-0.5 rounded border border-[#3a3f50] text-gray-300 hover:bg-[#2f3440] disabled:opacity-50"
                                            >
                                                pin
                                            </button>
                                            <button
                                                onClick={() => void handleMindAction(item.id, "boost")}
                                                disabled={mindBusyId === item.id}
                                                className="text-[10px] px-2 py-0.5 rounded border border-[#3a3f50] text-gray-300 hover:bg-[#2f3440] disabled:opacity-50"
                                            >
                                                boost
                                            </button>
                                            <button
                                                onClick={() => void handleMindAction(item.id, "park")}
                                                disabled={mindBusyId === item.id}
                                                className="text-[10px] px-2 py-0.5 rounded border border-[#3a3f50] text-gray-300 hover:bg-[#2f3440] disabled:opacity-50"
                                            >
                                                park
                                            </button>
                                            <button
                                                onClick={() => void handleMindAction(item.id, "done")}
                                                disabled={mindBusyId === item.id}
                                                className="text-[10px] px-2 py-0.5 rounded border border-[#3a3f50] text-gray-300 hover:bg-[#2f3440] disabled:opacity-50"
                                            >
                                                done
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            {(mind.active_tags || []).length > 0 && (
                                <div className="mt-3 flex flex-wrap gap-1">
                                    {mind.active_tags.slice(0, 12).map((tag) => (
                                        <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded bg-[#252a35] border border-[#364158] text-[#9ec1ff]">
                                            #{tag}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </section>

                        {notes.length === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center text-center p-10">
                                <p className="text-gray-300 font-semibold mb-3">생성된 소피아 노트가 없습니다</p>
                                <p className="text-xs text-gray-500 mb-4">
                                    소피아가 아직 기록을 생성하지 못한 상태입니다.
                                </p>
                                <div className="space-y-2 text-xs text-gray-500 max-w-md">
                                    {(generatorStatus.empty_reasons || []).length > 0 ? (
                                        generatorStatus.empty_reasons.map((reason) => (
                                            <div key={reason} className="bg-[#232325] border border-[#333] rounded px-3 py-2">
                                                {reason}
                                            </div>
                                        ))
                                    ) : (
                                        <div className="bg-[#232325] border border-[#333] rounded px-3 py-2">원인 분석 중</div>
                                    )}
                                </div>
                                <div className="mt-4 flex gap-2">
                                    <button
                                        onClick={handleRefresh}
                                        className="px-4 py-2 bg-[#2b2b2f] hover:bg-[#35353a] text-gray-200 text-xs font-bold rounded transition-colors"
                                    >
                                        새로고침
                                    </button>
                                    {canManualGenerate && (
                                        <button
                                            onClick={handleGenerateNow}
                                            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded transition-colors"
                                        >
                                            지금 생성
                                        </button>
                                    )}
                                </div>
                            </div>
                        ) : (
                            notes.map((note) => (
                                <button
                                    key={`${note.id}-${note.created_at}`}
                                    onClick={() => setSelectedNote(note)}
                                    className="w-full text-left bg-[#252526] border border-[#333] rounded p-4 hover:border-blue-500/50 transition-colors cursor-pointer"
                                >
                                    <div className="flex justify-between items-start mb-2 gap-3">
                                        <h3 className="font-bold text-gray-100">{note.title}</h3>
                                        <span className="text-xs text-gray-500 font-mono shrink-0">
                                            {note.created_at ? new Date(note.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}
                                        </span>
                                    </div>
                                    <div className="flex flex-wrap gap-2 mb-3">
                                        {(note.source_events || []).slice(0, 3).map((event) => (
                                            <span key={event} className="text-[10px] text-cyan-200 bg-cyan-900/30 border border-cyan-800/60 px-2 py-0.5 rounded">
                                                {event}
                                            </span>
                                        ))}
                                        <span className={`text-[10px] border px-2 py-0.5 rounded ${badgeClass(note.badge)}`}>
                                            {note.badge || "INFO"}
                                        </span>
                                    </div>
                                    <p className="text-sm text-gray-300 line-clamp-2">{note.summary || note.body_markdown || "요약 없음"}</p>
                                </button>
                            ))
                        )}
                    </div>
                </main>

                <aside className="flex-[0.28] flex flex-col bg-[#1b1b1b]">
                    <div className="px-6 py-3 border-b border-[#333]/50 text-xs font-bold text-gray-500 uppercase tracking-widest flex items-center gap-2">
                        <Calendar size={12} />
                        ARCHIVE
                    </div>
                    <div className="flex-1 overflow-y-auto p-4 space-y-1">
                        {availableDates.length === 0 && (
                            <div className="text-center py-4 text-gray-500 text-xs">
                                소피아가 보관한 기록이 없습니다.
                            </div>
                        )}
                        {availableDates.map((date) => (
                            <button
                                key={date}
                                onClick={() => setSelectedDate(date)}
                                className={`
                                    w-full text-left flex items-center justify-between text-sm px-3 py-2 rounded transition-colors group
                                    ${selectedDate === date ? "bg-[#333] text-white" : "text-gray-400 hover:text-gray-200 hover:bg-[#2a2a2e]"}
                                `}
                            >
                                <span>{date}</span>
                                {selectedDate === date && <ChevronRight size={14} className="text-blue-500" />}
                            </button>
                        ))}
                    </div>
                </aside>
            </div>

            {selectedNote && (
                <div className="absolute inset-0 z-50 bg-black/60 backdrop-blur-sm flex justify-end">
                    <div className="w-[640px] h-full bg-[#1e1e1e] border-l border-[#333] shadow-2xl flex flex-col">
                        <div className="px-6 py-4 border-b border-[#333] flex justify-between items-start">
                            <div>
                                <h2 className="text-xl font-bold text-white pr-8">{selectedNote.title}</h2>
                                <p className="text-xs text-gray-500 mt-1">{selectedNote.created_at}</p>
                            </div>
                            <button onClick={() => setSelectedNote(null)} className="text-gray-500 hover:text-white transition-colors">
                                Close
                            </button>
                        </div>

                        <div className="flex-1 overflow-y-auto p-6 space-y-6">
                            <div className="flex flex-wrap gap-2">
                                {(selectedNote.source_events || []).map((event) => (
                                    <span key={event} className="text-xs text-cyan-200 bg-cyan-900/30 border border-cyan-800/60 px-2 py-1 rounded">
                                        {event}
                                    </span>
                                ))}
                                <span className={`text-xs border px-2 py-1 rounded ${badgeClass(selectedNote.badge)}`}>
                                    {selectedNote.badge || "INFO"}
                                </span>
                            </div>

                            <div>
                                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Summary</h3>
                                <p className="text-sm text-gray-200">{selectedNote.summary || "요약 없음"}</p>
                            </div>

                            <div>
                                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Body</h3>
                                <div className="text-sm text-gray-300 whitespace-pre-wrap leading-relaxed">
                                    {selectedNote.body_markdown || "본문 없음"}
                                </div>
                            </div>

                            {(selectedNote.actionables || []).length > 0 && (
                                <div>
                                    <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Actionables</h3>
                                    <div className="space-y-2">
                                        {selectedNote.actionables.map((action, idx) => (
                                            <div key={idx} className="text-xs bg-[#111] border border-[#333] rounded px-3 py-2 text-gray-300">
                                                {JSON.stringify(action)}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {selectedNote.linked_cluster_id && (
                                <div className="border-t border-[#333] pt-4">
                                    <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">질문에 답하기</h3>
                                    <textarea
                                        value={responseText}
                                        onChange={(e) => setResponseText(e.target.value)}
                                        className="w-full h-24 bg-[#111] border border-[#333] rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
                                        placeholder="이 질문에 대한 응답을 입력하세요."
                                    />
                                    <button
                                        onClick={handleRespondToQuestion}
                                        disabled={responding || !responseText.trim()}
                                        className="mt-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed rounded text-xs font-bold text-white"
                                    >
                                        {responding ? "전송 중..." : "응답 전송"}
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
