const API_BASE = 'http://localhost:8090';

export type MemoryNamespace = 'notes' | 'ideas' | 'decisions' | 'actions';

export interface MemoryItem {
    namespace: MemoryNamespace;
    raw: string;
    parsed: any;
    timestamp?: string; // Derived from parsed data if available
}

export interface SophiaSystemNote {
    id: string;
    verse_id?: number;
    created_at: string;
    title: string;
    note_type: string;
    source_events: string[];
    summary: string;
    body_markdown: string;
    status: string;
    actionables: Array<Record<string, unknown>>;
    linked_cluster_id?: string | null;
    risk_score?: number | null;
    dedup_key?: string;
    badge?: string;
    raw?: Record<string, unknown>;
}

export interface SophiaNoteGeneratorStatus {
    last_generated_at: string;
    generator_status: 'idle' | 'running' | 'failed' | string;
    last_trigger: string;
    empty_reasons: string[];
    last_error: string;
}

export interface MindItem {
    id: string;
    type: 'TASK' | 'QUESTION_CLUSTER' | 'ALERT' | 'FOCUS' | string;
    title: string;
    summary_120: string;
    priority: number;
    risk_score: number;
    confidence: number;
    linked_bits: string[];
    tags: string[];
    source_events: string[];
    status: 'active' | 'parked' | 'done' | string;
    created_at: string;
    updated_at: string;
}

export interface MindWorkingLogLine {
    id: number;
    line: string;
    event_type: string;
    item_id?: string | null;
    delta_priority: number;
    created_at?: string;
}

export interface MindDashboard {
    focus_items: MindItem[];
    question_clusters: MindItem[];
    risk_alerts: MindItem[];
    working_log: MindWorkingLogLine[];
    active_tags: string[];
    items: MindItem[];
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
        headers: {
            'Content-Type': 'application/json',
            ...(init?.headers || {}),
        },
        ...init,
    });
    if (!response.ok) {
        const text = await response.text();
        throw new Error(`HTTP ${response.status}: ${text}`);
    }
    return response.json() as Promise<T>;
}

function toMemoryItem(item: any): MemoryItem {
    const parsed = item?.parsed && typeof item.parsed === 'object'
        ? item.parsed
        : (typeof item?.content === 'string' ? { text: item.content } : {});
    const raw = typeof item?.content === 'string'
        ? item.content
        : JSON.stringify(parsed);
    const timestamp = item?.created_at || item?.timestamp;
    const namespace = (item?.namespace || parsed?.__namespace || 'notes') as MemoryNamespace;
    return { namespace, raw, parsed, timestamp };
}

export const memoryService = {
    async listMemory(namespace: MemoryNamespace | 'all', limit: number = 50): Promise<MemoryItem[]> {
        const namespaces: MemoryNamespace[] = namespace === 'all'
            ? ['notes', 'ideas', 'decisions', 'actions']
            : [namespace];

        const responses = await Promise.all(
            namespaces.map((ns) =>
                fetchJson<{ items: any[] }>(`/memory/verses?namespace=${encodeURIComponent(ns)}&limit=${limit}`)
                    .catch((e) => {
                        console.error(`Failed to fetch memory namespace=${ns}`, e);
                        return { items: [] };
                    })
            )
        );

        const allItems = responses.flatMap((res) => (res.items || []).map(toMemoryItem));
        allItems.sort((a, b) => {
            const tA = a.timestamp ? new Date(a.timestamp).getTime() : 0;
            const tB = b.timestamp ? new Date(b.timestamp).getTime() : 0;
            return tB - tA;
        });
        return allItems.slice(0, limit);
    },

    async getAvailableDates(namespace: MemoryNamespace): Promise<string[]> {
        try {
            const result = await fetchJson<{ dates: string[] }>(`/memory/dates?namespace=${encodeURIComponent(namespace)}`);
            return Array.isArray(result.dates) ? result.dates : [];
        } catch (e) {
            console.error(`Failed to get dates for ${namespace}`, e);
            return [];
        }
    },

    async listMessagesByDate(namespace: MemoryNamespace, dateStr: string): Promise<MemoryItem[]> {
        const result = await fetchJson<{ items: any[] }>(
            `/memory/chapters?date=${encodeURIComponent(dateStr)}&namespace=${encodeURIComponent(namespace)}&limit=2000`
        );
        return (result.items || []).map(toMemoryItem);
    },

    async listSophiaNotesByDate(dateStr: string, includeArchived = false): Promise<SophiaSystemNote[]> {
        const result = await fetchJson<{ items: SophiaSystemNote[] }>(
            `/memory/notes?date=${encodeURIComponent(dateStr)}&include_archived=${includeArchived ? 'true' : 'false'}&system_generated_only=true&limit=500`
        );
        return Array.isArray(result.items) ? result.items : [];
    },

    async listSophiaNoteDates(includeArchived = false): Promise<string[]> {
        const result = await fetchJson<{ dates: string[] }>(
            `/memory/notes/dates?include_archived=${includeArchived ? 'true' : 'false'}`
        );
        return Array.isArray(result.dates) ? result.dates : [];
    },

    async getSophiaNoteGeneratorStatus(): Promise<SophiaNoteGeneratorStatus> {
        return fetchJson<SophiaNoteGeneratorStatus>(`/memory/notes/status`);
    },

    async triggerSophiaNoteGenerateNow(reason = 'manual_refresh'): Promise<{ status: string; created: boolean }> {
        return fetchJson<{ status: string; created: boolean }>(`/memory/notes/generate`, {
            method: 'POST',
            body: JSON.stringify({ reason }),
        });
    },

    async getMindDashboard(): Promise<MindDashboard> {
        return fetchJson<MindDashboard>(`/mind/dashboard`);
    },

    async adjustMindItem(
        itemId: string,
        action: 'pin' | 'boost' | 'park' | 'done' | 'label',
        label?: string,
    ): Promise<{ status: string }> {
        return fetchJson<{ status: string }>(`/mind/items/${encodeURIComponent(itemId)}/${action}`, {
            method: 'POST',
            body: JSON.stringify({ label }),
        });
    },

    async appendNote(data: { title: string, body: string, tags: string[], date: string }): Promise<void> {
        try {
            await fetchJson(`/memory/verse`, {
                method: 'POST',
                body: JSON.stringify({
                    namespace: 'notes',
                    date: data.date,
                    speaker: 'User',
                    content: {
                        title: data.title,
                        body: data.body,
                        tags: data.tags,
                        refs: { date: data.date, source: 'ui' },
                        v: 'note_v0',
                        __namespace: 'notes',
                    },
                }),
            });
        } catch (e) {
            console.error("Append note failed", e);
            throw e;
        }
    }
};
