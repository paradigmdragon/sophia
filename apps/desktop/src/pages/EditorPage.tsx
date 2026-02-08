import { useState, useEffect } from "react";
import { MarkdownEditor } from "../components/MarkdownEditor";
import { noteService } from "../lib/noteService";
import { FileSidebar } from "../components/FileSidebar";
import { PanelLeft } from "lucide-react";

export function EditorPage() {
    const [selectedPath, setSelectedPath] = useState<string | null>(null);
    const [content, setContent] = useState<string>("");
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [isSaving, setIsSaving] = useState(false);

    // Initial Load: Today's Note
    useEffect(() => {
        loadDefaultNote();
    }, []);

    const loadDefaultNote = async () => {
        // Default to today's note if nothing selected
        if (!selectedPath) {
            const todayPath = noteService.getTodayFileName();
            // Ensure directory exists first?
            await noteService.ensureNotesDir();
            const noteContent = await noteService.loadTodayNote();
            setContent(noteContent);
            setSelectedPath(todayPath);
        }
    };

    // Load content when path changes
    useEffect(() => {
        if (selectedPath) {
            loadFile(selectedPath);
        }
    }, [selectedPath]);

    const loadFile = async (path: string) => {
        try {
            const fileContent = await noteService.readFile(path);
            setContent(fileContent);
        } catch (error) {
            console.error("Error loading file:", error);
        }
    };

    const handleSave = async (newContent: string) => {
        setContent(newContent);
        if (selectedPath) {
            setIsSaving(true);
            try {
                await noteService.saveFile(selectedPath, newContent);
            } finally {
                setIsSaving(false);
            }
        }
    };

    return (
        <div className="h-full w-full flex bg-[#1e1e1e] text-gray-200 overflow-hidden relative">
            {/* Sidebar */}
            {isSidebarOpen && (
                <div className="h-full flex-shrink-0">
                    <FileSidebar 
                        currentFile={selectedPath}
                        onSelectFile={setSelectedPath}
                        isCollapsed={false}
                        className="h-full border-r border-[#333]"
                    />
                </div>
            )}

            {/* Main Content: Editor */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Header: File Name & Controls */}
                <div className="h-10 px-4 border-b border-[#333] flex items-center justify-between bg-[#1e1e1e]">
                    <div className="flex items-center gap-3">
                        <button 
                            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                            className={`p-1.5 rounded-md hover:bg-[#333] text-gray-400 ${isSidebarOpen ? 'text-blue-400' : ''}`}
                            title="Toggle Sidebar"
                        >
                            <PanelLeft size={18} />
                        </button>
                        <h1 className="text-sm font-medium text-gray-300 truncate">
                            {selectedPath ? selectedPath.split('/').pop() : 'Untitled'}
                        </h1>
                    </div>
                    <div className="flex items-center gap-2">
                        {isSaving && <span className="text-xs text-gray-500 animate-pulse">Saving...</span>}
                    </div>
                </div>

                {/* Editor Area */}
                <div className="flex-1 overflow-hidden relative">
                     <MarkdownEditor 
                        value={content} 
                        onChange={handleSave} 
                    />
                </div>
            </div>
        </div>
    );
}
