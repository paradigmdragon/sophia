import { useState } from "react";
import { X, Save, Plus } from "lucide-react";
import { memoryService } from "../lib/memoryService";

interface NoteQuickAddModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
}

export function NoteQuickAddModal({ isOpen, onClose, onSuccess }: NoteQuickAddModalProps) {
    const [title, setTitle] = useState("");
    const [body, setBody] = useState("");
    const [tags, setTags] = useState("");
    const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
    const [saving, setSaving] = useState(false);

    if (!isOpen) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!title.trim()) return;

        setSaving(true);
        try {
            await memoryService.appendNote({
                title: title.trim(),
                body: body.trim(),
                tags: tags.split(',').map(t => t.trim()).filter(Boolean),
                date: date
            });
            onSuccess();
            onClose();
            // Reset form
            setTitle("");
            setBody("");
            setTags("");
            setDate(new Date().toISOString().split('T')[0]);
        } catch (e) {
            alert("Failed to save note. See console.");
            console.error(e);
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[60] bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-[#1e1e1e] w-full max-w-lg rounded-lg border border-[#333] shadow-2xl flex flex-col max-h-[90vh] animation-scale-in">
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-3 border-b border-[#333]">
                    <h2 className="text-sm font-bold text-gray-200 flex items-center gap-2">
                        <Plus size={16} className="text-blue-500" />
                        Add Note
                    </h2>
                    <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors">
                        <X size={18} />
                    </button>
                </div>

                {/* Body */}
                <form onSubmit={handleSubmit} className="p-4 space-y-4 flex-1 overflow-y-auto">
                    <div>
                        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Title <span className="text-red-500">*</span></label>
                        <input
                            type="text"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            className="w-full bg-[#252526] border border-[#333] rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500 transition-colors"
                            placeholder="노트 제목을 입력하세요"
                            required
                        />
                    </div>
                    
                    <div>
                        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Date</label>
                        <input
                            type="date"
                            value={date}
                            onChange={(e) => setDate(e.target.value)}
                            className="w-full bg-[#252526] border border-[#333] rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500 transition-colors"
                            required
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Tags (comma separated)</label>
                        <input
                            type="text"
                            value={tags}
                            onChange={(e) => setTags(e.target.value)}
                            className="w-full bg-[#252526] border border-[#333] rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500 transition-colors"
                            placeholder="ex) idea, todo, project"
                        />
                    </div>

                    <div className="flex-1">
                        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Content</label>
                        <textarea
                            value={body}
                            onChange={(e) => setBody(e.target.value)}
                            className="w-full h-32 bg-[#252526] border border-[#333] rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500 transition-colors resize-none font-mono"
                            placeholder="내용을 입력하세요..."
                        />
                    </div>
                </form>

                {/* Footer */}
                <div className="p-3 border-t border-[#333] flex justify-end gap-2 bg-[#252526] rounded-b-lg">
                    <button 
                        onClick={onClose}
                        className="px-3 py-1.5 text-xs text-gray-400 hover:text-white transition-colors"
                    >
                        Cancel
                    </button>
                    <button 
                        onClick={handleSubmit}
                        disabled={saving || !title.trim()}
                        className={`
                            px-4 py-1.5 text-xs font-bold rounded flex items-center gap-1.5 transition-colors
                            ${saving || !title.trim() ? 'bg-blue-900/50 text-blue-400/50 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-500 text-white'}
                        `}
                    >
                        <Save size={14} />
                        {saving ? "Saving..." : "Save Note"}
                    </button>
                </div>
            </div>
        </div>
    );
}
