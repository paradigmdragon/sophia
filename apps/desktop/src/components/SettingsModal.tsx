import { useState, useEffect } from "react";
import { X, Save, RotateCcw } from "lucide-react";

export interface LineWrapSettings {
  enabled: boolean;
  max_chars: number;
  max_lines_per_cue: number;
  break_priority: string[]; // "punctuation", "space", "hard"
  keep_words: boolean;
  hanging_punctuation: boolean;
}

export const DEFAULT_SETTINGS: LineWrapSettings = {
  enabled: false,
  max_chars: 22,
  max_lines_per_cue: 2,
  break_priority: ["punctuation", "space", "hard"],
  keep_words: true,
  hanging_punctuation: false,
};

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: LineWrapSettings;
  onSave: (newSettings: LineWrapSettings) => void;
}

export function SettingsModal({ isOpen, onClose, settings, onSave }: SettingsModalProps) {
  const [localSettings, setLocalSettings] = useState<LineWrapSettings>(settings);

  // Reset local state when modal opens or settings change externally
  useEffect(() => {
    setLocalSettings(settings);
  }, [settings, isOpen]);

  if (!isOpen) return null;

  const handleSave = () => {
    onSave(localSettings);
    onClose();
  };

  const applyPreset = (type: "korean" | "compact") => {
    if (type === "korean") {
        setLocalSettings(prev => ({
            ...prev,
            enabled: true,
            max_chars: 22,
            max_lines_per_cue: 2,
            keep_words: true
        }));
    } else if (type === "compact") {
         setLocalSettings(prev => ({
            ...prev,
            enabled: true,
            max_chars: 16,
            max_lines_per_cue: 2,
            keep_words: true
        }));
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-[500px] bg-[#1e293b] border border-[#334155] rounded-xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden animate-in fade-in zoom-in duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#334155] bg-[#0f172a]/50">
          <h2 className="text-lg font-semibold text-gray-100 flex items-center gap-2">
            <span className="text-xl">⚙️</span> 설정
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto space-y-8">
          
          {/* Section: Refiner Line Wrap */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
                <div>
                    <h3 className="text-sm font-medium text-blue-400 uppercase tracking-wider">자동 라인 줄바꿈 (Line Wrapping)</h3>
                    <p className="text-xs text-gray-500 mt-1">정제된 자막(refined.txt, refined.srt)에만 적용됩니다.</p>
                </div>
                <div className="flex items-center gap-2">
                    <label className="relative inline-flex items-center cursor-pointer">
                        <input 
                            type="checkbox" 
                            className="sr-only peer"
                            checked={localSettings.enabled}
                            onChange={(e) => setLocalSettings({...localSettings, enabled: e.target.checked})}
                        />
                        <div className="w-11 h-6 bg-[#334155] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                    </label>
                </div>
            </div>

            <div className={`space-y-6 p-4 rounded-lg border border-[#334155] bg-[#0f172a]/30 transition-opacity ${localSettings.enabled ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
                
                {/* Presets */}
                <div className="flex gap-2 mb-2">
                    <button onClick={() => applyPreset('korean')} className="px-3 py-1.5 text-xs bg-[#334155] hover:bg-[#475569] text-gray-200 rounded border border-[#475569] transition-colors">
                        한국어 표준 (22자)
                    </button>
                     <button onClick={() => applyPreset('compact')} className="px-3 py-1.5 text-xs bg-[#334155] hover:bg-[#475569] text-gray-200 rounded border border-[#475569] transition-colors">
                        컴팩트 (16자)
                    </button>
                </div>

                {/* Max Chars */}
                <div className="space-y-2">
                    <div className="flex justify-between text-sm text-gray-300">
                        <span>최대 줄 길이 (글자 수)</span>
                        <span className="font-mono text-blue-400 font-bold">{localSettings.max_chars}</span>
                    </div>
                    <input 
                        type="range" 
                        min="10" 
                        max="40" 
                        step="1"
                        value={localSettings.max_chars}
                        onChange={(e) => setLocalSettings({...localSettings, max_chars: parseInt(e.target.value)})}
                        className="w-full h-2 bg-[#334155] rounded-lg appearance-none cursor-pointer accent-blue-500"
                    />
                     <div className="flex justify-between text-xs text-gray-600 font-mono">
                        <span>10</span>
                        <span>40</span>
                    </div>
                </div>

                {/* Max Lines */}
                <div className="space-y-2">
                    <label className="text-sm text-gray-300 block">자막당 최대 줄 수</label>
                    <select 
                        value={localSettings.max_lines_per_cue}
                        onChange={(e) => setLocalSettings({...localSettings, max_lines_per_cue: parseInt(e.target.value)})}
                        className="w-full bg-[#1e293b] border border-[#334155] text-gray-200 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block p-2.5"
                    >
                        <option value={1}>1줄</option>
                        <option value={2}>2줄 (표준)</option>
                        <option value={3}>3줄</option>
                        <option value={4}>4줄</option>
                    </select>
                </div>

                {/* Toggles */}
                <div className="grid grid-cols-2 gap-4">
                     <label className="flex items-center cursor-pointer gap-2">
                        <input 
                            type="checkbox" 
                            className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-600 ring-offset-gray-800"
                            checked={localSettings.keep_words}
                            onChange={(e) => setLocalSettings({...localSettings, keep_words: e.target.checked})}
                        />
                        <span className="text-sm text-gray-300">단어 단위 유지 (Keep Words)</span>
                    </label>

                    <label className="flex items-center cursor-pointer gap-2">
                        <input 
                            type="checkbox" 
                            className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-600 ring-offset-gray-800"
                            checked={localSettings.hanging_punctuation}
                            onChange={(e) => setLocalSettings({...localSettings, hanging_punctuation: e.target.checked})}
                        />
                        <span className="text-sm text-gray-300">문장 부호 라인 끝 허용</span>
                    </label>
                </div>

            </div>
          </div>

        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[#334155] bg-[#0f172a]/50 flex justify-end gap-3">
             <button 
                onClick={() => setLocalSettings(DEFAULT_SETTINGS)}
                className="flex items-center px-4 py-2 text-sm font-medium text-gray-400 hover:text-white transition-colors gap-2"
            >
                <RotateCcw size={14} />
                초기화
            </button>
            <button 
                onClick={handleSave}
                className="flex items-center px-6 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-lg shadow-blue-500/20 transition-all gap-2"
            >
                <Save size={16} />
                설정 저장
            </button>
        </div>

      </div>
    </div>
  );
}
