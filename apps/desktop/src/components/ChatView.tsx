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

export function ChatView() {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [inputText, setInputText] = useState("");
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        loadInitialMessages();
        const interval = setInterval(checkInbox, 3000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    const loadInitialMessages = async () => {
        // Load history (mock or file)
        // Load pending patches as Sophia's messages
        await checkInbox();
        
        if (messages.length === 0) {
            // Initial greeting if empty
            // setMessages([{
            //     id: 'welcome',
            //     sender: 'sophia',
            //     text: '안녕하세요, 주인님. 생각의 흐름을 정리해드릴까요?',
            //     timestamp: new Date()
            // }]);
        }
    };

    const checkInbox = async () => {
        const pendingItems = await inboxService.getPendingItems();
        
        // Convert pending items to messages if not already shown
        // In a real app, we'd have a 'delivered' state.
        // Here we just check if message id exists in state.
        
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
            // Call Sophia API
            // 1. Ingest (Create Episode) or use a default Session Episode?
            // For v0.1 simplification, we'll just hit /propose with a specific ID or create one on fly.
            // Let's assume we want to trigger a thought process:
            // Step A: Ingest (Ref: chat_ui)
            const ingestRes = await fetch("http://localhost:8090/ingest", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ref_uri: "chat_ui" })
            });
            const ingestData = await ingestRes.json();
            const epId = ingestData.episode_id;

            // Step B: Propose (Trigger Candidates)
            await fetch("http://localhost:8090/propose", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ episode_id: epId, text: text })
            });

            // Step C: Dispatch (Try to get a response?)
            // If Dispatch is successful, it might add to Inbox?
            // Currently InboxService reads from file.
            // We need the API to write to that file or we need to poll the API Status?
            
            // For now, let's just trigger Dispatch so if there is a message it goes to queue.
            // AND we need to simulate a response in UI if the system is "Thinking".
            
            // Temporary: We just rely on inbox polling.
            // But we need to make sure the backend WRITES to the inbox file or exposed via API.
            // Since backend uses HeartEngine, and HeartEngine uses MessageQueue.
            // We need a bridge.

        } catch (e) {
            console.error("Failed to send message to Sophia:", e);
        }
    };

    return (
        <div className="flex flex-col h-full bg-[#1e1e1e]">
            {/* Header */}
            {/* <div className="p-4 border-b border-[#333] bg-[#252526] flex items-center">
                <span className="text-gray-200 font-bold">Sophia Chat</span>
            </div> */}

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.map((msg) => (
                    <div 
                        key={msg.id} 
                        className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                        <div 
                            className={`max-w-[70%] rounded-lg p-3 text-sm leading-relaxed shadow-sm w-fit
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
            <div className="p-4 border-t border-[#333] bg-[#252526]">
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
                        placeholder="메시지 입력..."
                        className="flex-1 bg-[#1e1e1e] border border-[#333] rounded-full px-4 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                    />
                    <button 
                        onClick={() => handleSendMessage()}
                        className="bg-blue-600 hover:bg-blue-700 text-white rounded-full p-2 w-10 h-10 flex items-center justify-center transition-colors"
                    >
                        ➤
                    </button>
                </div>
            </div>
        </div>
    );
}
