import React, { useRef, useState, useEffect } from "react";
import Editor, { OnMount } from "@monaco-editor/react";

interface MarkdownEditorProps {
    initialContent?: string;
    onChange?: (value: string) => void;
    className?: string; // Added to fix lint error in NotePage too if we keep it there temporarily
}

export function MarkdownEditor({ initialContent = "", onChange, className }: MarkdownEditorProps) {
    const editorRef = useRef<any>(null);
    const [content, setContent] = useState(initialContent || localStorage.getItem("sophia_draft_v1") || "# Sophia Notebook\n\nStart thinking...");

    const handleEditorDidMount: OnMount = (editor, monaco) => {
        editorRef.current = editor;
        
        // Drag and Drop Logic
        // Monaco handles text drag/drop natively. 
        // We want to intercept file drop from our SourceExplorer.
        // We can listen to container drop event.
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        const path = e.dataTransfer.getData("text/plain");
        const nodeJson = e.dataTransfer.getData("application/sophia-file");
        
        if (path && nodeJson) {
            const node = JSON.parse(nodeJson);
            const fileName = node.name;
            
            // Format: > 💡 [Reference: filename] (Target: path)
            const citation = `\n> 💡 [Reference: ${fileName}](file://${path})\n`;
            
            insertAtCursor(citation);
        }
    };
    
    const insertAtCursor = (text: string) => {
        const editor = editorRef.current;
        if (editor) {
            const position = editor.getPosition();
            editor.executeEdits("citation", [{
                range: {
                    startLineNumber: position?.lineNumber || 1,
                    startColumn: position?.column || 1,
                    endLineNumber: position?.lineNumber || 1,
                    endColumn: position?.column || 1
                },
                text: text,
                forceMoveMarkers: true
            }]);
        }
    };

    const handleChange = (value: string | undefined) => {
        if (value !== undefined) {
            setContent(value);
            localStorage.setItem("sophia_draft_v1", value);
            if (onChange) {
                onChange(value);
            }
        }
    };

    return (
        <div 
            className="h-full w-full" 
            onDrop={handleDrop} 
            onDragOver={(e) => e.preventDefault()}
        >
            <Editor
                height="100%"
                defaultLanguage="markdown"
                theme="vs-dark"
                value={content}
                onChange={handleChange}
                onMount={handleEditorDidMount}
                options={{
                    wordWrap: 'on',
                    minimap: { enabled: false },
                    fontSize: 14,
                    padding: { top: 20 }
                }}
            />
        </div>
    );
}
