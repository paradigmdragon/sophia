import { useState, useEffect } from "react";
import { noteService, NoteCard as NoteCardType } from "../lib/noteService";
import { NoteCard } from "../components/NoteCard";
import { ChevronRight, Calendar } from "lucide-react";

export function SophiaNotePage() {
    const [cards, setCards] = useState<NoteCardType[]>([]);
    const [selectedCard, setSelectedCard] = useState<NoteCardType | null>(null);

    useEffect(() => {
        loadTodayCards();
    }, []);

    const loadTodayCards = async () => {
        const path = noteService.getTodayFileName();
        // Ensure file exists or create empty? Parse logic handles it (returns empty if file read fails/empty)
        try {
            if (await noteService.exists(path)) {
                const parsed = await noteService.parseNoteCards(path);
                setCards(parsed);
            } else {
                setCards([]); 
                // Maybe create a default "Welcome" card if empty?
            }
        } catch (e) {
            console.error(e);
            setCards([]);
        }
    };

    return (
        <div className="h-full w-full flex flex-col bg-[#1e1e1e] text-gray-200 font-sans relative">
            {/* Minimal Header */}
            <header className="px-6 py-4 border-b border-[#333] flex justify-between items-center h-14 flex-shrink-0">
                <div className="flex items-center gap-2">
                    <h1 className="text-xl font-bold text-gray-100 tracking-tight">Sophia Note</h1>
                    <span className="text-xs text-gray-500 px-2 py-0.5 border border-[#333] rounded">Today</span>
                </div>
                {/* Right utility icons if needed, e.g. "Refresh" or "New Note" */}
            </header>

            <div className="flex-1 flex overflow-hidden">
                {/* Left: Today's Records (70%) */}
                <main className="flex-[0.7] flex flex-col min-w-0 border-r border-[#333] bg-[#1e1e1e]">
                    <div className="px-6 py-3 border-b border-[#333]/50 text-xs font-bold text-gray-500 uppercase tracking-widest flex items-center gap-2">
                        TODAY (Sophia Summary)
                    </div>
                    
                    <div className="flex-1 overflow-y-auto p-6 space-y-4">
                        {cards.length === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center text-center p-10 select-none">
                                <p className="text-gray-500 font-medium mb-4 leading-relaxed">
                                    오늘은 아직 소피아가 정리한 기록이 없습니다.
                                </p>
                                <p className="text-xs text-gray-600 leading-relaxed max-w-sm">
                                    주인님과의 대화, 작성, 자막 활동이 쌓이면<br/>
                                    소피아가 자동으로 요약하여 여기에 표시합니다.
                                </p>
                            </div>
                        ) : (
                            cards.map(card => (
                                <NoteCard 
                                    key={card.id} 
                                    {...card}
                                    source="chat" // Default for now
                                    timeRange="13:20 ~ 13:47" // Dummy for now
                                    onOpen={() => setSelectedCard(card)} 
                                />
                            ))
                        )}
                    </div>
                </main>

                {/* Right: Past Records (30%) */}
                <aside className="flex-[0.3] flex flex-col bg-[#1b1b1b]">
                     <div className="px-6 py-3 border-b border-[#333]/50 text-xs font-bold text-gray-500 uppercase tracking-widest flex items-center gap-2">
                        <Calendar size={12} />
                        ARCHIVE
                    </div>
                    <div className="flex-1 overflow-y-auto p-4 space-y-1">
                        {/* Placeholder Dates */}
                        {[...Array(5)].map((_, i) => {
                            const d = new Date();
                            d.setDate(d.getDate() - (i + 1));
                            return (
                                <button key={i} className="w-full text-left flex items-center justify-between text-sm text-gray-400 hover:text-gray-200 hover:bg-[#2a2a2e] px-3 py-2 rounded transition-colors group">
                                    <span>{d.toISOString().split('T')[0]}</span>
                                    <ChevronRight size={14} className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-500" />
                                </button>
                            );
                        })}
                    </div>
                </aside>
            </div>

            {/* Detail Modal/Panel (Overlay) */}
            {selectedCard && (
                <div className="absolute inset-0 z-50 bg-black/60 backdrop-blur-sm flex justify-end">
                    <div className="w-[600px] h-full bg-[#1e1e1e] border-l border-[#333] shadow-2xl flex flex-col animation-slide-in-right">
                        <div className="px-6 py-4 border-b border-[#333] flex justify-between items-start">
                            <h2 className="text-xl font-bold text-white pr-8">{selectedCard.title}</h2>
                            <button 
                                onClick={() => setSelectedCard(null)}
                                className="text-gray-500 hover:text-white transition-colors"
                            >
                                Close
                            </button>
                        </div>
                        
                        <div className="flex-1 overflow-y-auto p-6">
                            {/* Tags */}
                            {selectedCard.tags.length > 0 && (
                                <div className="flex flex-wrap gap-2 mb-6">
                                    {selectedCard.tags.map(t => (
                                        <span key={t} className="text-xs text-blue-300 bg-blue-900/40 px-2 py-1 rounded">
                                            {t}
                                        </span>
                                    ))}
                                </div>
                            )}

                            {/* Summary Content */}
                            <div className="text-gray-300 leading-relaxed text-sm whitespace-pre-wrap mb-8">
                                {selectedCard.summary}
                            </div>

                            {/* Original Content Section */}
                            <div className="border-t border-[#333] pt-6">
                                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">Original Log</h3>
                                <div className="bg-[#111] p-4 rounded text-xs font-mono text-gray-400 whitespace-pre-wrap">
                                    {selectedCard.originalContent}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
