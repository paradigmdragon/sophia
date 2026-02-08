
import { useState, useEffect, useCallback } from "react";
import { MarkdownEditor } from "../components/MarkdownEditor";
import { noteService } from "../lib/noteService";

export function EditorPage() {
    const [content, setContent] = useState<string>("");
    const [isLoaded, setIsLoaded] = useState(false);

    useEffect(() => {
        async function load() {
            const text = await noteService.loadTodayNote();
            setContent(text);
            setIsLoaded(true);
        }
        load();
    }, []);

    // Auto-save debounce could be implemented here or in the service.
    // For simplicity, we save on every change (or rely on Editor's onBlur/onChange).
    // Let's assume handleChange is called often, so we might want a debouncer.
    // But for now, direct save is safer for data loss prevention if performance allows.
    // Actually, `writeTextFile` might be expensive.
    
    // Let's modify MarkdownEditor to accept an `onChange` that we can debounce.
    // Or just pass the saver.

    const handleContentChange = useCallback((newContent: string) => {
        setContent(newContent);
        noteService.saveTodayNote(newContent);
    }, []);

    if (!isLoaded) {
        return <div className="h-full w-full flex items-center justify-center bg-[#1e1e1e] text-gray-500">Loading...</div>;
    }

    const today = new Date().toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

    return (
        <div className="h-full w-full flex flex-col bg-[#1e1e1e] text-gray-200">
            {/* Header: Date */}
            <div className="px-8 py-6 border-b border-[#333]">
                <h1 className="text-3xl font-serif text-gray-100">{today}</h1>
            </div>

            {/* Editor Area */}
            <div className="flex-1 overflow-hidden relative">
                 {/* 
                    Passing key to force re-attach if needed, but not necessary here.
                    Passing initialContent.
                    We need to update MarkdownEditor to allow controlled input or just initialContent.
                    Current MarkdownEditor uses `initialContent` prop only on mount.
                    So we pass `content` as `initialContent` only once when `isLoaded` becomes true.
                 */}
                 <MarkdownEditor initialContent={content} onChange={handleContentChange} />
            </div>
        </div>
    );
}
