import { ChevronUp, Loader2 } from "lucide-react";

interface LogEntry {
  timestamp: string;
  message: string;
  type: "info" | "error" | "event";
}

interface LogFooterProps {
  lastLog?: LogEntry;
  onExpand: () => void;
  isProcessing: boolean;
}

export function LogFooter({ lastLog, onExpand, isProcessing }: LogFooterProps) {
  return (
    <div className="area-footer justify-between cursor-pointer hover:bg-[#0a0f1e] relative group" onClick={onExpand}>
      
      {/* Progress Bar Background */}
      {isProcessing && (
        <div className="absolute top-0 left-0 h-[2px] bg-blue-500/20 w-full">
            <div className="h-full bg-blue-500 animate-progress-indeterminate"></div>
        </div>
      )}

      <div className="flex items-center gap-2 overflow-hidden w-full">
        {isProcessing ? (
             <Loader2 size={12} className="text-blue-500 animate-spin shrink-0" />
        ) : (
            <span className="text-blue-500 shrink-0">➜</span>
        )}
        
        {lastLog ? (
            <span className={`truncate text-xs font-mono ${lastLog.type === 'error' ? 'text-red-400' : 'text-gray-500'}`}>
                <span className="opacity-50 mr-2">[{lastLog.timestamp}]</span>
                {lastLog.message}
            </span>
        ) : (
            <span className="text-gray-700 italic text-xs">대기 중...</span>
        )}
      </div>
      <ChevronUp size={12} className="text-gray-600 opacity-50 group-hover:opacity-100" />
    </div>
  );
}
