import { useState, useEffect } from "react";
import { SourceExplorer } from "../components/SourceExplorer";
import { MarkdownEditor } from "../components/MarkdownEditor";
import { Timeline } from "../components/Timeline";
import { chatService, ChatMessage } from "../lib/chatService";

export function NotePage() {
    const [messages, setMessages] = useState<ChatMessage[]>([]);

    useEffect(() => {
        // Load logs for Timeline
        chatService.getDailyLogs().then(setMessages);
        
        // Watch for updates
        const stop = chatService.watchLogs(setMessages);
        return () => stop();
    }, []);

    return (
        <div className="h-full w-full flex bg-[#1e1e1e]">
            {/* Left Pane: Sources */}
            <div className="w-64 border-r border-[#333] hidden md:block">
                <SourceExplorer />
            </div>

            {/* Center Pane: Editor & Journal */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Top: Editor */}
                <div className="flex-1 border-b border-[#333] overflow-hidden relative">
                    {/* MarkdownEditor doesn't support className prop based on inspection, wrapping it or assuming it takes full height */}
                    <div className="h-full w-full">
                         <MarkdownEditor />
                    </div>
                </div>

                {/* Bottom: Journal / Timeline */}
                <div className="h-[40%] flex flex-col bg-[#1e1e1e]">
                   <div className="px-4 py-2 border-b border-[#333] bg-[#252526] text-xs font-bold text-gray-400 uppercase tracking-widest flex justify-between">
                        <span>Journal Stream</span>
                        <span>{new Date().toLocaleDateString()}</span>
                   </div>
                   <div className="flex-1 overflow-y-auto">
                        <Timeline messages={messages} />
                   </div>
                </div>
            </div>
        </div>
    );
}
