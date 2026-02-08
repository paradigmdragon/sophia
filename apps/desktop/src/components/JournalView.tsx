import { useState, useEffect } from "react";
import { readTextFile, exists } from '@tauri-apps/plugin-fs';

interface JournalEntry {
    id: string;
    date: string; // YYYY-MM-DD
    time: string; // HH:mm
    content: string;
    type: 'log' | 'note' | 'asr';
}

const LOGS_DIR = "/Users/dragonpd/Sophia/logs";

export function JournalView() {
    const [entries, setEntries] = useState<JournalEntry[]>([]);
    
    // For v0.1, we'll just read the latest log file and display it as journal entries.
    // In future, this should be a proper database or aggregated view.

    useEffect(() => {
        loadJournal();
    }, []);

    const loadJournal = async () => {
        // Mocking timeline from log files
        // 1. Find latest log file
        // 2. Parse lines
        // 3. Convert to entries
        
        try {
            if (!(await exists(LOGS_DIR))) return;
            
            // Get today's log
            const dateStr = new Date().toISOString().split('T')[0];
            // const todayLogPath = `${LOGS_DIR}/${dateStr}.log`; // Assuming simple log format for now or check 'chat' dir
            const chatLogDir = `${LOGS_DIR}/chat`;
            const todayChatLog = `${chatLogDir}/${dateStr}.jsonl`;

            let loadedEntries: JournalEntry[] = [];

            if (await exists(todayChatLog)) {
                 const content = await readTextFile(todayChatLog);
                 const lines = content.split('\n').filter(line => line.trim());
                 
                 loadedEntries = lines.map((line, idx) => {
                     try {
                         const json = JSON.parse(line);
                         return {
                             id: json.message_id || `msg_${idx}`,
                             date: dateStr,
                             time: new Date(json.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}),
                             content: json.content,
                             type: 'log'
                         };
                     } catch {
                         return null;
                     }
                 }).filter(e => e !== null) as JournalEntry[];
            } else {
                // If no log today, add a welcome entry
                loadedEntries.push({
                    id: 'welcome',
                    date: dateStr,
                    time: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}),
                    content: "오늘의 기록이 아직 없습니다.",
                    type: 'note'
                });
            }

            setEntries(loadedEntries.reverse()); // Newest first

        } catch (e) {
            console.error("Failed to load journal", e);
        }
    };

    return (
        <div className="h-full bg-[#1e1e1e] text-gray-300 p-8 overflow-y-auto">
            <h1 className="text-2xl font-bold mb-8 text-white">Sophia Journal</h1>
            
            <div className="space-y-8 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-slate-300 before:to-transparent">
                {entries.map((entry: JournalEntry) => (
                    <div key={entry.id} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
                        {/* Dot */}
                        <div className="flex items-center justify-center w-10 h-10 rounded-full border border-white bg-slate-300 group-[.is-active]:bg-emerald-500 text-slate-500 group-[.is-active]:text-emerald-50 shadow shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2">
                            <div className="w-2 h-2 bg-white rounded-full"></div>
                        </div>
                        
                        {/* Card */}
                        <div className="w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] bg-[#2d2d2d] p-4 rounded border border-[#333] shadow">
                            <div className="flex items-center justify-between space-x-2 mb-1">
                                <span className="font-bold text-gray-400 text-sm">{entry.date}</span>
                                <time className="font-caveat font-medium text-indigo-500 text-xs">{entry.time}</time>
                            </div>
                            <div className="text-gray-200 text-sm leading-relaxed">
                                {entry.content}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
