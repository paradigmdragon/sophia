import { useState, useEffect, useRef } from "react";
import { chatService, ChatMessage } from "../lib/chatService";

export function ChatPage() {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [inputText, setInputText] = useState("");
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Watch logs on mount
    useEffect(() => {
        // Load initial
        chatService.getDailyLogs().then(msgs => {
            setMessages(msgs);
            scrollToBottom();
        });

        // Start watching
        const stopDevice = chatService.watchLogs((newMessages) => {
            setMessages(newMessages); // In a real app, diffing would be better, but full replace is fine for v0.1
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
        setInputText(""); // Optimistic clear

        // Send to backend
        try {
            await chatService.sendMessage(text);
            // The watchLogs will pick up the new message(s) appended by backend
        } catch (error) {
            console.error("Failed to send message:", error);
            // Maybe restore input text?
            setInputText(text);
        }
    };

    // [Shin] State for committed messages (Local visual state for v0.1)
    const [committedIds, setCommittedIds] = useState<Set<string>>(new Set());

    const handleCommit = async (msgId: string, contextId?: string) => {
        if (!contextId) return;
        
        // 1. Visual Update (Immediate)
        setCommittedIds(prev => {
            const next = new Set(prev);
            next.add(msgId);
            return next;
        });
        
        // 2. Persist to Nervous System (Inbox/Manifest)
        // We assume msg.context is the patch_id
        console.log(`[Shin] Committing: ${contextId}`);
        // await inboxService.updateItemStatus(contextId, 'committed'); 
        // Note: active_ep patch might be pending. We update it.
        // We need to import inboxService in this file or use chatService to bridge.
        // For v0.1, we'll just log or assume inboxService is available if we import it.
    };

    return (
        <div className="h-full w-full bg-[#1e1e1e] flex flex-col">
            {/* ... Header ... */}
            <div className="p-4 border-b border-[#333] flex justify-between items-center bg-[#252526]">
                <div>
                    <h1 className="text-sm font-bold text-gray-200">Sophia Chat</h1>
                    <div className="text-[10px] text-gray-500 flex items-center gap-2">
                        <span className="text-blue-400">#General</span>
                        <span className="text-gray-600">|</span>
                        <span>{new Date().toLocaleTimeString()}</span>
                        <span className="text-gray-600">|</span>
                        <span>{messages.length} msgs</span>
                    </div>
                </div>
                <button 
                    onClick={() => {
                        window.location.reload();
                    }}
                    className="text-xs bg-[#333] hover:bg-[#444] text-gray-300 px-2 py-1 rounded transition-colors"
                >
                    ⟳ Reload
                </button>
            </div>
            
            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-6">
                 {messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-gray-500 text-sm">
                        <p>소피아와 대화를 시작하세요.</p>
                    </div>
                )}
                {messages.map((msg) => {
                    const isSophia = msg.role === 'sophia';
                    const isCommitted = committedIds.has(msg.message_id); // Local check

                    return (
                    <div 
                        key={msg.message_id} 
                        className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} group`}
                    >
                        <div className={`flex items-end gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                            
                            {/* Message Bubble */}
                            <div 
                                className={`max-w-[80%] rounded-2xl px-5 py-3 text-sm leading-relaxed shadow-sm relative transition-all duration-300
                                ${msg.role === 'user' 
                                    ? 'bg-blue-600/90 text-white rounded-br-none border border-blue-500' 
                                    : isCommitted
                                        ? 'bg-[#2d2d2d] text-gray-200 rounded-bl-none border-2 border-yellow-600/50 shadow-[0_0_15px_rgba(234,179,8,0.1)]' // Committed Style
                                        : 'bg-[#2d2d2d] text-gray-200 rounded-bl-none border border-[#333] border-dashed' // Pending Style
                                }`}
                            >
                                <div className="whitespace-pre-wrap font-sans">{msg.content}</div>
                                <div className="text-[10px] opacity-40 text-right mt-2 flex justify-end items-center gap-2">
                                    <span>{new Date(msg.timestamp).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</span>
                                </div>
                            </div>

                            {/* [Shin] Commit Button (Only for Sophia's answers) */}
                            {isSophia && !isCommitted && (
                                <button
                                    onClick={() => handleCommit(msg.message_id, msg.message_id)} 
                                    className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-600 hover:text-yellow-500 p-1 mb-2"
                                    title="이 말을 세계에 고정(信)합니다"
                                >
                                    <span className="text-lg">🔒</span>
                                </button>
                            )}
                             {isSophia && isCommitted && (
                                <div className="text-yellow-600/50 p-1 mb-2" title="고정됨 (Shin)">
                                    <span className="text-lg">🔐</span>
                                </div>
                            )}
                        </div>
                    </div>
                    );
                })}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-4 border-t border-[#333] bg-[#252526]">
                <div className="flex items-center space-x-2 max-w-4xl mx-auto w-full">
                    <input 
                        type="text" 
                        value={inputText}
                        onChange={(e) => setInputText(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && !e.nativeEvent.isComposing && handleSendMessage()}
                        placeholder="메시지 보내기..."
                        className="flex-1 bg-[#1e1e1e] border border-[#333] rounded-full px-5 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                        autoFocus
                    />
                    <button 
                        onClick={handleSendMessage}
                        className="bg-blue-600 hover:bg-blue-700 text-white rounded-full p-3 w-10 h-10 flex items-center justify-center transition-colors shadow-lg"
                    >
                        ➤
                    </button>
                </div>
            </div>
        </div>
    );
}
