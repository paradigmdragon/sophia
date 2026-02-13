import { FileText, Database, Activity, Cpu } from "lucide-react";
import { NotesPanel } from "./panels/NotesPanel";
import { MemoryPanel } from "./panels/MemoryPanel";
import { AuditPanel } from "./panels/AuditPanel";
import { SkillsPanel } from "./panels/SkillsPanel";

export type PanelTab = "notes" | "memory" | "audit" | "skills";

interface ActivePanelProps {
    activeTab: PanelTab;
    onTabChange: (tab: PanelTab) => void;
    className?: string; // Support drawer styling
    refreshToken?: number;
}

export function ActivePanel({ activeTab, onTabChange, className = "", refreshToken = 0 }: ActivePanelProps) {
    const tabs = [
        { id: "notes", icon: FileText, label: "Notes" },
        { id: "memory", icon: Database, label: "Memory" },
        { id: "audit", icon: Activity, label: "Audit" },
        { id: "skills", icon: Cpu, label: "Skills" },
    ] as const;

    return (
        <div className={`flex flex-col h-full bg-[#1e1e1e] border-l border-[#333] ${className}`}>
            {/* Tab Bar */}
            <div className="flex items-center border-b border-[#333] bg-[#252526]">
                {tabs.map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => onTabChange(tab.id as PanelTab)}
                        className={`
                            flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors
                            ${activeTab === tab.id 
                                ? "text-blue-400 border-b-2 border-blue-400 bg-[#1e1e1e]" 
                                : "text-gray-400 hover:text-gray-200 hover:bg-[#2a2a2e]"
                            }
                        `}
                    >
                        <tab.icon size={16} />
                        <span>{tab.label}</span>
                    </button>
                ))}
            </div>

            {/* Search / Filter (Placeholder) */}
            <div className="p-2 border-b border-[#333]">
                <input 
                    type="text" 
                    placeholder="Search in panel..." 
                    className="w-full bg-[#1e1e1e] border border-[#333] rounded px-3 py-1.5 text-xs text-gray-300 focus:border-blue-500 outline-none"
                />
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-hidden relative">
                {activeTab === "notes" && <NotesPanel refreshToken={refreshToken} />}
                {activeTab === "memory" && <MemoryPanel refreshToken={refreshToken} />}
                {activeTab === "audit" && <AuditPanel />}
                {activeTab === "skills" && <SkillsPanel />}
            </div>

            {/* Action Footer (Placeholder) */}
            {/* <div className="p-2 border-t border-[#333] bg-[#252526] text-xs text-gray-500">
                Panel Actions
            </div> */}
        </div>
    );
}
