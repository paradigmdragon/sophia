import { useState, useEffect, useRef } from "react";
import { 
    FileText, ChevronRight, ChevronDown, 
    Plus, FolderPlus, Trash2, RotateCw 
} from "lucide-react";
import { noteService, FileNode } from "../lib/noteService";

interface FileSidebarProps {
    onSelectFile: (path: string) => void;
    currentFile: string | null;
    className?: string;
    isCollapsed: boolean;
}

export function FileSidebar({ onSelectFile, currentFile, className = "", isCollapsed }: FileSidebarProps) {
    const [fileTree, setFileTree] = useState<FileNode[]>([]);
    const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [width, setWidth] = useState(250);
    const [isResizing, setIsResizing] = useState(false);
    const [renamingPath, setRenamingPath] = useState<string | null>(null);
    const [renameValue, setRenameValue] = useState("");
    const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
    const [lastSelectedPath, setLastSelectedPath] = useState<string | null>(null); // For Shift+Click range
    
    // DnD State
    const [draggedNodes, setDraggedNodes] = useState<FileNode[]>([]); // Support multiple
    const [dragOverNode, setDragOverNode] = useState<string | null>(null);
    
    // Rename Input Ref
    const renameInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        refreshNotes();
    }, []);

    // Effect to focus input when renaming starts
    useEffect(() => {
        if (renamingPath && renameInputRef.current) {
            renameInputRef.current.focus();
            // Select filename without extension if possible
            const dotIndex = renameValue.lastIndexOf('.');
            if (dotIndex > 0) {
                 renameInputRef.current.setSelectionRange(0, dotIndex);
            } else {
                 renameInputRef.current.select();
            }
        }
    }, [renamingPath]);

    const refreshNotes = async () => {
        setIsRefreshing(true);
        const nodes = await noteService.listNotes();
        
        // Auto-create Welcome note if empty
        if (nodes.length === 0) {
             const welcomePath = await noteService.createNote(undefined, "Welcome.md", "# Welcome to Sophia\n\nStart writing here.");
             if (welcomePath) {
                 const newNodes = await noteService.listNotes();
                 setFileTree(newNodes);
                 setIsRefreshing(false);
                 handleSelect(welcomePath, false, false); 
                 onSelectFile(welcomePath); 
                 return;
             }
        }

        setFileTree(nodes);
        setIsRefreshing(false);
    };

    const toggleFolder = (path: string) => {
        const newExpanded = new Set(expandedFolders);
        if (newExpanded.has(path)) {
            newExpanded.delete(path);
        } else {
            newExpanded.add(path);
        }
        setExpandedFolders(newExpanded);
    };

    const handleCreateFolder = async () => {
        const name = `New Folder`; 
        // We'll try to create it, if it exists, maybe append number? 
        // For now, let's just create and if it fails (exists), it might return null or throw. 
        // noteService doesn't handle deduplication internally yet explicitly for this flow, but let's assume we want to create and then rename.
        // Actually, let's just create "New Folder" and immediately trigger rename.
        // But if "New Folder" exists, it might conflict. 
        // Let's generate a unique name or just let user rename.
        let uniqueName = name;
        let counter = 1;
        while (await noteService.exists(await noteService.getNotesPath() + "/" + uniqueName)) {
            uniqueName = `${name} ${counter}`;
            counter++;
        }

        const path = await noteService.createFolder(undefined, uniqueName);
        if (path) {
            await refreshNotes();
            setRenamingPath(path);
            setRenameValue(uniqueName);
            // Auto expand parent if needed? It's root.
        }
    };

    const handleCreateNote = async () => {
        const name = `Untitled`;
        let uniqueName = name;
        let counter = 1;
        // Ideally we check existence.
        while (await noteService.exists(await noteService.getNotesPath() + "/" + uniqueName + ".md")) {
            uniqueName = `${name} ${counter}`;
            counter++;
        }

        const path = await noteService.createNote(undefined, uniqueName + ".md");
        if (path) {
            await refreshNotes();
            await refreshNotes();
            handleSelect(path, false, false);
            onSelectFile(path);
            setRenamingPath(path);
            setRenameValue(uniqueName); 
        }
    };

    const handleDelete = async (path: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (await confirm(`Delete ${path.split('/').pop()}?`)) {
            await noteService.deleteItem(path);
            await refreshNotes();
            if (currentFile === path) onSelectFile("");
        }
    };

    const startRenaming = (node: FileNode, e: React.MouseEvent) => {
        e.stopPropagation();
        setRenamingPath(node.path);
        setRenameValue(node.name);
    };

    const submitRename = async () => {
        if (!renamingPath) return;
        
        const oldPath = renamingPath;
        let newName = renameValue.trim();
        if (!newName) {
            setRenamingPath(null);
            return;
        }

        // Check if it's a file and needs extension
        // We can check if oldPath ends with .md or find node.
        // Simple heuristic: if oldPath was .md, newName should be .md
        if (oldPath.endsWith('.md') && !newName.endsWith('.md')) {
            newName += '.md';
        }

        const success = await noteService.renameItem(oldPath, newName);
        if (success) {
            await refreshNotes();
            // Update selection if needed (logic to find new path is tricky without return)
            // But if we refresh, tree is updated. Selection might correspond to old path if not updated.
            if (currentFile === oldPath) {
                 const parent = oldPath.substring(0, oldPath.lastIndexOf('/'));
                 onSelectFile(`${parent}/${newName}`);
            }
        }
        setRenamingPath(null);
    };

    // Resize Logic
    const startResize = (e: React.MouseEvent) => {
        e.preventDefault();
        setIsResizing(true);
        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', stopResize);
    };

    const handleMouseMove = (e: MouseEvent) => {
        const newWidth = Math.max(180, Math.min(600, e.clientX));
        setWidth(newWidth);
    };

    const stopResize = () => {
        setIsResizing(false);
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', stopResize);
    };

    // --- Selection Logic ---
    
    const handleSelect = (path: string, multiSelect: boolean, rangeSelect: boolean) => {
        const newSelected = new Set(multiSelect ? selectedPaths : []);
        
        if (rangeSelect && lastSelectedPath) {
            // Simple range selection: Flatten tree and find range
            // This requires flattening the current visible tree. 
            // For now, let's implement simple multi-select first or complex range later.
            // A full range select requires knowing the visual order.
            // We'll stick to simple multi-select or just add the single item if range logic is complex.
            // Let's implement robust range select if possible:
            const flatVisibleNodes: string[] = [];
            const traverse = (nodes: FileNode[]) => {
                for (const node of nodes) {
                    flatVisibleNodes.push(node.path);
                    if (node.isDirectory && expandedFolders.has(node.path) && node.children) {
                        traverse(node.children);
                    }
                }
            };
            traverse(fileTree);
            
            const startIdx = flatVisibleNodes.indexOf(lastSelectedPath);
            const endIdx = flatVisibleNodes.indexOf(path);
            
            if (startIdx !== -1 && endIdx !== -1) {
                const min = Math.min(startIdx, endIdx);
                const max = Math.max(startIdx, endIdx);
                for (let i = min; i <= max; i++) {
                     newSelected.add(flatVisibleNodes[i]);
                }
            } else {
                 newSelected.add(path);
            }
        } else {
            if (multiSelect) {
                if (newSelected.has(path)) newSelected.delete(path);
                else newSelected.add(path);
            } else {
                newSelected.add(path);
            }
        }

        setSelectedPaths(newSelected);
        setLastSelectedPath(path);
        
        // If single select, also trigger onSelectFile for preview
        if (newSelected.size === 1 && newSelected.has(path)) {
             onSelectFile(path);
        } else if (newSelected.size === 0) {
             onSelectFile("");
        }
    };

    // --- Drag and Drop Logic ---

    const handleDragStart = (e: React.DragEvent, node: FileNode) => {
        e.stopPropagation();
        
        // If dragging a node that is NOT in selection, select it solely
        let draggingPaths = [node.path];
        if (selectedPaths.has(node.path)) {
            draggingPaths = Array.from(selectedPaths);
        } else {
            setSelectedPaths(new Set([node.path]));
            setLastSelectedPath(node.path);
        }

        // We need to resolve FileNodes for these paths to store in state if needed, 
        // or just store paths. State `draggedNodes` needs FileNode[].
        // For simplicity, let's just store paths in dataTransfer and use state for visual?
        // Actually, we perform move based on paths.
        
        setDraggedNodes(draggingPaths.map(p => ({ path: p, name: p.split('/').pop() || '', isDirectory: false }))); // Dummy nodes mainly for count
        
        e.dataTransfer.setData("text/plain", JSON.stringify(draggingPaths));
        e.dataTransfer.effectAllowed = "move";
        
        // Custom drag image showing count?
        if (draggingPaths.length > 1) {
             // const dragIcon = document.createElement('div'); ...
             // Optional polish.
        }
    };

    const handleDragOver = (e: React.DragEvent, targetNode: FileNode) => {
        e.preventDefault();
        e.stopPropagation();
        
        const draggingCount = draggedNodes.length;
        if (draggingCount === 0) return;
        
        // If target is inside the list of dragged items, invalid.
        // But we only have paths. 
        // Also check recursive.
        
        // Only allow dropping on directories
        if (targetNode.isDirectory) {
             setDragOverNode(targetNode.path);
             e.dataTransfer.dropEffect = "move";
        } else {
             setDragOverNode(null);
             e.dataTransfer.dropEffect = "none";
        }
    };

    const handleDrop = async (e: React.DragEvent, targetNode: FileNode) => {
        e.preventDefault();
        e.stopPropagation();
        setDragOverNode(null);
        
        const data = e.dataTransfer.getData("text/plain");
        if (!data || !targetNode.isDirectory) return;

        let pathsToMove: string[] = [];
        try {
            pathsToMove = JSON.parse(data);
            if (!Array.isArray(pathsToMove)) pathsToMove = [data]; // Fallback for single legacy
        } catch {
            pathsToMove = [data];
        }

        let movedCount = 0;
        let errors = [];

        for (const draggedPath of pathsToMove) {
             if (targetNode.path.startsWith(draggedPath)) {
                 console.warn("Cannot move parent into child:", draggedPath);
                 continue;
             }
             
             const success = await noteService.moveItem(draggedPath, targetNode.path);
             if (success) movedCount++;
             else errors.push(draggedPath);
        }

        if (movedCount > 0) {
            console.log(`Moved ${movedCount} items successfully.`);
            await refreshNotes();
            setExpandedFolders(prev => new Set(prev).add(targetNode.path));
            // Keep selection? Or clear? Usually clear or select moved items.
            // Paths changed, so clearing is safer.
            setSelectedPaths(new Set());
        }
        
        if (errors.length > 0) {
             alert(`Failed to move ${errors.length} items.\n${errors.join('\n')}`);
        }

        setDraggedNodes([]);
    };

    const handleRootDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        if (draggedNodes.length === 0) return;
        e.dataTransfer.dropEffect = "move";
    };

    const handleRootDrop = async (e: React.DragEvent) => {
        e.preventDefault();
        const data = e.dataTransfer.getData("text/plain");
        if (!data) return;

        let pathsToMove: string[] = [];
        try {
            pathsToMove = JSON.parse(data);
        } catch {
            pathsToMove = [data];
        }

        const rootPath = noteService.getNotesPath();
        let movedCount = 0;
        let errors = [];

        for (const draggedPath of pathsToMove) {
             const currentParent = draggedPath.substring(0, draggedPath.lastIndexOf('/'));
             if (currentParent === rootPath) continue;

             const success = await noteService.moveItem(draggedPath, rootPath);
             if (success) movedCount++;
             else errors.push(draggedPath);
        }

        if (movedCount > 0) {
            await refreshNotes();
            setSelectedPaths(new Set());
        }

        if (errors.length > 0) {
             alert(`Failed to move ${errors.length} items to root.\n${errors.join('\n')}`);
        }

        setDraggedNodes([]);
        setDragOverNode(null);
    };

    const renderNode = (node: FileNode, depth: number = 0) => {
        const isExpanded = expandedFolders.has(node.path);
        const isActive = currentFile === node.path;
        const isSelected = selectedPaths.has(node.path); // Multi-select state
        const isRenaming = renamingPath === node.path;

        return (
            <div key={node.path}>
                <div 
                    className={`
                        group flex items-center gap-2 px-3 py-1.5 cursor-pointer select-none relative
                        ${isSelected ? 'bg-[#37373d] text-white' : 'text-gray-400 hover:bg-[#2a2a2e] hover:text-gray-200'}
                        ${depth > 0 ? 'ml-4 border-l border-[#333]' : ''}
                        ${dragOverNode === node.path ? 'bg-blue-900/30 outline outline-1 outline-blue-500' : ''}
                    `}
                    style={{ paddingLeft: `${depth * 12 + 12}px` }}
                    draggable={!isRenaming}
                    onDragStart={(e) => handleDragStart(e, node)}
                    onDragOver={(e) => handleDragOver(e, node)}
                    onDrop={(e) => handleDrop(e, node)}
                    onClick={(e) => {
                        if (isRenaming) return;
                        e.stopPropagation(); // Handle click here
                        
                        // Toggle folder if clicking icon/arrow is customary, 
                        // but user usually clicks row to select. 
                        // Let's separate Folder Toggle from Selection if possible?
                        // Standard behavior: Click selects. Double Click renames. 
                        // Arrow click toggles.
                        // Here we don't have separate arrow hit area easily. 
                        // Let's say: Click on row -> Select. 
                        // If Directory -> Toggle too? VSCode toggles on click.
                        
                        const multiSelect = e.metaKey || e.ctrlKey;
                        const rangeSelect = e.shiftKey;
                        
                        handleSelect(node.path, multiSelect, rangeSelect);
                        
                        // Also toggle if directory and single click? 
                        // Maybe only toggle if not modifying selection?
                        if (node.isDirectory && !multiSelect && !rangeSelect) {
                            toggleFolder(node.path);
                        }
                    }}
                    onDoubleClick={(e) => startRenaming(node, e)}
                >
                    {/* Icon */}
                    <span 
                        className="opacity-80 flex-shrink-0"
                        onClick={(e) => {
                            e.stopPropagation();
                            if(node.isDirectory) toggleFolder(node.path);
                        }}
                    >
                        {node.isDirectory ? (
                             isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
                        ) : (
                            <FileText size={14} className={isActive ? 'text-yellow-400' : ''} />
                        )}
                    </span>

                    {/* Name or Input */}
                    <div className="flex-1 truncate text-sm">
                        {isRenaming ? (
                            <input
                                ref={renameInputRef}
                                type="text"
                                value={renameValue}
                                onChange={(e) => setRenameValue(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter') submitRename();
                                    if (e.key === 'Escape') setRenamingPath(null);
                                }}
                                onBlur={submitRename}
                                onClick={(e) => e.stopPropagation()}
                                className="w-full bg-[#1e1e1e] border border-blue-500 text-white px-1 outline-none rounded-sm"
                            />
                        ) : (
                            <span>{node.name}</span>
                        )}
                    </div>

                    {/* Actions (Hover) */}
                    {!isRenaming && (
                        <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-opacity">
                            <button 
                                onClick={(e) => handleDelete(node.path, e)}
                                className="p-0.5 text-gray-500 hover:text-red-400"
                                title="Delete"
                            >
                                <Trash2 size={12} />
                            </button>
                        </div>
                    )}
                </div>

                {/* Children */}
                {node.isDirectory && isExpanded && node.children && (
                    <div>
                        {node.children.map(child => renderNode(child, depth + 1))}
                    </div>
                )}
            </div>
        );
    };

    if (isCollapsed) return null;

    return (
        <div 
            className={`flex flex-col h-full bg-[#1e1e1e] relative group/sidebar ${className}`}
            style={{ width: width, transition: isResizing ? 'none' : 'width 0.1s' }}
        >
             {/* Header */}
            <div className="h-10 px-3 flex items-center justify-between border-b border-[#333] flex-shrink-0 bg-[#252526]">
                {/* No Text, just icons on right, or left? User said remove FOLDERS text. */}
                <div className="flex items-center gap-1">
                     <button onClick={refreshNotes} className="p-1 hover:bg-[#333] rounded text-gray-500 hover:text-gray-300" title="Refresh">
                        <RotateCw size={14} className={isRefreshing ? "animate-spin" : ""} />
                    </button>
                </div>
                <div className="flex items-center gap-1">
                    <button onClick={handleCreateFolder} className="p-1 hover:bg-[#333] rounded text-gray-500 hover:text-gray-300" title="New Folder">
                        <FolderPlus size={16} />
                    </button>
                    <button onClick={handleCreateNote} className="p-1 hover:bg-[#333] rounded text-gray-500 hover:text-gray-300" title="New Note">
                        <Plus size={16} />
                    </button>
                </div>
            </div>

            {/* File List */}
            <div 
                className="flex-1 overflow-y-auto overflow-x-hidden py-2 custom-scrollbar"
                onDragOver={handleRootDragOver}
                onDrop={handleRootDrop}
            >
                {fileTree.map(node => renderNode(node))}
                {fileTree.length === 0 && (
                    <div className="text-center text-xs text-gray-600 mt-4">
                        Empty
                    </div>
                )}
            </div>

            {/* Resize Handle */}
            <div 
                onMouseDown={startResize}
                className="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-blue-500/50 z-10 transition-colors"
            />
        </div>
    );
}
