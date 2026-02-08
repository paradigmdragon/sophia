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

    const handleSendMessage = () => {
        if (!inputText.trim()) return;

        const newUserMessage: ChatMessage = {
            id: `usr_${Date.now()}`,
            sender: 'user',
            text: inputText,
            timestamp: new Date()
        };

        setMessages(prev => [...prev, newUserMessage]);
        setInputText("");

        // Mock Sophia thinking/reply logic (or just wait for next signal)
        // For v0.1, we just log the user input (in manager) -> Generate Signal -> Inbox -> Sophia Message
        // But here we are just UI. The backend (Manager) should be listening to this input.
        // We need a way to send input to Manager.
        // For v0.1, let's assume 'chat logs' are written to file and Manager picks them up?
        // Or we use tauri invoke to send message.
        
        // TODO: Implement 'send_message' command. 
        // For now, just a valid UI.
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
                            className={`max-w-[70%] rounded-lg p-3 text-sm leading-relaxed shadow-sm
                            ${msg.sender === 'user' 
                                ? 'bg-blue-600 text-white rounded-br-none' 
                                : 'bg-[#2d2d2d] text-gray-200 rounded-bl-none border border-[#333]'
                            }`}
                        >
                            {msg.text}
                            <div className="text-[10px] opacity-50 text-right mt-1">
                                {msg.timestamp.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}
                            </div>
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
                        onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                        placeholder="메시지 입력..."
                        className="flex-1 bg-[#1e1e1e] border border-[#333] rounded-full px-4 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
                    />
                    <button 
                        onClick={handleSendMessage}
                        className="bg-blue-600 hover:bg-blue-700 text-white rounded-full p-2 w-10 h-10 flex items-center justify-center transition-colors"
                    >
                        ➤
                    </button>
                </div>
            </div>
        </div>
    );
}
