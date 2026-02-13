import { useState, useEffect } from "react";
import { auditService, AuditItem } from "../../lib/auditService";
import { RefreshCw, CheckCircle, XCircle, Clock } from "lucide-react";

export function AuditPanel() {
    const [items, setItems] = useState<AuditItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [filter, setFilter] = useState('all');

    const loadData = async () => {
        setLoading(true);
        try {
            const data = await auditService.listAuditLog(50, filter);
            setItems(data);
        } catch (e) {
            console.error("Failed to load audit log", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, [filter]);

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'committed': return <CheckCircle size={14} className="text-green-500" />;
            case 'failed': return <XCircle size={14} className="text-red-500" />;
            default: return <Clock size={14} className="text-yellow-500" />;
        }
    };

    return (
        <div className="h-full flex flex-col bg-[#1e1e1e]">
             {/* Toolbar */}
             <div className="p-2 border-b border-[#333] flex gap-2 items-center">
                <select 
                    value={filter} 
                    onChange={(e) => setFilter(e.target.value)}
                    className="bg-[#2a2a2a] text-gray-300 text-xs px-2 py-1 rounded border border-[#333] outline-none focus:border-blue-500"
                >
                    <option value="all">All Status</option>
                    <option value="committed">Committed</option>
                    <option value="failed">Failed</option>
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
                        No audit records found.
                    </div>
                )}
                
                {items.map((item, idx) => (
                    <div key={idx} className="bg-[#252526] border border-[#333] rounded p-2 text-xs flex flex-col gap-1 hover:border-[#444] transition-colors">
                        <div className="flex items-center gap-2">
                            {getStatusIcon(item.status)}
                            <span className={`font-mono font-medium ${item.status === 'committed' ? 'text-green-400' : 'text-gray-300'}`}>
                                {item.skill_id}
                            </span>
                            <span className="ml-auto text-gray-500 font-mono text-[10px]">
                                {item.timestamps?.finished_at ? new Date(item.timestamps.finished_at).toLocaleTimeString() : '-'}
                            </span>
                        </div>
                        <div className="pl-6 text-gray-400 font-mono text-[10px] truncate" title={item.run_id}>
                            ID: {item.run_id}
                        </div>
                         {item.diff_refs && item.diff_refs.length > 0 && (
                            <div className="pl-6 mt-1 flex flex-wrap gap-1">
                                {item.diff_refs.map((ref, i) => (
                                    <span key={i} className="bg-[#333] text-gray-400 px-1 rounded flex items-center" title={ref}>
                                        verifier
                                    </span>
                                ))}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}
