import { useState, useEffect } from "react";
import { LineWrapSettings, DEFAULT_SETTINGS } from "../components/SettingsModal";

export function SettingsPage() {
    // Reusing the logic from SettingsModal but rendered as a page
    const [settings, setSettings] = useState<LineWrapSettings>(DEFAULT_SETTINGS);

    useEffect(() => {
        const stored = localStorage.getItem("sophia_settings_v1");
        if (stored) {
            try {
            } catch (e) { console.error("Failed to load settings", e); }
        }
    }, []);

    const handleSave = (newSettings: LineWrapSettings) => {
        setSettings(newSettings);
        localStorage.setItem("sophia_settings_v1", JSON.stringify({ line_wrap: newSettings }));
    };



    return (
        <div className="h-full w-full flex flex-col bg-[#1e1e1e] text-gray-200 items-center pt-10 overflow-auto">
             <div className="w-full max-w-2xl bg-[#1e293b] rounded-xl border border-[#334155] p-8 shadow-2xl mb-10">
                <div className="flex items-center justify-between mb-8 border-b border-[#334155] pb-4">
                    <h2 className="text-2xl font-bold flex items-center gap-3 text-gray-100">
                        <span className="text-3xl">⚙️</span> 설정
                    </h2>
                </div>
                
                <div className="space-y-8">
                  {/* Section: Refiner Line Wrap */}
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <h3 className="text-base font-semibold text-blue-400 uppercase tracking-wider">자동 라인 줄바꿈 (Line Wrapping)</h3>
                            <p className="text-sm text-gray-400 mt-1">정제된 자막(refined.txt, refined.srt)에만 적용됩니다.</p>
                        </div>
                        <div className="flex items-center gap-2">
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input 
                                    type="checkbox" 
                                    className="sr-only peer"
                                    checked={settings.enabled}
                                    onChange={(e) => handleSave({...settings, enabled: e.target.checked})}
                                />
                                <div className="w-11 h-6 bg-[#334155] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                            </label>
                        </div>
                    </div>

                    <div className={`space-y-6 p-6 rounded-lg border border-[#334155] bg-[#0f172a]/30 transition-opacity ${settings.enabled ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
                        
                        {/* Presets */}
                        <div className="flex gap-2 mb-4">
                            <button onClick={() => updateSettingAndSave({ ...settings, enabled: true, max_chars: 22, max_lines_per_cue: 2, keep_words: true })} className="px-4 py-2 text-xs font-medium bg-[#334155] hover:bg-[#475569] text-gray-200 rounded-md border border-[#475569] transition-colors">
                                한국어 표준 (22자)
                            </button>
                             <button onClick={() => updateSettingAndSave({ ...settings, enabled: true, max_chars: 16, max_lines_per_cue: 2, keep_words: true })} className="px-4 py-2 text-xs font-medium bg-[#334155] hover:bg-[#475569] text-gray-200 rounded-md border border-[#475569] transition-colors">
                                컴팩트 (16자)
                            </button>
                        </div>

                        {/* Max Chars */}
                        <div className="space-y-3">
                            <div className="flex justify-between text-sm text-gray-300 font-medium">
                                <span>최대 줄 길이 (글자 수)</span>
                                <span className="font-mono text-blue-400 font-bold text-lg">{settings.max_chars}</span>
                            </div>
                            <input 
                                type="range" 
                                min="10" 
                                max="40" 
                                step="1"
                                value={settings.max_chars}
                                onChange={(e) => handleSave({...settings, max_chars: parseInt(e.target.value)})}
                                className="w-full h-2 bg-[#334155] rounded-lg appearance-none cursor-pointer accent-blue-500"
                            />
                             <div className="flex justify-between text-xs text-gray-500 font-mono px-1">
                                <span>10</span>
                                <span>40</span>
                            </div>
                        </div>

                        {/* Max Lines */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-gray-300 block">자막당 최대 줄 수</label>
                            <select 
                                value={settings.max_lines_per_cue}
                                onChange={(e) => handleSave({...settings, max_lines_per_cue: parseInt(e.target.value)})}
                                className="w-full bg-[#1e293b] border border-[#334155] text-gray-200 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block p-2.5"
                            >
                                <option value={1}>1줄</option>
                                <option value={2}>2줄 (표준)</option>
                                <option value={3}>3줄</option>
                                <option value={4}>4줄</option>
                            </select>
                        </div>

                        {/* Toggles */}
                        <div className="grid grid-cols-2 gap-6 pt-2">
                             <label className="flex items-center cursor-pointer gap-3 p-2 rounded hover:bg-[#334155]/20">
                                <input 
                                    type="checkbox" 
                                    className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-600 ring-offset-gray-800"
                                    checked={settings.keep_words}
                                    onChange={(e) => handleSave({...settings, keep_words: e.target.checked})}
                                />
                                <span className="text-sm text-gray-300 font-medium">단어 단위 유지 (Keep Words)</span>
                            </label>

                            <label className="flex items-center cursor-pointer gap-3 p-2 rounded hover:bg-[#334155]/20">
                                <input 
                                    type="checkbox" 
                                    className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-600 ring-offset-gray-800"
                                    checked={settings.hanging_punctuation}
                                    onChange={(e) => handleSave({...settings, hanging_punctuation: e.target.checked})}
                                />
                                <span className="text-sm text-gray-300 font-medium">문장 부호 라인 끝 허용</span>
                            </label>
                        </div>

                    </div>
                  </div>
                </div>

             </div>
        </div>
    );
     
    // Helper to update state and save immediately (for preset buttons)
    function updateSettingAndSave(newSettings: LineWrapSettings) {
        handleSave(newSettings);
    }
}
