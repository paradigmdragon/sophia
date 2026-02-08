
import { ChatMessage } from "../lib/chatService";

interface TimelineProps {
    messages: ChatMessage[];
    onNoteChange?: (id: string, content: string) => void;
}

export function Timeline({ messages }: TimelineProps) {
    // Group messages by time proximity or just list them?
    // User wants "Timeline View" - [Date Header] - [Block] - [Note]
    
    // Simple grouping by Date
    const grouped = messages.reduce((acc, msg) => {
        const date = new Date(msg.timestamp).toLocaleDateString();
        if (!acc[date]) acc[date] = [];
        acc[date].push(msg);
        return acc;
    }, {} as Record<string, ChatMessage[]>);

    return (
        <div className="flex flex-col space-y-8 p-8 max-w-3xl mx-auto w-full">
            {Object.entries(grouped).map(([date, msgs]) => (
                <div key={date} className="space-y-6">
                    {/* Date Header */}
                    <div className="flex items-center space-x-4">
                        <div className="h-px bg-gray-700 flex-1"></div>
                        <span className="text-gray-500 text-xs font-mono uppercase tracking-widest">{date}</span>
                        <div className="h-px bg-gray-700 flex-1"></div>
                    </div>

                    {/* Messages & Notes */}
                    <div className="space-y-6 relative border-l border-gray-800 ml-4 pl-8">
                        {msgs.map((msg) => (
                            <div key={msg.message_id} className="relative group">
                                {/* Time Dot */}
                                <div className={`absolute -left-[37px] top-1 w-2.5 h-2.5 rounded-full border-2 border-[#1e1e1e]
                                    ${msg.role === 'user' ? 'bg-blue-500' : 'bg-purple-500'}`} 
                                />
                                
                                {/* Content Block */}
                                <div className={`p-4 rounded-lg border text-sm leading-relaxed
                                    ${msg.role === 'user' 
                                        ? 'bg-[#1e1e1e] border-[#333] text-gray-300' 
                                        : 'bg-[#252526] border-purple-900/30 text-gray-200'
                                    }`}>
                                    <div className="flex justify-between items-start mb-2 opacity-50 text-xs">
                                        <span className="uppercase font-bold tracking-wider">
                                            {msg.role === 'sophia' ? 'Sophia' : 'You'}
                                        </span>
                                        <span>
                                            {new Date(msg.timestamp).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}
                                        </span>
                                    </div>
                                    <div className="whitespace-pre-wrap font-sans">{msg.content}</div>
                                </div>

                                {/* Editable Note Area (After each block or group?) */}
                                {/* User said: "Interspersed Notes" */}
                                <div className="mt-4 pl-2 opacity-0 group-hover:opacity-100 transition-opacity focus-within:opacity-100">
                                    <textarea 
                                        placeholder="Add a note here..."
                                        className="w-full bg-transparent text-gray-400 text-sm resize-none focus:outline-none focus:border-b border-gray-700 py-2 h-10 focus:h-24 transition-all placeholder:text-gray-700"
                                    />
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            ))}
            
            {messages.length === 0 && (
                <div className="text-center text-gray-600 py-20">
                    <p>No journal entries yet.</p>
                    <p className="text-xs mt-2">Chat with Sophia to create memories.</p>
                </div>
            )}
        </div>
    );
}
