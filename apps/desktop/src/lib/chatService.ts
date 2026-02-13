// apps/desktop/src/lib/chatService.ts
import { Command } from '@tauri-apps/plugin-shell';
import { readTextFile, exists } from '@tauri-apps/plugin-fs';

const LOG_ROOT = '/Users/dragonpd/Sophia/logs/chat';
const CORE_ROOT = '/Users/dragonpd/Sophia/core';
const CHAT_MEMORY_NOTE_THRESHOLD = 240;

export interface ChatMessage {
    message_id: string;
    timestamp: string;
    role: 'user' | 'sophia';
    content: string;
}

export const chatService = {
    /**
     * Sends a message via the Python Backend CLI.
     * This triggers logging, Epidora analysis, and LLM response.
     */
    async sendMessage(text: string): Promise<any> {
        console.log(`Sending message: ${text}`);
        try {
            // Using absolute path to python/cli or assume env.
            // Command: python3 -m app.cli chat "text"
            // Cwd: CORE_ROOT
            const command = Command.create('run-python', [
                '-m', 'app.cli', 'chat', text
            ], { cwd: CORE_ROOT });

            const output = await command.execute();
            console.log('CLI Output:', output);
            
            if (output.code !== 0) {
                console.error('CLI Error:', output.stderr);
                throw new Error(output.stderr);
            }

            try {
                return JSON.parse(output.stdout);
            } catch (e) {
                console.warn('Failed to parse CLI output JSON:', e);
                return null;
            }
        } catch (error) {
            console.error('Failed to execute chat command:', error);
            throw error;
        }
    },

    /**
     * Appends a user chat message into memory/actions.
     * Optionally mirrors long text into memory/notes via threshold rule.
     */
    async appendUserMessageToMemory(
        text: string,
        channel: string = "General",
        noteThreshold: number = CHAT_MEMORY_NOTE_THRESHOLD
    ): Promise<any> {
        try {
            const command = Command.create('run-append-chat-memory', [
                text,
                channel,
                String(noteThreshold)
            ], { cwd: '/Users/dragonpd/Sophia' });

            const output = await command.execute();
            if (output.code !== 0) {
                throw new Error(output.stderr || output.stdout || 'append chat memory failed');
            }

            try {
                return JSON.parse(output.stdout);
            } catch {
                return { status: 'ok' };
            }
        } catch (error) {
            console.error('Failed to append user chat message to memory:', error);
            throw error;
        }
    },

    /**
     * Reads the daily log file.
     */
    async getDailyLogs(): Promise<ChatMessage[]> {
        try {
            // Use local date to match backend's datetime.now()
            const now = new Date();
            const year = now.getFullYear();
            const month = String(now.getMonth() + 1).padStart(2, '0');
            const day = String(now.getDate()).padStart(2, '0');
            const dateStr = `${year}-${month}-${day}`;
            
            const logFile = `${LOG_ROOT}/${dateStr}.jsonl`;

            if (!await exists(logFile)) {
                return [];
            }

            const content = await readTextFile(logFile);
            const lines = content.split('\n').filter(line => line.trim());
            
            return lines.map(line => {
                try {
                    return JSON.parse(line) as ChatMessage;
                } catch (e) {
                    return null;
                }
            }).filter((msg): msg is ChatMessage => msg !== null);

        } catch (error) {
            console.error('Failed to read logs:', error);
            return [];
        }
    },

    /**
     * Simple polling mechanism to watch for log changes.
     * Tauri v2 fs plugin doesn't have robust watch support yet in all environments,
     * so polling is safer for v0.1.
     */
    watchLogs(callback: (messages: ChatMessage[]) => void, intervalMs = 1000): () => void {
        let isWatching = true;
        let lastCount = 0;

        const poll = async () => {
            if (!isWatching) return;
            
            const logs = await this.getDailyLogs();
            if (logs.length !== lastCount) {
                lastCount = logs.length;
                callback(logs);
            }

            if (isWatching) {
                setTimeout(poll, intervalMs);
            }
        };

        poll();

        return () => {
            isWatching = false;
        };
    }
};
