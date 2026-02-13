import { useState, useEffect, useRef } from "react";
import { chatService, ChatMessage } from "../lib/chatService";
import { ActivePanel, PanelTab } from "../components/ActivePanel";
import { LogDropModal } from "../components/LogDropModal";
import { PanelRightOpen, PenTool } from "lucide-react";

export function ChatPage() {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [inputText, setInputText] = useState("");
    const [toastMessage, setToastMessage] = useState<string | null>(null);
    const [panelRefreshToken, setPanelRefreshToken] = useState(0);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Panel State
    const [activeTab, setActiveTab] = useState<PanelTab>("notes");
    
    // Watch logs on mount
    useEffect(() => {
        chatService.getDailyLogs().then(msgs => {
            setMessages(msgs);
            scrollToBottom();
        });

        const stopDevice = chatService.watchLogs((newMessages) => {
            setMessages(newMessages); 
            // Auto-focus logic based on latest message
            const lastMsg = newMessages[newMessages.length - 1];
            if (lastMsg && lastMsg.role === 'sophia') {
                if (lastMsg.content.includes("memory.append")) setActiveTab("memory");
                if (lastMsg.content.includes("audit")) setActiveTab("audit");
            }
        });

        return () => stopDevice();
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    const handleSendMessage = async () => {
        if (!inputText.trim()) return;
        const text = inputText;
        setInputText(""); 
        try {
            await chatService.sendMessage(text);
            try {
                await chatService.appendUserMessageToMemory(text, "General");
                setPanelRefreshToken(prev => prev + 1);
            } catch (appendError) {
                console.error("Chat memory append failed:", appendError);
                setToastMessage("메모리 기록 실패 (채팅은 정상 전송됨)");
                window.setTimeout(() => setToastMessage(null), 3000);
            }
        } catch (error) {
            console.error("Failed to send message:", error);
            setInputText(text);
        }
    };

    // Responsive & Panel State
    const [isPanelOpen, setIsPanelOpen] = useState(window.innerWidth >= 1200);
    const [showPanelToggle, setShowPanelToggle] = useState(window.innerWidth < 1200);

    useEffect(() => {
        const handleResize = () => {
            const isDesktop = window.innerWidth >= 1200;
            setShowPanelToggle(!isDesktop);
            if (isDesktop) setIsPanelOpen(true);
        };
        
        window.addEventListener('resize', handleResize);
        handleResize(); // Init
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    const [committedIds, setCommittedIds] = useState<Set<string>>(new Set());
    const handleCommit = async (msgId: string, contextId?: string) => {
        if (!contextId) return;
        setCommittedIds(prev => new Set(prev).add(msgId));
        console.log(`[Shin] Committing: ${contextId}`);
    };

    // Log Drop Modal State
    const [isLogModalOpen, setIsLogModalOpen] = useState(false);

    // Global Shortcut for Log Modal (Cmd+L inside this page)
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'l') {
                e.preventDefault();
                setIsLogModalOpen(true);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, []);

    return (
        <div className="flex flex-row h-full w-full bg-[#1e1e1e] overflow-hidden relative">
            {/* Left Column: Chat */}
            <div className={`
                flex flex-col h-full border-r border-[#333] bg-[#1e1e1e] transition-all duration-300 relative z-10
                ${showPanelToggle ? 'w-full' : 'w-[42%] min-w-[400px]'}
            `}>
                
                {/* Header */}
                <div className="h-10 px-4 border-b border-[#333] flex justify-between items-center bg-[#252526] flex-shrink-0">
                    <div className="flex items-center gap-2">
                         <span className="text-xs font-bold text-gray-300">IDE Assistant</span>
                         <span className="text-[10px] text-gray-500 bg-[#333] px-1 rounded">v1.1</span>
                    </div>
                    
                    <div className="flex items-center gap-2">
                        <div className="text-[10px] text-gray-500">
                            {messages.length} msgs
                        </div>
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
                                className={`p-1 rounded hover:bg-[#333] ${isPanelOpen ? 'text-blue-400' : 'text-gray-400'}`}
                            >
                                <PanelRightOpen size={16} />
                            </button>
                        )}
                    </div>
                </div>
                
                {/* Messages Area */}
                <div className="flex-1 overflow-y-auto p-2 space-y-3 custom-scrollbar">
                     {messages.length === 0 && (
                        <div className="flex flex-col items-center justify-center h-full text-gray-600 text-xs">
                            <p>Ready to assist.</p>
                        </div>
                    )}
                    {messages.map((msg) => {
                        const isSophia = msg.role === 'sophia';
                        const isCommitted = committedIds.has(msg.message_id);

                        return (
                        <div 
                            key={msg.message_id} 
                            className={`flex flex-col gap-1 group ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                        >
                            {/* Sender Label */}
                            <div className="flex items-center gap-2 px-1">
                                <span className={`text-[10px] font-mono ${msg.role === 'user' ? 'text-blue-400' : 'text-yellow-500'}`}>
                                    {msg.role === 'user' ? 'USER' : 'SOPHIA'}
                                </span>
                                <span className="text-[10px] text-gray-600">
                                    {new Date(msg.timestamp).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}
                                </span>
                            </div>

                            {/* Message Card */}
                            <div 
                                className={`
                                    max-w-[85%] rounded border p-3 text-sm shadow-sm relative
                                    ${msg.role === 'user' 
                                        ? 'bg-[#222] border-[#333] text-gray-200' 
                                        : isCommitted
                                            ? 'bg-[#2a2a2e] border-yellow-900/30 text-gray-100 shadow-[0_0_10px_rgba(234,179,8,0.05)]'
                                            : 'bg-[#252526] border-[#333] text-gray-300'
                                    }
                                `}
                                style={{
                                    wordBreak: 'keep-all',
                                    overflowWrap: 'break-word',
                                    whiteSpace: 'pre-wrap'
                                }}
                            >
                                <div className="font-sans leading-relaxed text-[13px]">
                                    {msg.content}
                                </div>
                                
                                {/* Tools / Actions */}
                                {isSophia && (
                                    <div className="absolute right-2 bottom-1 opacity-0 group-hover:opacity-100 transition-opacity flex gap-2">
                                         {!isCommitted ? (
                                            <button
                                                onClick={() => handleCommit(msg.message_id, msg.message_id)} 
                                                className="text-gray-500 hover:text-yellow-500"
                                                title="Commit to Memory"
                                            >
                                                <span className="text-xs">💾</span>
                                            </button>
                                         ) : (
                                            <span className="text-xs text-yellow-600">Locked</span>
                                         )}
                                    </div>
                                )}
                            </div>
                        </div>
                        );
                    })}
                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area (IDE Style) */}
                <div className="p-3 border-t border-[#333] bg-[#252526]">
                    <div className="bg-[#1e1e1e] border border-[#333] rounded flex flex-col focus-within:border-blue-500/50 transition-colors">
                        <div className="flex items-center p-1">
                             <input 
                                type="text" 
                                value={inputText}
                                onChange={(e) => setInputText(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                                        e.preventDefault();
                                        handleSendMessage();
                                    }
                                }}
                                placeholder="Type a message or /command..."
                                className="flex-1 bg-transparent px-2 py-2 text-sm text-white focus:outline-none min-h-[40px]"
                                autoFocus
                            />
                            <button 
                                onClick={handleSendMessage}
                                className="text-blue-500 hover:bg-[#333] p-2 rounded transition-colors"
                            >
                                ➤
                            </button>
                        </div>
                    </div>
                    <div className="text-[10px] text-gray-600 mt-1 flex justify-between px-1">
                        <span>Enter to send, Shift+Enter for newline</span>
                        <span>IDE Mode</span>
                    </div>
                </div>
            </div>

            {/* Right Column: Active Panel */}
            <div className={`
                h-full bg-[#1e1e1e] z-20 transition-transform duration-300
                ${showPanelToggle 
                    ? `fixed inset-y-0 right-0 w-[80%] max-w-[400px] border-l border-[#333] shadow-2xl transform ${isPanelOpen ? 'translate-x-0' : 'translate-x-full'}` 
                    : 'flex-1 border-l border-[#333] relative'
                }
            `}>
                <ActivePanel 
                    activeTab={activeTab} 
                    onTabChange={setActiveTab} 
                    refreshToken={panelRefreshToken}
                />
            </div>
            
             {/* Backdrop for mobile drawer */}
             {showPanelToggle && isPanelOpen && (
                <div 
                    className="fixed inset-0 bg-black/50 z-10"
                    onClick={() => setIsPanelOpen(false)}
                />
            )}
            {/* Log Drop Modal */}
            <LogDropModal 
                isOpen={isLogModalOpen} 
                onClose={() => setIsLogModalOpen(false)} 
                onSaveSuccess={(filename) => {
                    console.log(`Log saved: ${filename}`);
                    // Optional: Show a toast? For now just console log.
                    // Ideally we might want to refresh messages if there was an ingest? 
                    // But ingest is manual for now.
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
