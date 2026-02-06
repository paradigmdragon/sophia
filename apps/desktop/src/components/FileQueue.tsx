import { FileAudio, FileVideo, Plus, Trash2, Loader2, CheckCircle, AlertCircle } from "lucide-react";

export interface FileItem {
  path: string;
  name: string;
  status: "idle" | "processing" | "refining" | "done" | "error";
  error?: string;
  outputPath?: string;
  refinedPath?: string;
}

interface FileQueueProps {
  files: FileItem[];
  selectedFileId: string | null;
  onSelect: (path: string) => void;
  onRemove: (path: string) => void;
  onAddFiles: () => void; // Trigger hidden input usually, or just visually guide
}

export function FileQueue({ files, selectedFileId, onSelect, onRemove, onAddFiles }: FileQueueProps) {
  
  return (
    <div className="area-queue">
      <div className="glass-panel">
        {/* Queue Toolbar */}
        <div className="flex flex-col gap-3 px-6 py-4 border-b border-[#334155] bg-[#1e293b]">
            <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">대기열 ({files.length})</span>
            </div>
            <button 
                className="w-full flex-center gap-2 bg-[#3b82f6] hover:bg-[#2563eb] text-white py-1.5 rounded transition-colors text-xs font-semibold" 
                onClick={onAddFiles}
            >
                <Plus size={14} /> 파일 추가
            </button>
        </div>

        {/* List Area */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-0">
            {files.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-gray-600 gap-3 p-6 text-center">
                    <div className="p-4 rounded-full bg-[#334155]/20 mb-2">
                        <span className="text-2xl opacity-50 block animate-bounce">⬇</span>
                    </div>
                    <div className="space-y-1">
                        <p className="text-sm font-medium text-gray-400">대기 중인 파일이 없습니다</p>
                        <p className="text-xs">이곳에 파일을 드래그하거나<br/><span className="text-blue-400">파일 추가</span> 버튼을 누르세요</p>
                    </div>
                </div>
            ) : (
                <div className="flex flex-col">
                    {files.map(f => (
                        <div 
                            key={f.path}
                            onClick={() => onSelect(f.path)}
                            className={`
                                group flex items-center gap-3 px-6 py-3 border-b border-[#334155]/50 cursor-pointer transition-colors
                                ${selectedFileId === f.path ? 'bg-[#334155] border-l-4 border-l-blue-500 pl-[20px]' : 'hover:bg-[#334155]/30 border-l-4 border-l-transparent pl-[20px]'}
                            `}
                        >
                            {/* Icon */}
                            <div className={`
                                text-gray-500
                                ${f.status === 'processing' || f.status === 'refining' ? 'text-blue-400' : ''}
                                ${f.status === 'done' ? 'text-emerald-500' : ''}
                                ${f.status === 'error' ? 'text-red-500' : ''}
                            `}>
                                {f.status === 'processing' || f.status === 'refining' ? (
                                    <Loader2 size={14} className="animate-spin"/>
                                ) : f.status === 'done' ? (
                                    <CheckCircle size={14} />
                                ) : f.status === 'error' ? (
                                    <AlertCircle size={14} />
                                ) : (
                                    ["mp4", "mov", "mkv"].some(ext => f.name.endsWith(ext)) ? <FileVideo size={14}/> : <FileAudio size={14}/>
                                )}
                            </div>

                            {/* Name */}
                            <div className="flex-1 min-w-0 flex flex-col gap-0.5">
                                <span className={`text-sm truncate ${selectedFileId === f.path ? 'text-white' : 'text-gray-300'}`}>
                                    {f.name}
                                </span>
                                <span className="text-[10px] text-gray-500 uppercase tracking-tight font-mono">
                                    {f.status}
                                </span>
                            </div>

                            {/* Hover Action */}
                            <div className="opacity-0 group-hover:opacity-100">
                                <button 
                                    onClick={(e) => { e.stopPropagation(); onRemove(f.path); }}
                                    className="p-1 hover:text-red-400 text-gray-600"
                                >
                                    <Trash2 size={12} />
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
      </div>
    </div>
  );
}
