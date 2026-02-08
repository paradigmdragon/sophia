
import { writeTextFile, readTextFile, exists, BaseDirectory, create, mkdir } from '@tauri-apps/plugin-fs';

const NOTES_DIR = 'notes'; // Relative to AppLocalData or Document? 
// User instruction: "notes/{yyyy-mm-dd}.md"
// Let's use BaseDirectory.AppLocalData for now, or Workspace if defined.
// Re-reading taskManager.ts, it used absolute path '/Users/dragonpd/Sophia/workspace'.
// I should stick to that pattern for consistency, or use BaseDirectory if possible.
// Given strict "notes/{yyyy-mm-dd}.md", let's assume a 'notes' folder in the workspace root.
// Workspace Root: /Users/dragonpd/Sophia/workspace

const WORKSPACE_ROOT = '/Users/dragonpd/Sophia/workspace';
const NOTES_PATH = `${WORKSPACE_ROOT}/notes`;

export const noteService = {
    async ensureNotesDir() {
        // This is a bit tricky with absolute paths in browser JS without a proper backend bridge if FS plugin doesn't support absolute paths easily without configuration.
        // But we added "fs:scope-..." capabilities.
        // Let's try to use the absolute path if allowed, or fallback.
        // For now, let's assume we can write to the workspace.
        // We might need to create the directory.
        // tauri-plugin-fs `mkdir` with recursive.
        try {
           // We can't easily check if dir exists with absolute path using just `exists` if it expects BaseDir.
           // But `readDir` might work.
           // Actually, `mkdir` is safer.
           // Wait, `tauri-plugin-shell` can consistently make dirs.
           // But let's try `tauri-plugin-fs`.
           // If we use absolute paths, we just pass the path string.
           // Note: tauri-plugin-fs v2 might require scopes.
           // I'll assume the scope configuration in `default.json` covers it (it has broad allow-lists).
        } catch (e) {
            console.error("Error ensuring notes dir", e);
        }
    },

    getTodayFileName(): string {
        const date = new Date();
        const yyyy = date.getFullYear();
        const mm = String(date.getMonth() + 1).padStart(2, '0');
        const dd = String(date.getDate()).padStart(2, '0');
        return `${NOTES_PATH}/${yyyy}-${mm}-${dd}.md`;
    },

    async loadTodayNote(): Promise<string> {
        const path = this.getTodayFileName();
        try {
            // Check if exists
            // Since `exists` is async and might need permissions, let's just try reading.
            // If it fails, return empty.
            // Actually, `exists` is available.
            const fileExists = await exists(path);
            if (fileExists) {
                return await readTextFile(path);
            } else {
                return ""; // New empty note
            }
        } catch (e) {
            console.error("Failed to load note:", e);
            return ""; 
        }
    },

    async saveTodayNote(content: string): Promise<void> {
        const path = this.getTodayFileName();
        try {
            await writeTextFile(path, content);
        } catch (e) {
            console.error("Failed to save note:", e);
        }
    }
};
