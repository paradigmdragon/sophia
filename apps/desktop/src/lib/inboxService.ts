import { readTextFile, writeTextFile, exists } from '@tauri-apps/plugin-fs';

const MANIFEST_PATH = "/Users/dragonpd/Sophia/memory/memory_manifest.json";

export interface InboxItem {
    id: string; // patch_id
    message: string; // thin_summary (The Question)
    context: string; // snippet or issue_code (hidden but useful for debug)
    status: 'pending' | 'adopted' | 'deferred' | 'rejected';
    timestamp: string;
}

export const inboxService = {
    async getPendingItems(): Promise<InboxItem[]> {
        try {
            if (!(await exists(MANIFEST_PATH))) return [];
            
            const content = await readTextFile(MANIFEST_PATH);
            const manifest = JSON.parse(content);
            const patches = manifest.patches || {};
            
            const items: InboxItem[] = (Object.values(patches) as any[])
                .filter((p: any) => p.status === 'pending')
                .map((p: any) => ({
                    id: p.patch_id,
                    message: p.thin_summary,
                    context: p.issue_code,
                    status: 'pending',
                    timestamp: p.created_at
                })) as InboxItem[];
                
            return items.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
        } catch (e) {
            console.error("Failed to load inbox:", e);
            return [];
        }
    },

    async updateItemStatus(itemId: string, status: 'adopted' | 'deferred' | 'rejected'): Promise<boolean> {
        try {
            if (!(await exists(MANIFEST_PATH))) return false;
            
            const content = await readTextFile(MANIFEST_PATH);
            const manifest = JSON.parse(content);
            
            if (manifest.patches && manifest.patches[itemId]) {
                manifest.patches[itemId].status = status;
                manifest.patches[itemId].updated_at = new Date().toISOString();
                
                await writeTextFile(MANIFEST_PATH, JSON.stringify(manifest, null, 2));
                return true;
            }
            return false;
        } catch (e) {
            console.error("Failed to update item:", e);
            return false;
        }
    }
};
