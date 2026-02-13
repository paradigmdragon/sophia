import { readTextFile, exists } from '@tauri-apps/plugin-fs';
import { Command } from '@tauri-apps/plugin-shell';

const WORKSPACE_ROOT = '/Users/dragonpd/Sophia/sophia_workspace';
const MEMORY_ROOT = `${WORKSPACE_ROOT}/memory`;

export type MemoryNamespace = 'notes' | 'ideas' | 'decisions' | 'actions';

export interface MemoryItem {
    namespace: MemoryNamespace;
    raw: string;
    parsed: any;
    timestamp?: string; // Derived from parsed data if available
}

export const memoryService = {
    async listMemory(namespace: MemoryNamespace | 'all', limit: number = 50): Promise<MemoryItem[]> {
        const namespaces: MemoryNamespace[] = namespace === 'all' 
            ? ['notes', 'ideas', 'decisions', 'actions'] 
            : [namespace];

        let allItems: MemoryItem[] = [];

        for (const ns of namespaces) {
            const path = `${MEMORY_ROOT}/${ns}.jsonl`;
            try {
                if (await exists(path)) {
                    const content = await readTextFile(path);
                    const lines = content.split('\n').filter(line => line.trim() !== '');
                    
                    // Parse lines in reverse order (newest first)
                    const items: MemoryItem[] = lines.reverse().slice(0, limit).map(line => {
                        let parsed = null;
                        try {
                            parsed = JSON.parse(line);
                        } catch (e) {
                            // Keep raw if parse fails
                        }

                        // Try to extract a timestamp if present in common fields
                        let timestamp = undefined;
                        if (parsed) {
                           if (parsed.created_at) timestamp = parsed.created_at;
                           else if (parsed.timestamp) timestamp = parsed.timestamp;
                           else if (parsed.timestamps && parsed.timestamps.created_at) timestamp = parsed.timestamps.created_at;
                        }

                        return {
                            namespace: ns,
                            raw: line,
                            parsed: parsed || {},
                            timestamp
                        };
                    });
                    
                    allItems = [...allItems, ...items];
                }
            } catch (e) {
                console.error(`Failed to read memory file: ${path}`, e);
            }
        }

        // Re-sort combined list by timestamp if multiple namespaces merged
        if (namespace === 'all') {
             allItems.sort((a, b) => {
                 const tA = a.timestamp ? new Date(a.timestamp).getTime() : 0;
                 const tB = b.timestamp ? new Date(b.timestamp).getTime() : 0;
                 return tB - tA;
             });
             return allItems.slice(0, limit);
        }

        return allItems;
    },

    async getAvailableDates(namespace: MemoryNamespace): Promise<string[]> {
        const path = `${MEMORY_ROOT}/${namespace}.jsonl`;
        try {
            if (!(await exists(path))) return [];
            const content = await readTextFile(path);
            const lines = content.split('\n').filter(line => line.trim() !== '');
            
            const dates = new Set<string>();
            lines.forEach(line => {
                try {
                    const parsed = JSON.parse(line);
                    // Check various date fields
                    let ts = parsed.created_at || parsed.timestamp || (parsed.timestamps && parsed.timestamps.created_at);
                    if (ts) {
                        const dateStr = new Date(ts).toISOString().split('T')[0];
                        dates.add(dateStr);
                    }
                } catch (e) {}
            });
            
            // Return sorted descending
            return Array.from(dates).sort().reverse();
        } catch (e) {
            console.error(`Failed to get dates for ${namespace}`, e);
            return [];
        }
    },

    async listMessagesByDate(namespace: MemoryNamespace, dateStr: string): Promise<MemoryItem[]> {
        const all = await this.listMemory(namespace, 1000);
        return all.filter(item => {
            if (!item.timestamp) return false;
            const itemDate = new Date(item.timestamp).toISOString().split('T')[0];
            return itemDate === dateStr;
        });
    },

    async appendNote(data: { title: string, body: string, tags: string[], date: string }): Promise<void> {
        try {
            const command = Command.create('run-append-note', [
                data.title, 
                data.body, 
                data.tags.join(','), 
                data.date
            ]);
            
            const output = await command.execute();
            if (output.code !== 0) {
                throw new Error(`Script failed with code ${output.code}: ${output.stderr}`);
            }
            
            console.log("Append note result:", output.stdout);
        } catch (e) {
            console.error("Append note failed", e);
            throw e;
        }
    }
};
