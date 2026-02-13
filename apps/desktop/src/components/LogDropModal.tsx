import { useState, useEffect, useRef } from "react";
import { X, Save } from "lucide-react";
import { logDropService } from "../lib/logDropService";

interface LogDropModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSaveSuccess: (filename: string) => void;
}

export function LogDropModal({ isOpen, onClose, onSaveSuccess }: LogDropModalProps) {
    const [title, setTitle] = useState("");
    const [body, setBody] = useState("");
    const [tags, setTags] = useState("");
    const [saving, setSaving] = useState(false);
    const bodyRef = useRef<HTMLTextAreaElement>(null);

    // Reset form on open
    useEffect(() => {
        if (isOpen) {
            const now = new Date();
            setTitle(`Dev Log ${now.toLocaleTimeString()}`);
            setBody("");
            setTags("ide, manual");
            setSaving(false);
            // Autofocus body after a short delay to ensure modal render
            setTimeout(() => bodyRef.current?.focus(), 100);
        }
    }, [isOpen]);

    const handleSave = async () => {
        if (!body.trim()) return;

        setSaving(true);
        try {
            const tagList = tags.split(',').map(t => t.trim()).filter(t => t);
            const filename = await logDropService.saveLog({
                title: title || "Untitled",
                body,
                tags: tagList
            });

            if (filename) {
                onSaveSuccess(filename);
                onClose();
            }
        } catch (e) {
            alert("Failed to save log");
        } finally {
            setSaving(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
            <div className="bg-[#1e1e1e] border border-[#333] rounded-lg shadow-2xl w-full max-w-lg flex flex-col max-h-[90vh]">
                
                {/* Header */}
                <div className="flex items-center justify-between p-3 border-b border-[#333]">
                    <h3 className="text-sm font-bold text-gray-200">New IDE Log</h3>
                    <button onClick={onClose} className="text-gray-400 hover:text-white">
                        <X size={16} />
                    </button>
                </div>

                {/* Body */}
                <div className="p-4 space-y-3 flex-1 overflow-y-auto">
                    <div>
                        <label className="block text-xs text-gray-500 mb-1">Title</label>
                        <input 
                            type="text" 
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            className="w-full bg-[#2a2a2a] text-gray-200 border border-[#333] rounded px-2 py-1.5 text-sm focus:border-blue-500 outline-none"
                            placeholder="Log Title"
                        />
                    </div>

                    <div>
                        <label className="block text-xs text-gray-500 mb-1">Tags (comma separated)</label>
                        <input 
                            type="text" 
                            value={tags}
                            onChange={(e) => setTags(e.target.value)}
                            className="w-full bg-[#2a2a2a] text-gray-200 border border-[#333] rounded px-2 py-1.5 text-sm focus:border-blue-500 outline-none"
                            placeholder="tag1, tag2"
                        />
                    </div>

                    <div className="flex-1 flex flex-col">
                        <label className="block text-xs text-gray-500 mb-1">Content</label>
                        <textarea 
                            ref={bodyRef}
                            value={body}
                            onChange={(e) => setBody(e.target.value)}
                            className="w-full h-40 bg-[#2a2a2a] text-gray-200 border border-[#333] rounded px-2 py-2 text-sm focus:border-blue-500 outline-none resize-none flex-1 font-mono"
                            placeholder="What did you do?"
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                                    handleSave();
                                }
                            }}
                        />
                         <div className="text-[10px] text-gray-600 mt-1 text-right">
                            Cmd+Enter to save
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <div className="p-3 border-t border-[#333] flex justify-between items-center bg-[#252526]">
                    
                    {/* Manual Ingest CTA */}
                    <button
                        onClick={async () => {
                            if (confirm("Run manual ingest now?")) {
                                setSaving(true);
                                try {
                                    const result = await logDropService.ingestLogs();
                                    alert(`Ingest Result:\nScanned: ${result.scanned}\nIngested: ${result.ingested}\nSkipped: ${result.skipped}`);
                                    if (result.ingested > 0) {
                                        onClose(); // Close modal on success
                                    }
                                } catch (e) {
                                    alert("Ingest failed check console");
                                } finally {
                                    setSaving(false);
                                }
                            }
                        }}
                        className="text-xs text-blue-400 hover:text-blue-300 underline"
                    >
                        지금 반영(ingest)
                    </button>

                    <div className="flex gap-2">
                        <button 
                            onClick={onClose}
                            className="px-3 py-1.5 text-xs text-gray-400 hover:text-white transition-colors"
                        >
                            Cancel
                        </button>
                        <button 
                            onClick={handleSave}
                            disabled={saving || !body.trim()}
                            className={`
                                px-4 py-1.5 text-xs font-bold rounded flex items-center gap-1.5 transition-colors
                                ${saving || !body.trim() ? 'bg-blue-900/50 text-blue-400/50 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-500 text-white'}
                            `}
                        >
                            <Save size={14} />
                            {saving ? "Saving..." : "Save Log"}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
