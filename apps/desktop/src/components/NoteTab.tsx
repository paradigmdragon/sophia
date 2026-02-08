import { SourceExplorer } from "./SourceExplorer";
import { MarkdownEditor } from "./MarkdownEditor";

export function NoteTab() {
    return (
        <div className="flex h-full w-full relative">
            {/* Left Pane: Source Explorer */}
            <div className="w-64 h-full flex-shrink-0 border-r border-[#333]">
                <SourceExplorer />
            </div>

            {/* Center Pane: Workbench (Expanded) */}
            <div className="flex-1 h-full min-w-0 bg-[#1e1e1e]">
                <MarkdownEditor />
            </div>
        </div>
    );
}

