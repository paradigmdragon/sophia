import { useState, useEffect, useRef } from "react";
// import { getCurrentWebview } from "@tauri-apps/api/webview";
import { inboxService } from "../lib/inboxService";

interface ChatMessage {
    id: string;
    sender: 'user' | 'sophia';
    text: string;
    timestamp: Date;
    context?: string; // patch_id or context snippet
}

interface ChatOverlayProps {
    isOpen: boolean;
    onClose: () => void;
}

export function ChatOverlay({ isOpen, onClose }: ChatOverlayProps) {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [inputText, setInputText] = useState("");
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (isOpen) {
            loadInitialMessages();
        }
    }, [isOpen]);

    useEffect(() => {
        const interval = setInterval(checkInbox, 3000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, isOpen]);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    const loadInitialMessages = async () => {
        // Load history (mock or file)
        // Load pending patches as Sophia's messages
        await checkInbox();
    };

    const checkInbox = async () => {
        const pendingItems = await inboxService.getPendingItems();
        
        const newMessages: ChatMessage[] = [];
        
        pendingItems.forEach(item => {
            if (!messages.some(m => m.context === item.id)) {
                newMessages.push({
                    id: `msg_${item.id}`,
                    sender: 'sophia',
                    text: item.message, // The Question
                    timestamp: new Date(item.timestamp),
                    context: item.id
                });
            }
        });

        if (newMessages.length > 0) {
            setMessages(prev => [...prev, ...newMessages].sort((a,b) => a.timestamp.getTime() - b.timestamp.getTime()));
        }
    };

    const handleSendMessage = async () => {
        if (!inputText.trim()) return;

        const text = inputText;
        const newUserMessage: ChatMessage = {
            id: `usr_${Date.now()}`,
            sender: 'user',
            text: text,
            timestamp: new Date()
        };

        setMessages(prev => [...prev, newUserMessage]);
        setInputText("");
        
        try {
            const ingestRes = await fetch("http://localhost:8090/ingest", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ref_uri: "chat_overlay" })
            });
            const ingestData = await ingestRes.json();
            const epId = ingestData.episode_id;

            await fetch("http://localhost:8090/propose", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ episode_id: epId, text: text })
            });

        } catch (e) {
            console.error("Failed to send message to Sophia:", e);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed bottom-20 right-6 w-96 h-[600px] bg-[#1e1e1e] border border-[#333] shadow-2xl rounded-xl overflow-hidden flex flex-col z-50 animate-fade-in-up">
            {/* Header */}
            <div className="px-4 py-3 border-b border-[#333] bg-[#252526] flex justify-between items-center">
                <span className="text-sm font-bold text-gray-200">Sophia Chat</span>
                <button onClick={onClose} className="text-gray-400 hover:text-white">✕</button>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-[#1e1e1e]">
                 {messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-gray-500 text-xs">
                        <p>소피아와 대화를 시작하세요.</p>
                    </div>
                )}
                {messages.map((msg) => (
                    <div 
                        key={msg.id} 
                        className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                        <div 
                            className={`max-w-[85%] rounded-lg p-3 text-sm leading-relaxed shadow-sm w-fit
                            ${msg.sender === 'user' 
                                ? 'bg-blue-600 text-white rounded-br-none' 
                                : 'bg-[#2d2d2d] text-gray-200 rounded-bl-none border border-[#333]'
                            }`}
                        >
                            <span className="break-words">{msg.text}</span>
                            <span className="text-[10px] opacity-50 ml-2 select-none float-right mt-1.5 align-bottom">
                                {msg.timestamp.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}
                            </span>
                            <div className="clear-both"></div>
                        </div>
                    </div>
                ))}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-3 border-t border-[#333] bg-[#252526]">
                <div className="flex items-center space-x-2">
                    <input 
                        type="text" 
                        value={inputText}
                        onChange={(e) => setInputText(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.nativeEvent.isComposing) return;
                            if (e.key === 'Enter') {
                                e.preventDefault();
                                handleSendMessage();
                            }
                        }}
                        placeholder="Ask Sophia..."
                        className="flex-1 bg-[#252526] border border-[#444] rounded-full px-4 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                        autoFocus
                    />
                    <button 
                        onClick={handleSendMessage}
                        className="bg-blue-600 hover:bg-blue-700 text-white rounded-full p-2 w-9 h-9 flex items-center justify-center transition-colors shadow-lg"
                    >
                        ➤
                    </button>
                </div>
            </div>
        </div>
    );
}
