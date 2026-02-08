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

    return (
        <div className="h-full w-full bg-[#1e1e1e] flex flex-col">
            {/* Header */}
            <div className="p-4 border-b border-[#333] flex justify-between items-center bg-[#252526]">
                <h1 className="text-sm font-bold text-gray-200">Sophia Chat</h1>
                <div className="text-xs text-gray-500">
                    Topic: <span className="text-blue-400">#General</span>
                </div>
            </div>
            
            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                 {messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-gray-500 text-sm">
                        <p>소피아와 대화를 시작하세요.</p>
                    </div>
                )}
                {messages.map((msg) => (
                    <div 
                        key={msg.message_id} 
                        className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                        <div 
                            className={`max-w-[70%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm
                            ${msg.role === 'user' 
                                ? 'bg-blue-600 text-white rounded-br-none' 
                                : 'bg-[#2d2d2d] text-gray-200 rounded-bl-none border border-[#333]'
                            }`}
                        >
                            <div className="whitespace-pre-wrap">{msg.content}</div>
                            <div className="text-[10px] opacity-50 text-right mt-1">
                                {new Date(msg.timestamp).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}
                            </div>
                        </div>
                    </div>
                ))}
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
