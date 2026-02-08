
import { useState, useEffect } from "react";
import { Timeline } from "../components/Timeline";
import { chatService, ChatMessage } from "../lib/chatService";

// Sophia Note Page: "Archive" / "Viewer"
// - Today's Records (Timeline)
// - Past Records (Date List)

export function SophiaNotePage() {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    
    // For now, we only load today's logs for the "Today" section.
    // In the future, we'll load past dates.
    useEffect(() => {
        chatService.getDailyLogs().then(setMessages);
        const stop = chatService.watchLogs(setMessages);
        return () => stop();
    }, []);

    // Placeholder for Past Records
    // We would need to scan 'logs/chat/' directory to find other files.
    // user instruction: "Date based record list"
    
    return (
        <div className="h-full w-full flex flex-col bg-[#1e1e1e] text-gray-200 font-sans">
            {/* Header */}
            <header className="px-8 py-6 border-b border-[#333] flex justify-between items-center">
                <h1 className="text-2xl font-serif text-gray-100">Sophia Note</h1>
                <span className="text-xs text-gray-500 uppercase tracking-widest">Archive</span>
            </header>

            <div className="flex-1 flex overflow-hidden">
                {/* Main Content: Today's Records (Timeline) */}
                <main className="flex-1 flex flex-col min-w-0 border-r border-[#333]">
                    <div className="px-6 py-3 border-b border-[#333] bg-[#252526] text-xs font-bold text-gray-400 uppercase tracking-widest">
                        Today's Records
                    </div>
                    <div className="flex-1 overflow-y-auto bg-[#1e1e1e]">
                        <Timeline messages={messages} />
                    </div>
                </main>

                {/* Sidebar: Past Records */}
                <aside className="w-64 flex flex-col bg-[#1b1b1b]">
                    <div className="px-6 py-3 border-b border-[#333] bg-[#252526] text-xs font-bold text-gray-400 uppercase tracking-widest">
                        Past Records
                    </div>
                    <div className="flex-1 overflow-y-auto p-4 space-y-2">
                        {/* Placeholder list */}
                        <div className="text-sm text-gray-500 hover:text-gray-300 cursor-pointer p-2 rounded hover:bg-[#333] transition-colors">
                            2026-02-07
                        </div>
                        <div className="text-sm text-gray-500 hover:text-gray-300 cursor-pointer p-2 rounded hover:bg-[#333] transition-colors">
                            2026-02-06
                        </div>
                        <div className="text-sm text-gray-600 italic p-2">
                            (More history...)
                        </div>
                    </div>
                </aside>
            </div>
        </div>
    );
}
