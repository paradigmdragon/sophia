import { useState, useEffect } from "react";
import { readDir, exists } from '@tauri-apps/plugin-fs';
// import { join } from '@tauri-apps/api/path'; // Use manual string concat for v0.1 specific scope

const LOGS_DIR = "/Users/dragonpd/Sophia/logs";
const DOCS_DIR = "/Users/dragonpd/Sophia/docs";

interface FileNode {
    name: string;
    path: string;
    isDir: boolean;
    children?: FileNode[];
}

export function SourceExplorer() {
    const [nodes, setNodes] = useState<FileNode[]>([]);
    
    useEffect(() => {
        loadFiles();
        // File watcher could be added here later (polling or watch API)
        const interval = setInterval(loadFiles, 5000);
        return () => clearInterval(interval);
    }, []);

    const loadFiles = async () => {
        try {
            const logNodes = await loadDir(LOGS_DIR, "Logs");
            const docNodes = await loadDir(DOCS_DIR, "Docs");
            setNodes([logNodes, docNodes]);
        } catch (e) {
            console.error("Failed to load source explorer:", e);
        }
    };

    const loadDir = async (path: string, label: string): Promise<FileNode> => {
        try {
            if (!(await exists(path))) return { name: label, path, isDir: true, children: [] };
            
            const entries = await readDir(path);
            const children = await Promise.all(entries.map(async (entry) => {
                const fullPath = `${path}/${entry.name}`;
                if (entry.isDirectory) {
                    return loadDir(fullPath, entry.name);
                }
                return { name: entry.name, path: fullPath, isDir: false };
            }));
            
            // Sort folders first, then files
            children.sort((a, b) => {
                if (a.isDir && !b.isDir) return -1;
                if (!a.isDir && b.isDir) return 1;
                return a.name.localeCompare(b.name);
            });

            return { name: label, path, isDir: true, children };
        } catch (e) {
            console.error(`Error reading ${path}:`, e);
            return { name: label, path, isDir: true, children: [] }; // Return empty on error
        }
    };

    const handleDragStart = (e: React.DragEvent, node: FileNode) => {
        e.dataTransfer.setData("text/plain", node.path);
        e.dataTransfer.setData("application/sophia-file", JSON.stringify(node));
        e.dataTransfer.effectAllowed = "copyLink";
    };

    const renderTree = (node: FileNode, level: number = 0) => {
        return (
            <div key={node.path} style={{ paddingLeft: `${level * 12}px` }}>
                <div 
                    className={`flex items-center py-1 hover:bg-white/5 cursor-pointer text-sm ${node.isDir ? 'font-bold text-gray-300' : 'text-gray-400'}`}
                    draggable={!node.isDir}
                    onDragStart={(e) => handleDragStart(e, node)}
                >
                    <span className="mr-2">{node.isDir ? (level === 0 ? '📂' : '📁') : '📄'}</span>
                    <span className="truncate">{node.name}</span>
                </div>
                {node.isDir && node.children && (
                    <div>
                        {node.children.map(child => renderTree(child, level + 1))}
                    </div>
                )}
            </div>
        );
    };

    return (
        <div className="h-full bg-[#1e1e1e] border-r border-[#333] overflow-y-auto p-2">
            <h3 className="text-xs font-bold text-gray-500 uppercase mb-2">Source Explorer</h3>
            {nodes.map(node => renderTree(node))}
        </div>
    );
}
