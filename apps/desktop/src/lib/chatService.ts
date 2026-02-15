const API_BASE = 'http://localhost:8090';

export interface ChatMessage {
    id: string;
    message_id: string;
    created_at: string;
    timestamp: string;
    role: 'user' | 'sophia';
    content: string;
    context_tag: string;
    importance: number;
    emotion_signal: string | null;
    linked_cluster: string | null;
    linked_node: string | null;
    status: 'normal' | 'pending' | 'escalated' | 'acknowledged' | 'resolved' | 'read';
    intent?: string;
    context?: any;
    priority?: string;
    message_type?: string;
}

export interface SendMessageResponse {
    status: string;
    reply?: string;
    context_tag: string;
    messages: ChatMessage[];
    pending_inserted: ChatMessage[];
}

export interface QuestionPoolItem {
    cluster_id: string;
    description: string;
    hit_count: number;
    risk_score: number;
    evidence: Array<{ snippet: string; source: string; timestamp: string }>;
    linked_nodes: string[];
    status: string;
    last_triggered_at: string;
    last_asked_at: string;
    asked_count: number;
}

export interface WorkPackageItem {
    id: string;
    title: string;
    description: string | null;
    payload: Record<string, unknown>;
    work_packet?: {
        id: string;
        kind: 'ANALYZE' | 'IMPLEMENT' | 'REVIEW' | 'MIGRATE';
        context_tag: string;
        linked_node?: string | null;
        acceptance_criteria: string[];
        deliverables: string[];
        return_payload_spec: Record<string, unknown>;
    };
    packet_text?: string;
    context_tag: string;
    status: string;
    linked_node: string | null;
    created_at: string;
    acknowledged_at: string;
    completed_at: string;
    updated_at: string;
}

function normalizeMessage(raw: any): ChatMessage {
    const id = String(raw?.id || raw?.message_id || "");
    const ts = String(raw?.created_at || raw?.timestamp || new Date().toISOString());
    return {
        id,
        message_id: id,
        created_at: ts,
        timestamp: ts,
        role: raw?.role === 'user' ? 'user' : 'sophia',
        content: String(raw?.content || ''),
        context_tag: String(raw?.context_tag || 'general'),
        importance: Number(raw?.importance ?? 0.5),
        emotion_signal: raw?.emotion_signal ?? null,
        linked_cluster: raw?.linked_cluster ?? null,
        linked_node: raw?.linked_node ?? null,
        status: (
            raw?.status === 'pending' ||
            raw?.status === 'escalated' ||
            raw?.status === 'acknowledged' ||
            raw?.status === 'resolved' ||
            raw?.status === 'read'
        ) ? raw.status : 'normal',
        intent: raw?.intent,
        context: raw?.context,
        priority: raw?.priority,
        message_type: raw?.message_type,
    };
}

export const chatService = {
    async sendMessage(text: string, contextTag: string = 'system', linkedNode: string | null = null): Promise<SendMessageResponse> {
        console.log(`Sending message via API: ${text}`);
        try {
            const response = await fetch(`${API_BASE}/chat/message`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    content: text,
                    channel: 'General',
                    context_tag: contextTag,
                    linked_node: linkedNode,
                })
            });
            
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(errText);
            }
            
            const raw = await response.json();
            return {
                status: String(raw?.status || 'ok'),
                reply: raw?.reply ? String(raw.reply) : undefined,
                context_tag: String(raw?.context_tag || contextTag),
                messages: Array.isArray(raw?.messages) ? raw.messages.map(normalizeMessage) : [],
                pending_inserted: Array.isArray(raw?.pending_inserted) ? raw.pending_inserted.map(normalizeMessage) : [],
            };
        } catch (error) {
            console.error('Failed to send message:', error);
            throw error;
        }
    },

    async appendUserMessageToMemory(text: string, channel: string = "General"): Promise<any> {
        void text;
        void channel;
        return { status: 'handled_by_api' };
    },

    async addMessage(payload: {
        role: 'user' | 'sophia';
        content: string;
        context_tag: string;
        importance?: number;
        emotion_signal?: string | null;
        linked_node?: string | null;
        linked_cluster?: string | null;
        status?: 'normal' | 'pending' | 'escalated' | 'acknowledged' | 'resolved' | 'read';
    }): Promise<ChatMessage> {
        try {
            const response = await fetch(`${API_BASE}/chat/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                const errText = await response.text();
                throw new Error(errText);
            }
            const raw = await response.json();
            return normalizeMessage(raw?.message || {});
        } catch (error) {
            console.error('Failed to add chat message:', error);
            throw error;
        }
    },

    async getDailyLogs(contextTag?: string, limit: number = 300): Promise<ChatMessage[]> {
        try {
            const query = new URLSearchParams();
            query.set('limit', String(limit));
            if (contextTag && contextTag !== 'all') {
                query.set('context_tag', contextTag);
            }
            const response = await fetch(`${API_BASE}/chat/history?${query.toString()}`);
            if (!response.ok) return [];
            const raw = await response.json();
            if (!Array.isArray(raw)) return [];
            return raw.map(normalizeMessage);
        } catch (error) {
            console.error('Failed to fetch chat logs:', error);
            return [];
        }
    },

    async getContexts(): Promise<Array<{ context_tag: string; count: number }>> {
        try {
            const response = await fetch(`${API_BASE}/chat/contexts`);
            if (!response.ok) return [];
            const raw = await response.json();
            if (!Array.isArray(raw)) return [];
            return raw.map((item) => ({
                context_tag: String(item?.context_tag || 'general'),
                count: Number(item?.count || 0),
            }));
        } catch (error) {
            console.error('Failed to fetch contexts:', error);
            return [];
        }
    },

    async getPending(limit: number = 50): Promise<ChatMessage[]> {
        try {
            const response = await fetch(`${API_BASE}/chat/pending?limit=${encodeURIComponent(String(limit))}`);
            if (!response.ok) return [];
            const raw = await response.json();
            if (!Array.isArray(raw)) return [];
            return raw.map(normalizeMessage);
        } catch (error) {
            console.error('Failed to fetch pending chat messages:', error);
            return [];
        }
    },

    async markMessageRead(messageId: string): Promise<ChatMessage | null> {
        try {
            const response = await fetch(`${API_BASE}/chat/messages/${encodeURIComponent(messageId)}/read`, {
                method: 'POST',
            });
            if (!response.ok) return null;
            const raw = await response.json();
            return normalizeMessage(raw?.message || {});
        } catch (error) {
            console.error('Failed to mark message as read:', error);
            return null;
        }
    },

    async getQuestionPool(): Promise<QuestionPoolItem[]> {
        try {
            const response = await fetch(`${API_BASE}/chat/questions/pool`);
            if (!response.ok) return [];
            const raw = await response.json();
            if (!Array.isArray(raw)) return [];
            return raw.map((item) => ({
                cluster_id: String(item?.cluster_id || ''),
                description: String(item?.description || ''),
                hit_count: Number(item?.hit_count || 0),
                risk_score: Number(item?.risk_score || 0),
                evidence: Array.isArray(item?.evidence) ? item.evidence : [],
                linked_nodes: Array.isArray(item?.linked_nodes) ? item.linked_nodes : [],
                status: String(item?.status || ''),
                last_triggered_at: String(item?.last_triggered_at || ''),
                last_asked_at: String(item?.last_asked_at || ''),
                asked_count: Number(item?.asked_count || 0),
            }));
        } catch (error) {
            console.error('Failed to fetch question pool:', error);
            return [];
        }
    },

    async ackQuestion(clusterId: string): Promise<boolean> {
        try {
            const response = await fetch(`${API_BASE}/chat/questions/${encodeURIComponent(clusterId)}/ack`, {
                method: 'POST',
            });
            return response.ok;
        } catch (error) {
            console.error('Failed to ack question:', error);
            return false;
        }
    },

    async resolveQuestion(clusterId: string): Promise<boolean> {
        try {
            const response = await fetch(`${API_BASE}/chat/questions/${encodeURIComponent(clusterId)}/resolve`, {
                method: 'POST',
            });
            return response.ok;
        } catch (error) {
            console.error('Failed to resolve question:', error);
            return false;
        }
    },

    async createWorkPackage(payload: {
        kind: 'ANALYZE' | 'IMPLEMENT' | 'REVIEW' | 'MIGRATE';
        title?: string;
        description?: string;
        acceptance_criteria: string[];
        deliverables: string[];
        return_payload_spec: Record<string, unknown>;
        payload?: Record<string, unknown>;
        context_tag?: string;
        linked_node?: string | null;
    }): Promise<WorkPackageItem | null> {
        try {
            const response = await fetch(`${API_BASE}/work/packages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!response.ok) return null;
            const raw = await response.json();
            return raw?.package || null;
        } catch (error) {
            console.error('Failed to create work package:', error);
            return null;
        }
    },

    async getWorkPackages(status: 'READY' | 'IN_PROGRESS' | 'DONE' | 'BLOCKED' | 'FAILED' | 'ALL' = 'READY'): Promise<WorkPackageItem[]> {
        try {
            const response = await fetch(`${API_BASE}/work/packages?status=${encodeURIComponent(status)}`);
            if (!response.ok) return [];
            const raw = await response.json();
            if (!Array.isArray(raw?.items)) return [];
            return raw.items;
        } catch (error) {
            console.error('Failed to fetch work packages:', error);
            return [];
        }
    },

    async ackWorkPackage(id: string): Promise<boolean> {
        try {
            const response = await fetch(`${API_BASE}/work/packages/${encodeURIComponent(id)}/ack`, {
                method: 'POST',
            });
            return response.ok;
        } catch (error) {
            console.error('Failed to ack work package:', error);
            return false;
        }
    },

    async completeWorkPackage(id: string): Promise<boolean> {
        try {
            const response = await fetch(`${API_BASE}/work/packages/${encodeURIComponent(id)}/complete`, {
                method: 'POST',
            });
            return response.ok;
        } catch (error) {
            console.error('Failed to complete work package:', error);
            return false;
        }
    },

    async getWorkPacket(id: string): Promise<{ work_package_id: string; packet: Record<string, unknown>; packet_text: string } | null> {
        try {
            const response = await fetch(`${API_BASE}/work/packages/${encodeURIComponent(id)}/packet`);
            if (!response.ok) return null;
            const raw = await response.json();
            return {
                work_package_id: String(raw?.work_package_id || id),
                packet: (raw?.packet || {}) as Record<string, unknown>,
                packet_text: String(raw?.packet_text || ''),
            };
        } catch (error) {
            console.error('Failed to fetch work packet:', error);
            return null;
        }
    },

    async submitWorkReport(
        id: string,
        report: {
            work_package_id?: string;
            status: 'DONE' | 'BLOCKED' | 'FAILED';
            signals: Array<{ cluster_id: string; risk_score: number; evidence: string; linked_node?: string | null }>;
            artifacts: string[];
            notes: string;
        },
    ): Promise<boolean> {
        try {
            const response = await fetch(`${API_BASE}/work/packages/${encodeURIComponent(id)}/report`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(report),
            });
            return response.ok;
        } catch (error) {
            console.error('Failed to submit work report:', error);
            return false;
        }
    },

    watchLogs(callback: (messages: ChatMessage[]) => void, intervalMs = 2000, contextTag?: string): () => void {
        let isWatching = true;
        let lastLastId = '';
        let initialized = false;

        const poll = async () => {
            if (!isWatching) return;
            
            const logs = await this.getDailyLogs(contextTag);
            const currentLastId = logs.length > 0 ? logs[logs.length - 1].id : '';
            if (!initialized || currentLastId !== lastLastId) {
                initialized = true;
                lastLastId = currentLastId;
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
