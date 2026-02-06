import { Settings, RotateCw } from "lucide-react";

interface LogoHeaderProps {
  status: "idle" | "processing";
  onOpenSettings: () => void;
  onRefresh: () => void;
}

export function LogoHeader({ status, onOpenSettings, onRefresh }: LogoHeaderProps) {
  return (
    <div className="area-header">
      <div className="flex items-center gap-2 text-gray-300">
        <span className="font-bold tracking-tight">Sophia</span>
        <span className="text-gray-600">/</span>
        <span className="text-gray-400 text-xs uppercase tracking-wider">Local ASR</span>
      </div>
      
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-2 text-xs font-mono mr-4">
            <span className={`w-2 h-2 rounded-full ${status === 'processing' ? 'bg-blue-400 animate-pulse' : 'bg-gray-600'}`}></span>
            <span className="text-gray-500 uppercase">{status}</span>
        </div>
        
        <button 
            onClick={onRefresh}
            className="p-1.5 text-gray-500 hover:text-white transition-colors bg-[#1e293b]/50 rounded border border-transparent hover:border-[#334155]"
            title="Refresh App"
        >
            <RotateCw size={16} />
        </button>

        <button 
            onClick={onOpenSettings}
            className="p-1.5 text-gray-500 hover:text-white transition-colors bg-[#1e293b]/50 rounded border border-transparent hover:border-[#334155]"
            title="Settings"
        >
            <Settings size={16} />
        </button>
      </div>
    </div>
  );
}
