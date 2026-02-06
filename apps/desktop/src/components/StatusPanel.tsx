import { Play, FolderOpen } from "lucide-react";
import { FileItem } from "./FileQueue";

interface StatusPanelProps {
  selectedFile: FileItem | undefined;
  isProcessing: boolean;
  onStart: () => void;
  onOpenPath: (path: string) => void;
}

export function StatusPanel({ selectedFile, isProcessing, onStart, onOpenPath }: StatusPanelProps) {
  if (!selectedFile) {
    return (
      <div className="area-panel">
        <div className="glass-panel items-center justify-center text-gray-600 gap-4">
            <div className="w-12 h-12 rounded-full bg-[#1e293b] flex items-center justify-center">
                <span className="text-2xl">⚡</span>
            </div>
            <div className="text-center">
                <p className="text-sm font-medium text-gray-400">파일이 선택되지 않았습니다</p>
                <p className="text-xs text-gray-600 mt-1">목록에서 파일을 선택하여 상세 정보를 확인하세요.</p>
            </div>
        </div>
      </div>
    );
  }

  return (
    <div className="area-panel">
      <div className="glass-panel p-6">
      {/* Header Info */}
      <div className="mb-8">
        <h2 className="text-lg font-medium text-white break-all leading-tight mb-2">
            {selectedFile.name}
        </h2>
        <div className="flex items-center gap-4 text-xs text-gray-400 font-mono">
           <span className="bg-[#1e293b] px-2 py-1 rounded border border-[#334155]">
             {selectedFile.path.split('.').pop()?.toUpperCase() || "FILE"}
           </span>
           <span>MD5: (Calculating...)</span>
        </div>
      </div>

      {/* Main Content Area based on Status */}
      <div className="flex-1">
        
        {/* IDLE State */}
        {selectedFile.status === 'idle' && (
            <div className="bg-[#1e293b]/50 border border-dashed border-[#334155] rounded-lg p-6 flex flex-col items-center justify-center gap-4 text-center h-48">
                <div className="text-gray-400 text-sm">변환 준비 완료</div>
                <button 
                    onClick={onStart}
                    disabled={isProcessing}
                    className="primary px-6 py-2 h-9 text-xs rounded-md shadow-lg shadow-blue-500/20"
                >
                    <Play size={14} className="mr-2"/>
                    변환 시작
                </button>
            </div>
        )}

        {/* Processing State */}
        {(selectedFile.status === 'processing' || selectedFile.status === 'refining') && (
            <div className="space-y-6">
                <div className="space-y-2">
                    <div className="flex justify-between text-xs text-gray-400">
                        <span>상태</span>
                        <span className="text-blue-400 uppercase font-bold tracking-wider">{selectedFile.status}</span>
                    </div>
                    {/* Fake Progress Bar for now since we don't have exact percent from backend yet */}
                    <div className="h-1.5 w-full bg-[#1e293b] rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500 w-1/3 animate-pulse rounded-full"></div>
                    </div>
                </div>
                
                <div className="p-4 bg-[#0a0f1e] rounded border border-[#1e293b] font-mono text-xs text-gray-500 space-y-1">
                    <p>Engine: faster-whisper (medium)</p>
                    <p>Device: auto (mps/cuda)</p>
                    <p className="text-blue-400/80">Running inference...</p>
                </div>
            </div>
        )}

        {/* Done State */}
        {selectedFile.status === 'done' && (
             <div className="space-y-6 animate-fade-in">
                <div className="flex items-center gap-2 text-emerald-400 mb-6">
                    <span className="w-2 h-2 bg-emerald-400 rounded-full"></span>
                    <span className="font-medium">변환 완료</span>
                </div>

                <div className="space-y-3">
                    <p className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Outputs</p>
                    
                    {selectedFile.outputPath && (
                        <div className="flex items-center justify-between p-3 bg-[#1e293b] rounded border border-[#334155] hover:border-gray-500 transition-colors group">
                            <div className="flex items-center gap-3">
                                <div className="p-1.5 bg-[#0f172a] rounded text-gray-400 text-xs font-mono">SRT</div>
                                <span className="text-sm text-gray-300">원본 자막 (Raw)</span>
                            </div>
                            <button onClick={() => onOpenPath(selectedFile.outputPath!)} className="hover:text-white text-gray-500">
                                <FolderOpen size={14} /> <span className="text-xs ml-1">Open</span>
                            </button>
                        </div>
                    )}

                    {selectedFile.refinedPath && (
                        <div className="flex items-center justify-between p-3 bg-[#1e293b] rounded border border-[#334155] hover:border-purple-500/50 transition-colors group">
                            <div className="flex items-center gap-3">
                                <div className="p-1.5 bg-[#0f172a] rounded text-purple-400 text-xs font-mono">TXT</div>
                                <span className="text-sm text-gray-300">정제된 텍스트</span>
                            </div>
                            <button onClick={() => onOpenPath(selectedFile.refinedPath!)} className="hover:text-purple-300 text-purple-500/70">
                                <FolderOpen size={14} /> <span className="text-xs ml-1">Open</span>
                            </button>
                        </div>
                    )}
                </div>
             </div>
        )}
        
        {/* Error State */}
        {selectedFile.status === 'error' && (
            <div className="p-4 bg-red-900/10 border border-red-900/50 rounded text-red-400 text-sm">
                <p className="font-bold mb-1">Processing Failed</p>
                <p>{selectedFile.error || "Unknown error occurred"}</p>
            </div>
        )}

      </div>
      
      {/* Panel Footer Actions */}
      {selectedFile.status !== 'processing' && selectedFile.status !== 'refining' && (
          <div className="mt-8 pt-4 border-t border-[#1e293b] flex justify-end">
              {/* Contextual actions could go here */}
          </div>
      )}
      </div>
    </div>
  );
}
