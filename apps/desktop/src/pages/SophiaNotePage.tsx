import { useState, useEffect } from "react";
import { memoryService, MemoryItem } from "../lib/memoryService";
import { ChevronRight, Calendar, RefreshCw, Plus } from "lucide-react";
import { NoteQuickAddModal } from "../components/NoteQuickAddModal";

export function SophiaNotePage() {
    const [selectedDate, setSelectedDate] = useState<string>(new Date().toISOString().split('T')[0]);
    const [availableDates, setAvailableDates] = useState<string[]>([]);
    const [cards, setCards] = useState<MemoryItem[]>([]);
    const [selectedCard, setSelectedCard] = useState<MemoryItem | null>(null);
    const [loading, setLoading] = useState(false);
    const [isAddModalOpen, setIsAddModalOpen] = useState(false);

    useEffect(() => {
        loadDates();
    }, []);

    useEffect(() => {
        if (selectedDate) {
            loadCardsForDate(selectedDate);
        }
    }, [selectedDate]);

    const loadDates = async () => {
        const dates = await memoryService.getAvailableDates('notes');
        setAvailableDates(dates);
    };

    const loadCardsForDate = async (date: string) => {
        setLoading(true);
        try {
            const items = await memoryService.listMessagesByDate('notes', date);
            setCards(items);
        } catch (e) {
            console.error(e);
            setCards([]);
        } finally {
            setLoading(false);
        }
    };

    const handleRefresh = async () => {
        await loadDates();
        await loadCardsForDate(selectedDate);
    };

    return (
        <div className="h-full w-full flex flex-col bg-[#1e1e1e] text-gray-200 font-sans relative">
            {/* Minimal Header */}
            <header className="px-6 py-4 border-b border-[#333] flex justify-between items-center h-14 flex-shrink-0">
                <div className="flex items-center gap-2">
                    <h1 className="text-xl font-bold text-gray-100 tracking-tight">Sophia Note</h1>
                    <span className="text-xs text-gray-500 px-2 py-0.5 border border-[#333] rounded">
                        {selectedDate === new Date().toISOString().split('T')[0] ? "Today" : selectedDate}
                    </span>
                </div>
                <div className="flex gap-2">
                    <button 
                        onClick={() => setIsAddModalOpen(true)}
                        className="p-2 hover:bg-[#333] rounded text-blue-400 hover:text-blue-300 transition-colors flex items-center gap-1 text-xs font-bold"
                        title="Add Note"
                    >
                        <Plus size={14} />
                        노트 추가
                    </button>
                    <button 
                        onClick={handleRefresh}
                        className="p-2 hover:bg-[#333] rounded text-gray-400 transition-colors"
                        title="Refresh Notes"
                    >
                        <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
                    </button>
                </div>
            </header>

            <div className="flex-1 flex overflow-hidden">
                {/* Left: Records (70%) */}
                <main className="flex-[0.7] flex flex-col min-w-0 border-r border-[#333] bg-[#1e1e1e]">
                    <div className="px-6 py-3 border-b border-[#333]/50 text-xs font-bold text-gray-500 uppercase tracking-widest flex items-center gap-2">
                        RECORD (Memory/Notes)
                    </div>
                    
                    <div className="flex-1 overflow-y-auto p-6 space-y-4">
                        {cards.length === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center text-center p-10 select-none">
                                <p className="text-gray-500 font-medium mb-4 leading-relaxed">
                                    {selectedDate} 기록이 없습니다.
                                </p>
                                <p className="text-xs text-gray-600 leading-relaxed max-w-sm mb-4">
                                    'notes' 네임스페이스에 저장된 데이터가 이 곳에 표시됩니다.
                                </p>
                                <button 
                                    onClick={() => setIsAddModalOpen(true)}
                                    className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded flex items-center gap-2 transition-colors mx-auto"
                                >
                                    <Plus size={14} />
                                    노트 추가하기
                                </button>
                            </div>
                        ) : (
                            cards.map((item, idx) => {
                                const { parsed } = item;
                                const title = parsed.title || "Untitled Note";
                                const summary = parsed.summary || parsed.body || parsed.content || "No content";
                                const tags = parsed.tags || [];

                                return (
                                    <div 
                                        key={idx}
                                        onClick={() => setSelectedCard(item)}
                                        className="bg-[#252526] border border-[#333] rounded p-4 hover:border-blue-500/50 transition-colors cursor-pointer group"
                                    >
                                        <div className="flex justify-between items-start mb-2">
                                            <h3 className="font-bold text-gray-200">{title}</h3>
                                            <span className="text-xs text-gray-500 font-mono">
                                                {item.timestamp ? new Date(item.timestamp).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : ''}
                                            </span>
                                        </div>
                                        <p className="text-sm text-gray-400 line-clamp-3 mb-3">
                                            {typeof summary === 'string' ? summary : JSON.stringify(summary)}
                                        </p>
                                        {tags.length > 0 && (
                                            <div className="flex flex-wrap gap-2">
                                                {tags.map((t: string) => (
                                                    <span key={t} className="text-[10px] text-blue-300 bg-blue-900/40 px-1.5 py-0.5 rounded">
                                                        #{t}
                                                    </span>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                );
                            })
                        )}
                    </div>
                </main>

                {/* Right: Archive (30%) */}
                <aside className="flex-[0.3] flex flex-col bg-[#1b1b1b]">
                     <div className="px-6 py-3 border-b border-[#333]/50 text-xs font-bold text-gray-500 uppercase tracking-widest flex items-center gap-2">
                        <Calendar size={12} />
                        ARCHIVE
                    </div>
                    <div className="flex-1 overflow-y-auto p-4 space-y-1">
                        {availableDates.length === 0 && (
                            <div className="text-center py-4 text-gray-500 text-xs">
                                No archives found.
                            </div>
                        )}

                        {availableDates.map(date => (
                            <button 
                                key={date} 
                                onClick={() => setSelectedDate(date)}
                                className={`
                                    w-full text-left flex items-center justify-between text-sm px-3 py-2 rounded transition-colors group
                                    ${selectedDate === date ? 'bg-[#333] text-white' : 'text-gray-400 hover:text-gray-200 hover:bg-[#2a2a2e]'}
                                `}
                            >
                                <span>{date}</span>
                                {selectedDate === date && <ChevronRight size={14} className="text-blue-500" />}
                            </button>
                        ))}
                    </div>
                </aside>
            </div>

            {/* Note Quick Add Modal */}
            <NoteQuickAddModal 
                isOpen={isAddModalOpen} 
                onClose={() => setIsAddModalOpen(false)}
                onSuccess={handleRefresh}
            />

            {/* Detail Modal/Panel (Overlay) */}
            {selectedCard && (
                <div className="absolute inset-0 z-50 bg-black/60 backdrop-blur-sm flex justify-end">
                    <div className="w-[600px] h-full bg-[#1e1e1e] border-l border-[#333] shadow-2xl flex flex-col animation-slide-in-right">
                        <div className="px-6 py-4 border-b border-[#333] flex justify-between items-start">
                            <h2 className="text-xl font-bold text-white pr-8">
                                {selectedCard.parsed.title || "Note Detail"}
                            </h2>
                            <button 
                                onClick={() => setSelectedCard(null)}
                                className="text-gray-500 hover:text-white transition-colors"
                            >
                                Close
                            </button>
                        </div>
                        
                        <div className="flex-1 overflow-y-auto p-6">
                            {/* Tags */}
                            {selectedCard.parsed.tags && selectedCard.parsed.tags.length > 0 && (
                                <div className="flex flex-wrap gap-2 mb-6">
                                    {selectedCard.parsed.tags.map((t: string) => (
                                        <span key={t} className="text-xs text-blue-300 bg-blue-900/40 px-2 py-1 rounded">
                                            {t}
                                        </span>
                                    ))}
                                </div>
                            )}

                            {/* Content */}
                            <div className="text-gray-300 leading-relaxed text-sm whitespace-pre-wrap mb-8 font-serif">
                                {selectedCard.parsed.body || selectedCard.parsed.content || JSON.stringify(selectedCard.parsed, null, 2)}
                            </div>

                            {/* Metadata Section */}
                            <div className="border-t border-[#333] pt-6 space-y-2">
                                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">Metadata</h3>
                                <div className="text-xs text-gray-500 font-mono">
                                    <div>Timestamp: {selectedCard.timestamp}</div>
                                    <div>Namespace: {selectedCard.namespace}</div>
                                </div>
                                <div className="bg-[#111] p-4 rounded text-xs font-mono text-gray-400 whitespace-pre-wrap overflow-x-auto">
                                    {selectedCard.raw}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
