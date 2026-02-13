import { useState, useEffect } from "react";
import { memoryService, MemoryItem, MemoryNamespace } from "../../lib/memoryService";
import { RefreshCw, AlertCircle } from "lucide-react";

interface MemoryPanelProps {
    refreshToken?: number;
}

export function MemoryPanel({ refreshToken = 0 }: MemoryPanelProps) {
    const [items, setItems] = useState<MemoryItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [namespace, setNamespace] = useState<MemoryNamespace | 'all'>('all');
    const [limit, setLimit] = useState(50);

    const loadData = async () => {
        setLoading(true);
        try {
            const data = await memoryService.listMemory(namespace, limit);
            setItems(data);
        } catch (e) {
            console.error("Failed to load memory", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, [namespace, limit, refreshToken]);

    const getNamespaceColor = (ns: string) => {
        switch (ns) {
            case 'notes': return 'bg-blue-900/50 text-blue-200 border-blue-700/50';
            case 'ideas': return 'bg-yellow-900/50 text-yellow-200 border-yellow-700/50';
            case 'decisions': return 'bg-purple-900/50 text-purple-200 border-purple-700/50';
            case 'actions': return 'bg-green-900/50 text-green-200 border-green-700/50';
            default: return 'bg-gray-800 text-gray-300';
        }
    };

    const renderItemContent = (item: MemoryItem) => {
        const { parsed } = item;
        // Logic to display title/body if available, else snippet
        const title = parsed.title || parsed.summary || (typeof parsed.content === 'string' ? parsed.content.substring(0, 50) : null);
        // If body/description exists use it, otherwise fallback to content or raw stringify
        const body = parsed.body || parsed.description || (typeof parsed.content === 'string' ? parsed.content : JSON.stringify(parsed));
        
        return (
            <div className="flex-1 min-w-0">
                {title && <div className="font-medium text-gray-200 truncate">{title}</div>}
                <div className="text-sm text-gray-400 line-clamp-2 break-all">
                    {typeof body === 'object' ? JSON.stringify(body) : body}
                </div>
                {parsed.tags && Array.isArray(parsed.tags) && (
                    <div className="flex flex-wrap gap-1 mt-1">
                        {parsed.tags.map((tag: string, i: number) => (
                            <span key={i} className="text-xs px-1.5 py-0.5 rounded bg-[#333] text-gray-300">
                                #{tag}
                            </span>
                        ))}
                    </div>
                )}
            </div>
        );
    };

    return (
        <div className="h-full flex flex-col bg-[#1e1e1e]">
            {/* Toolbar */}
            <div className="p-2 border-b border-[#333] flex gap-2 items-center">
                <select 
                    value={namespace} 
                    onChange={(e) => setNamespace(e.target.value as any)}
                    className="bg-[#2a2a2a] text-gray-300 text-xs px-2 py-1 rounded border border-[#333] outline-none focus:border-blue-500"
                >
                    <option value="all">All Namespaces</option>
                    <option value="notes">Notes</option>
                    <option value="ideas">Ideas</option>
                    <option value="decisions">Decisions</option>
                    <option value="actions">Actions</option>
                </select>

                <select 
                    value={limit} 
                    onChange={(e) => setLimit(Number(e.target.value))}
                    className="bg-[#2a2a2a] text-gray-300 text-xs px-2 py-1 rounded border border-[#333] outline-none focus:border-blue-500"
                >
                    <option value={20}>20</option>
                    <option value={50}>50</option>
                    <option value={200}>200</option>
                </select>

                <button 
                    onClick={loadData}
                    disabled={loading}
                    className="p-1 hover:bg-[#333] rounded text-gray-400 transition-colors ml-auto"
                >
                    <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
                </button>
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-2">
                {items.length === 0 && !loading && (
                    <div className="text-center text-gray-500 py-8 text-sm">
                        No memory items found.
                    </div>
                )}

                {items.map((item, idx) => (
                    <div key={idx} className="bg-[#252526] border border-[#333] rounded p-2 flex flex-col gap-1 hover:border-[#444] transition-colors">
                        <div className="flex items-center gap-2 mb-1">
                            <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded border ${getNamespaceColor(item.namespace)}`}>
                                {item.namespace}
                            </span>
                            {item.timestamp && (
                                <span className="text-[10px] text-gray-500 ml-auto font-mono">
                                    {new Date(item.timestamp).toLocaleString(undefined, {
                                        month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'
                                    })}
                                </span>
                            )}
                        </div>
                        
                        {Object.keys(item.parsed).length === 0 ? (
                            <div className="flex items-start gap-2 text-red-400 text-xs">
                                <AlertCircle size={14} className="mt-0.5" />
                                <span className="font-mono break-all opacity-80">{item.raw}</span>
                            </div>
                        ) : (
                            renderItemContent(item)
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}
