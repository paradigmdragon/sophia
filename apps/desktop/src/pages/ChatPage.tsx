import { useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import { chatService, ChatMessage, WorkPackageItem } from "../lib/chatService";
import { ActivePanel, PanelTab } from "../components/ActivePanel";
import { LogDropModal } from "../components/LogDropModal";
import {
    BellRing,
    Brain,
    FolderTree,
    LayoutPanelTop,
    NotebookPen,
    PanelRightOpen,
    PenTool,
    Sprout,
    Trees,
    Wrench,
} from "lucide-react";

type ChatFilterId = "all" | "grove" | "canopy" | "questions" | "work" | "memo" | "roots" | "custom";

interface ChatFilter {
    id: ChatFilterId;
    label: string;
    icon: ComponentType<{ size?: number; className?: string }>;
    composeDefault: string;
}

const CHAT_FILTERS: ChatFilter[] = [
    { id: "all", label: "All", icon: FolderTree, composeDefault: "system" },
    { id: "grove", label: "Grove", icon: Sprout, composeDefault: "forest:grove" },
    { id: "canopy", label: "Canopy", icon: LayoutPanelTop, composeDefault: "forest:canopy" },
    { id: "questions", label: "Questions", icon: Brain, composeDefault: "question-queue" },
    { id: "work", label: "Work", icon: Wrench, composeDefault: "work" },
    { id: "memo", label: "Memo", icon: NotebookPen, composeDefault: "memo" },
    { id: "roots", label: "Roots", icon: Trees, composeDefault: "roots" },
];

function normalizeCustomTag(raw: string): string {
    const trimmed = raw.trim();
    if (!trimmed) return "";
    const normalized = trimmed
        .toLowerCase()
        .replace(/\s+/g, "-")
        .replace(/[^a-z0-9:_-]/g, "-")
        .replace(/-+/g, "-")
        .replace(/^-|-$/g, "");
    if (!normalized) return "";
    return normalized.includes(":") ? normalized : `forest:${normalized}`;
}

function matchesFilter(message: ChatMessage, filter: ChatFilterId, customContextTag: string): boolean {
    const tag = message.context_tag || "system";
    if (filter === "all") return true;
    if (filter === "custom") return customContextTag ? tag === customContextTag : true;
    if (filter === "grove") return tag === "forest" || tag.startsWith("forest:");
    if (filter === "canopy") return tag === "forest:canopy";
    if (filter === "questions") return tag === "question-queue";
    if (filter === "work") return tag === "work";
    if (filter === "memo") return tag === "memo";
    if (filter === "roots") return tag === "roots";
    return true;
}

export function ChatPage() {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [pendingMessages, setPendingMessages] = useState<ChatMessage[]>([]);
    const [workPackages, setWorkPackages] = useState<WorkPackageItem[]>([]);
    const [selectedWorkPackageId, setSelectedWorkPackageId] = useState<string | null>(null);
    const [selectedPacketText, setSelectedPacketText] = useState("");
    const [reportJsonInput, setReportJsonInput] = useState("");
    const [inputText, setInputText] = useState("");
    const [toastMessage, setToastMessage] = useState<string | null>(null);
    const [panelRefreshToken, setPanelRefreshToken] = useState(0);
    const [activeTab, setActiveTab] = useState<PanelTab>("notes");
    const [activeFilter, setActiveFilter] = useState<ChatFilterId>("all");
    const [composeContextTag, setComposeContextTag] = useState("system");
    const [customTopicInput, setCustomTopicInput] = useState("");
    const [customContextTag, setCustomContextTag] = useState("");
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const [isPanelOpen, setIsPanelOpen] = useState(window.innerWidth >= 1200);
    const [showPanelToggle, setShowPanelToggle] = useState(window.innerWidth < 1200);
    const [isLogModalOpen, setIsLogModalOpen] = useState(false);

    const visibleMessages = useMemo(
        () => messages.filter((msg) => matchesFilter(msg, activeFilter, customContextTag)),
        [messages, activeFilter, customContextTag]
    );

    const pendingCount = useMemo(
        () => pendingMessages.filter((msg) => msg.role === "sophia" && msg.status === "pending").length,
        [pendingMessages]
    );

    const topPendingMessage = useMemo(() => {
        const candidates = pendingMessages.filter((msg) => msg.role === "sophia" && msg.status === "pending");
        if (candidates.length === 0) return null;
        return [...candidates].sort((a, b) => (b.importance || 0) - (a.importance || 0))[0];
    }, [pendingMessages]);

    const openWorkPackages = useMemo(
        () => workPackages.filter((pkg) => pkg.status === "READY" || pkg.status === "IN_PROGRESS"),
        [workPackages]
    );

    const filterCounts = useMemo(() => {
        const base = {
            all: 0,
            grove: 0,
            canopy: 0,
            questions: 0,
            work: 0,
            memo: 0,
            roots: 0,
            custom: 0,
        };
        for (const msg of messages) {
            if (matchesFilter(msg, "all", customContextTag)) base.all += 1;
            if (matchesFilter(msg, "grove", customContextTag)) base.grove += 1;
            if (matchesFilter(msg, "canopy", customContextTag)) base.canopy += 1;
            if (matchesFilter(msg, "questions", customContextTag)) base.questions += 1;
            if (matchesFilter(msg, "work", customContextTag)) base.work += 1;
            if (matchesFilter(msg, "memo", customContextTag)) base.memo += 1;
            if (matchesFilter(msg, "roots", customContextTag)) base.roots += 1;
            if (matchesFilter(msg, "custom", customContextTag)) base.custom += 1;
        }
        return base;
    }, [messages, customContextTag]);

    const loadTimeline = async () => {
        try {
            const [timeline, pending, packages] = await Promise.all([
                chatService.getDailyLogs(undefined, 500),
                chatService.getPending(100),
                chatService.getWorkPackages("ALL"),
            ]);
            setMessages(timeline);
            setPendingMessages(pending);
            setWorkPackages(packages);
        } catch (error) {
            console.error("Failed to load timeline:", error);
        }
    };

    useEffect(() => {
        loadTimeline();
        const timer = window.setInterval(loadTimeline, 2000);
        return () => window.clearInterval(timer);
    }, []);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [visibleMessages]);

    useEffect(() => {
        const handleResize = () => {
            const isDesktop = window.innerWidth >= 1200;
            setShowPanelToggle(!isDesktop);
            if (isDesktop) setIsPanelOpen(true);
        };

        window.addEventListener("resize", handleResize);
        handleResize();
        return () => window.removeEventListener("resize", handleResize);
    }, []);

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "l") {
                e.preventDefault();
                setIsLogModalOpen(true);
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, []);

    const showToast = (message: string) => {
        setToastMessage(message);
        window.setTimeout(() => setToastMessage(null), 3000);
    };

    const handleSendMessage = async () => {
        if (!inputText.trim()) return;
        const text = inputText;
        setInputText("");

        try {
            const linkedNode = composeContextTag.startsWith("forest:") ? composeContextTag.split(":", 2)[1] : null;
            await chatService.sendMessage(text, composeContextTag, linkedNode);
            await loadTimeline();
            setPanelRefreshToken((prev) => prev + 1);
        } catch (error) {
            console.error("Failed to send message:", error);
            setInputText(text);
            showToast("메시지 전송 실패 (네트워크/API 확인 필요)");
        }
    };

    const handleMarkPendingRead = async (messageId: string) => {
        const updated = await chatService.markMessageRead(messageId);
        if (!updated) {
            showToast("읽음 처리 실패");
            return;
        }
        await loadTimeline();
    };

    const handleAckCluster = async (clusterId: string | null) => {
        if (!clusterId) return;
        const ok = await chatService.ackQuestion(clusterId);
        if (!ok) {
            showToast("질문 확인 처리 실패");
            return;
        }
        await loadTimeline();
    };

    const handleResolveCluster = async (clusterId: string | null) => {
        if (!clusterId) return;
        const ok = await chatService.resolveQuestion(clusterId);
        if (!ok) {
            showToast("질문 해결 처리 실패");
            return;
        }
        await loadTimeline();
    };

    const handleSelectWorkPackage = async (pkg: WorkPackageItem) => {
        setSelectedWorkPackageId(pkg.id);
        if (pkg.packet_text && pkg.packet_text.trim()) {
            setSelectedPacketText(pkg.packet_text);
            return;
        }
        const packet = await chatService.getWorkPacket(pkg.id);
        if (!packet) {
            showToast("패킷 조회 실패");
            return;
        }
        setSelectedPacketText(packet.packet_text);
    };

    const handleAckWorkPackage = async (id: string) => {
        const ok = await chatService.ackWorkPackage(id);
        if (!ok) {
            showToast("작업 확인 실패");
            return;
        }
        await loadTimeline();
    };

    const handleCompleteWorkPackage = async (id: string) => {
        const ok = await chatService.completeWorkPackage(id);
        if (!ok) {
            showToast("작업 완료 처리 실패");
            return;
        }
        await loadTimeline();
    };

    const handleSubmitWorkReport = async () => {
        if (!selectedWorkPackageId) {
            showToast("선택된 작업이 없습니다.");
            return;
        }
        let payload: {
            work_package_id?: string;
            status: "DONE" | "BLOCKED" | "FAILED";
            signals: Array<{ cluster_id: string; risk_score: number; evidence: string; linked_node?: string | null }>;
            artifacts: string[];
            notes: string;
        };
        try {
            payload = JSON.parse(reportJsonInput);
        } catch (error) {
            console.error(error);
            showToast("report JSON 파싱 실패");
            return;
        }
        const ok = await chatService.submitWorkReport(selectedWorkPackageId, payload);
        if (!ok) {
            showToast("IDE 보고 반영 실패");
            return;
        }
        setReportJsonInput("");
        await loadTimeline();
    };

    const handleFilterClick = (filterId: ChatFilterId) => {
        setActiveFilter(filterId);
        if (filterId === "custom") {
            if (customContextTag) setComposeContextTag(customContextTag);
            return;
        }
        const filter = CHAT_FILTERS.find((item) => item.id === filterId);
        if (filter) setComposeContextTag(filter.composeDefault);
    };

    const activateCustomTopic = () => {
        const tag = normalizeCustomTag(customTopicInput);
        if (!tag) {
            showToast("주제/노드 태그를 입력해 주세요.");
            return;
        }
        setCustomContextTag(tag);
        setComposeContextTag(tag);
        setActiveFilter("custom");
    };

    return (
        <div className="flex flex-row h-full w-full bg-[#1e1e1e] overflow-hidden relative">
            <div
                className={`
                    flex flex-col h-full border-r border-[#333] bg-[#1e1e1e] transition-all duration-300 relative z-10
                    ${showPanelToggle ? "w-full" : "w-[42%] min-w-[460px]"}
                `}
            >
                <div className="h-10 px-4 border-b border-[#333] flex justify-between items-center bg-[#252526] flex-shrink-0">
                    <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-gray-300">Sophia Timeline</span>
                        <span className="text-[10px] text-green-500 bg-[#333] px-1 rounded">Single Stream</span>
                    </div>

                    <div className="flex items-center gap-2">
                        <div className="text-[10px] text-gray-500">{messages.length} msgs</div>
                        <button
                            onClick={() => setIsLogModalOpen(true)}
                            className="p-1 rounded hover:bg-[#333] text-gray-400 hover:text-white"
                            title="New Log (Cmd+L)"
                        >
                            <PenTool size={14} />
                        </button>
                        {showPanelToggle && (
                            <button
                                onClick={() => setIsPanelOpen(!isPanelOpen)}
                                className={`p-1 rounded hover:bg-[#333] ${isPanelOpen ? "text-blue-400" : "text-gray-400"}`}
                            >
                                <PanelRightOpen size={16} />
                            </button>
                        )}
                    </div>
                </div>

                <div className="flex-1 min-h-0 flex">
                    <aside className="w-[170px] border-r border-[#333] bg-[#191a1d] p-2 overflow-y-auto">
                        {CHAT_FILTERS.map((filter) => {
                            const Icon = filter.icon;
                            const active = activeFilter === filter.id;
                            const count = filterCounts[filter.id];
                            return (
                                <button
                                    key={filter.id}
                                    onClick={() => handleFilterClick(filter.id)}
                                    className={`
                                        w-full flex items-center justify-between gap-2 px-2 py-2 rounded text-xs mb-1 transition-colors
                                        ${active ? "bg-[#2a2a2e] text-blue-300 border border-blue-800/60" : "text-gray-300 hover:bg-[#232428]"}
                                    `}
                                >
                                    <span className="flex items-center gap-2">
                                        <Icon size={14} />
                                        {filter.label}
                                    </span>
                                    <span className="text-[10px] text-gray-500">{count}</span>
                                </button>
                            );
                        })}

                        <div className="mt-3 pt-3 border-t border-[#2d2f35]">
                            <div className="text-[10px] text-gray-500 mb-2">이 주제로 대화하기</div>
                            <input
                                value={customTopicInput}
                                onChange={(e) => setCustomTopicInput(e.target.value)}
                                placeholder="SonE-analysis"
                                className="w-full bg-[#111214] border border-[#2e323a] rounded px-2 py-1.5 text-[11px] text-gray-200 outline-none focus:border-blue-500"
                            />
                            <button
                                onClick={activateCustomTopic}
                                className="w-full mt-2 bg-[#1d4ed8] hover:bg-[#2563eb] text-[11px] font-semibold rounded py-1.5 text-white"
                            >
                                Topic Filter ON
                            </button>
                            {customContextTag && (
                                <div className="mt-2 text-[10px] text-gray-500 break-all">{customContextTag}</div>
                            )}
                        </div>
                    </aside>

                    <div className="flex-1 min-h-0 flex flex-col">
                        <div className="px-3 py-2 border-b border-[#333] bg-[#202227] flex items-center justify-between">
                            <div className="text-[11px] text-gray-400">
                                Active Context: <span className="text-blue-300 font-mono">{composeContextTag}</span>
                            </div>
                            <div className="text-[10px] text-gray-500">DB: single timeline · UI: filtered views</div>
                        </div>

                        {pendingCount > 0 && topPendingMessage && (
                            <div className="mx-3 mt-2 rounded border border-amber-700/60 bg-amber-900/30 px-3 py-2 text-xs text-amber-200">
                                <div className="flex items-center justify-between gap-2">
                                    <div className="flex items-center gap-2">
                                        <BellRing size={14} />
                                        <span>대기 질문 {pendingCount}건 · 위험도 {Math.round((topPendingMessage.importance || 0) * 100)}%</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={() => handleFilterClick("questions")}
                                            className="rounded border border-amber-500/40 px-2 py-1 text-[11px] text-amber-100 hover:bg-amber-800/40"
                                        >
                                            전체 보기
                                        </button>
                                        <button
                                            onClick={() => handleMarkPendingRead(topPendingMessage.id)}
                                            className="rounded border border-amber-500/40 px-2 py-1 text-[11px] text-amber-100 hover:bg-amber-800/40"
                                        >
                                            읽음
                                        </button>
                                        {topPendingMessage.linked_cluster && (
                                            <>
                                                <button
                                                    onClick={() => handleAckCluster(topPendingMessage.linked_cluster)}
                                                    className="rounded border border-amber-500/40 px-2 py-1 text-[11px] text-amber-100 hover:bg-amber-800/40"
                                                >
                                                    확인
                                                </button>
                                                <button
                                                    onClick={() => handleResolveCluster(topPendingMessage.linked_cluster)}
                                                    className="rounded border border-amber-500/40 px-2 py-1 text-[11px] text-amber-100 hover:bg-amber-800/40"
                                                >
                                                    해결
                                                </button>
                                            </>
                                        )}
                                    </div>
                                </div>
                                <div className="mt-1 text-[11px] text-amber-100 line-clamp-2">
                                    {topPendingMessage.content}
                                </div>
                            </div>
                        )}

                        <div className="mx-3 mt-2 rounded border border-blue-900/60 bg-blue-950/30 px-3 py-2 text-xs text-blue-100">
                            <div className="flex items-center justify-between gap-2">
                                <span>작업 대기열 {openWorkPackages.length}건</span>
                                <span className="text-[10px] text-blue-200/80">IDE 수동 전달 전용</span>
                            </div>
                            <div className="mt-2 flex flex-wrap gap-2">
                                {openWorkPackages.slice(0, 5).map((pkg) => (
                                    <button
                                        key={pkg.id}
                                        onClick={() => handleSelectWorkPackage(pkg)}
                                        className={`
                                            rounded border px-2 py-1 text-[11px]
                                            ${selectedWorkPackageId === pkg.id
                                                ? "border-blue-400 bg-blue-800/40 text-blue-100"
                                                : "border-blue-700/50 bg-blue-900/20 text-blue-200 hover:bg-blue-800/30"}
                                        `}
                                    >
                                        {pkg.work_packet?.kind || "ANALYZE"} · {pkg.id.slice(0, 10)}
                                    </button>
                                ))}
                            </div>
                            {selectedWorkPackageId && (
                                <div className="mt-3 space-y-2">
                                    <pre className="max-h-44 overflow-auto rounded border border-blue-800/60 bg-[#0f172a] p-2 text-[11px] text-blue-100 whitespace-pre-wrap">
                                        {selectedPacketText || "패킷 로딩 중..."}
                                    </pre>
                                    <div className="flex flex-wrap gap-2">
                                        <button
                                            onClick={() => handleAckWorkPackage(selectedWorkPackageId)}
                                            className="rounded border border-cyan-600/60 px-2 py-1 text-[11px] text-cyan-100 hover:bg-cyan-800/30"
                                        >
                                            Ack
                                        </button>
                                        <button
                                            onClick={() => handleCompleteWorkPackage(selectedWorkPackageId)}
                                            className="rounded border border-green-600/60 px-2 py-1 text-[11px] text-green-100 hover:bg-green-800/30"
                                        >
                                            Complete
                                        </button>
                                    </div>
                                    <textarea
                                        value={reportJsonInput}
                                        onChange={(e) => setReportJsonInput(e.target.value)}
                                        placeholder='{"work_package_id":"...","status":"DONE","signals":[],"artifacts":[],"notes":""}'
                                        className="h-24 w-full rounded border border-blue-800/60 bg-[#0b1020] p-2 text-[11px] text-blue-100 outline-none focus:border-blue-500"
                                    />
                                    <button
                                        onClick={handleSubmitWorkReport}
                                        className="rounded border border-amber-600/60 px-2 py-1 text-[11px] text-amber-100 hover:bg-amber-800/30"
                                    >
                                        IDE 완료 JSON 반영
                                    </button>
                                </div>
                            )}
                        </div>

                        <div className="flex-1 overflow-y-auto p-3 space-y-3 custom-scrollbar">
                            {visibleMessages.length === 0 && (
                                <div className="flex flex-col items-center justify-center h-full text-gray-600 text-xs">
                                    <p>선택한 필터의 메시지가 없습니다.</p>
                                </div>
                            )}

                            {visibleMessages.map((msg) => {
                                const isUser = msg.role === "user";
                                return (
                                    <div key={msg.id} className={`flex flex-col gap-1 ${isUser ? "items-end" : "items-start"}`}>
                                        <div className="flex items-center gap-2 px-1">
                                            <span className={`text-[10px] font-mono ${isUser ? "text-blue-400" : "text-purple-400"}`}>
                                                {isUser ? "USER" : "SOPHIA"}
                                            </span>
                                            <span className="text-[10px] text-gray-600">
                                                {new Date(msg.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                                            </span>
                                            <span className="text-[10px] text-gray-500 font-mono">{msg.context_tag}</span>
                                            {msg.status !== "normal" && (
                                                <span
                                                    className={`
                                                        text-[10px] px-1 py-0.5 rounded border
                                                        ${msg.status === "pending"
                                                            ? "text-amber-300 border-amber-700/60 bg-amber-900/20"
                                                            : msg.status === "acknowledged" || msg.status === "read"
                                                                ? "text-cyan-300 border-cyan-700/60 bg-cyan-900/20"
                                                                : msg.status === "resolved"
                                                                    ? "text-green-300 border-green-700/60 bg-green-900/20"
                                                                    : "text-red-300 border-red-700/60 bg-red-900/20"}
                                                    `}
                                                >
                                                    {msg.status}
                                                </span>
                                            )}
                                        </div>

                                        <div
                                            className={`
                                                max-w-[90%] rounded border p-3 text-sm shadow-sm
                                                ${isUser
                                                    ? "bg-[#222] border-[#333] text-gray-200"
                                                    : msg.status === "pending"
                                                        ? "bg-[#3a2a12] border-amber-700/50 text-amber-100"
                                                        : msg.status === "acknowledged" || msg.status === "read"
                                                            ? "bg-[#12303a] border-cyan-700/50 text-cyan-100"
                                                            : msg.status === "resolved"
                                                                ? "bg-[#193323] border-green-700/50 text-green-100"
                                                        : "bg-[#252526] border-[#333] text-gray-300"}
                                            `}
                                            style={{ wordBreak: "keep-all", overflowWrap: "break-word", whiteSpace: "pre-wrap" }}
                                        >
                                            <div className="font-sans leading-relaxed text-[13px]">{msg.content}</div>
                                        </div>
                                    </div>
                                );
                            })}
                            <div ref={messagesEndRef} />
                        </div>

                        <div className="p-3 border-t border-[#333] bg-[#252526]">
                            <div className="bg-[#1e1e1e] border border-[#333] rounded flex flex-col focus-within:border-blue-500/50 transition-colors">
                                <div className="flex items-center p-1">
                                    <input
                                        type="text"
                                        value={inputText}
                                        onChange={(e) => setInputText(e.target.value)}
                                        onKeyDown={(e) => {
                                            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                                                e.preventDefault();
                                                handleSendMessage();
                                            }
                                        }}
                                        placeholder="메시지를 입력하세요..."
                                        className="flex-1 bg-transparent px-2 py-2 text-sm text-white focus:outline-none min-h-[40px]"
                                        autoFocus
                                    />
                                    <button onClick={handleSendMessage} className="text-blue-500 hover:bg-[#333] p-2 rounded transition-colors">
                                        ➤
                                    </button>
                                </div>
                            </div>
                            <div className="text-[10px] text-gray-600 mt-1 flex justify-between px-1">
                                <span>Enter to send, Shift+Enter for newline</span>
                                <span>Single Timeline + Context Filter</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div
                className={`
                    h-full bg-[#1e1e1e] z-20 transition-transform duration-300
                    ${showPanelToggle
                        ? `fixed inset-y-0 right-0 w-[80%] max-w-[400px] border-l border-[#333] shadow-2xl transform ${isPanelOpen ? "translate-x-0" : "translate-x-full"}`
                        : "flex-1 border-l border-[#333] relative"}
                `}
            >
                <ActivePanel activeTab={activeTab} onTabChange={setActiveTab} refreshToken={panelRefreshToken} />
            </div>

            {showPanelToggle && isPanelOpen && (
                <div className="fixed inset-0 bg-black/50 z-10" onClick={() => setIsPanelOpen(false)} />
            )}

            <LogDropModal
                isOpen={isLogModalOpen}
                onClose={() => setIsLogModalOpen(false)}
                onSaveSuccess={(filename) => {
                    console.log(`Log saved: ${filename}`);
                    alert(`Log saved: ${filename}\nRun ingest to see in Audit/Memory.`);
                }}
            />

            {toastMessage && (
                <div className="fixed right-4 bottom-4 z-40 rounded border border-yellow-700/60 bg-yellow-900/90 px-3 py-2 text-xs text-yellow-100 shadow-lg">
                    {toastMessage}
                </div>
            )}
        </div>
    );
}
