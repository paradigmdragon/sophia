import { MessageCircle, PenTool, Headphones, Clock } from "lucide-react";

interface NoteCardProps {
    title: string;
    summary: string;
    tags?: string[];
    source?: 'chat' | 'write' | 'audio';
    timeRange?: string;
    onOpen: () => void;
}

export function NoteCard({ title, summary, tags, source = 'chat', timeRange, onOpen }: NoteCardProps) {
    const SourceIcon = {
        chat: MessageCircle,
        write: PenTool,
        audio: Headphones
    }[source];

    return (
        <div 
            onClick={onOpen}
            className="bg-[#2a2a2e] p-5 rounded-lg border border-[#333] hover:border-[#555] cursor-pointer transition-all group shadow-sm hover:shadow-md active:bg-[#333]"
        >
            {/* Title */}
            <h3 className="text-base font-bold text-gray-100 mb-2 leading-tight group-hover:text-white">
                {title}
            </h3>
            
            {/* Summary */}
            <p className="text-sm text-gray-400 leading-relaxed mb-4 line-clamp-3">
                {summary}
            </p>
            
            {/* Footer: Metadata */}
            <div className="flex items-center justify-between text-xs text-gray-500 border-t border-[#333]/50 pt-3 mt-2">
                <div className="flex items-center gap-3">
                    {/* Source Icon */}
                    <div className="flex items-center gap-1.5" title="Source">
                        <SourceIcon size={14} className="text-gray-400" />
                        <span className="capitalize hidden md:inline">{source}</span>
                    </div>

                    {/* Time Range */}
                    {timeRange && (
                        <div className="flex items-center gap-1.5" title="Time Range">
                            <Clock size={14} className="text-gray-500" />
                            <span>{timeRange}</span>
                        </div>
                    )}
                </div>

                {/* Optional Tags (if present) */}
                {tags && tags.length > 0 && (
                    <div className="flex gap-2">
                         {tags.slice(0, 2).map((tag, i) => (
                            <span key={i} className="text-gray-500">#{tag}</span>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
