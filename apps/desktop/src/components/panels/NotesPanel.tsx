import { FileSidebar } from "../FileSidebar";

interface NotesPanelProps {
    refreshToken?: number;
}

export function NotesPanel({ refreshToken = 0 }: NotesPanelProps) {
    // Reusing FileSidebar for now. 
    // In future, this could be a more specialized view.
    return (
        <FileSidebar 
            key={`notes-panel-${refreshToken}`}
            onSelectFile={(path) => console.log("Selected:", path)} 
            currentFile={null} 
            isCollapsed={false} 
            className="w-full border-none"
        />
    );
}
