import { readTextFile, exists } from '@tauri-apps/plugin-fs';

const AUDIT_PATH = '/Users/dragonpd/Sophia/.sophia/audit/ledger.jsonl';

export interface AuditItem {
    run_id: string;
    skill_id: string;
    status: string;
    inputs_hash?: string;
    outputs_hash?: string;
    diff_refs?: string[];
    timestamps?: {
        queued_at?: string;
        started_at?: string;
        finished_at?: string;
    };
    raw: string;
}

export const auditService = {
    async listAuditLog(limit: number = 50, filterStatus?: string): Promise<AuditItem[]> {
        try {
            if (!(await exists(AUDIT_PATH))) {
                return [];
            }

            const content = await readTextFile(AUDIT_PATH);
            const lines = content.split('\n').filter(line => line.trim() !== '');

            // Process reverse for newest first
            let items: AuditItem[] = lines.reverse().map(line => {
                try {
                    const parsed = JSON.parse(line);
                    return {
                        ...parsed,
                        raw: line
                    };
                } catch (e) {
                    return {
                        run_id: 'parse_error',
                        skill_id: 'unknown',
                        status: 'error',
                        raw: line
                    };
                }
            });

            if (filterStatus && filterStatus !== 'all') {
                items = items.filter(item => item.status === filterStatus);
            }

            return items.slice(0, limit);

        } catch (e) {
            console.error("Failed to list audit log:", e);
            return [];
        }
    }
};
