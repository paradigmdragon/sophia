import { useState, useEffect } from 'react';
import { chatService } from '../lib/chatService';

export function useEpidoraState() {
    const [mode, setMode] = useState<'relaxed' | 'tense'>('relaxed');

    useEffect(() => {
        // Poll logs or use chatService watcher
        // We want to detect if a NEW message with intent='epidora_reveal' appeared recently.
        
        const stopWatching = chatService.watchLogs((messages) => {
            if (messages.length === 0) return;
            
            const lastMsg = messages[messages.length - 1];
            
            // Check if last message is recent (within 10 seconds)
            const msgTime = new Date(lastMsg.timestamp).getTime();
            const now = Date.now();
            
            // Allow 10s window
            if (now - msgTime < 10000) {
                 if (lastMsg.intent === 'epidora_reveal') {
                     setMode('tense');
                 } else {
                     // If user replied or Sophia replied normal, relax?
                     // Or just timeout? Let's stick to timeout or explicit "relax".
                     // Ideally, if a new normal message comes, we might relax.
                     // But for now, just relies on the last message being the error.
                     // If last message IS error, stay tense.
                     // If last message IS NOT error, relax.
                     setMode('relaxed');
                 }
            } else {
                setMode('relaxed');
            }
        }, 1000); // Poll every 1s

        return () => stopWatching();
    }, []);

    return mode;
}
