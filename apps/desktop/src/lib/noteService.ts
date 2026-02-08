import { writeTextFile, readTextFile, exists, mkdir, readDir, remove, rename } from '@tauri-apps/plugin-fs';

// Workspace Root: /Users/dragonpd/Sophia/workspace
const WORKSPACE_ROOT = '/Users/dragonpd/Sophia/workspace';
const NOTES_PATH = `${WORKSPACE_ROOT}/notes`;

export interface FileNode {
    name: string;
    path: string;
    isDirectory: boolean;
    children?: FileNode[];
}

export const noteService = {
    async ensureNotesDir() {
        try {
            // Check if directory exists by trying to read it
            // If error, create it
            // Since we use absolute paths, we can't use BaseDirectory.AppLocalData easily without configuring scope.
            // Assuming scope is open for WORKSPACE_ROOT.
            try {
                await readDir(NOTES_PATH);
            } catch {
                await mkdir(NOTES_PATH, { recursive: true });
            }
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
            if (await exists(path)) {
                return await readTextFile(path);
            }
            return ""; 
        } catch (e) {
            console.error("Failed to load note:", e);
            return ""; 
        }
    },

    async saveTodayNote(content: string): Promise<void> {
        const path = this.getTodayFileName();
        try {
            await this.ensureNotesDir();
            await writeTextFile(path, content);
        } catch (e) {
            console.error("Failed to save note:", e);
        }
    },

    // --- File System Operations for Sidebar ---

    async listNotes(dirPath: string = NOTES_PATH): Promise<FileNode[]> {
        try {
            await this.ensureNotesDir();
            const entries = await readDir(dirPath);
            const nodes: FileNode[] = [];

            for (const entry of entries) {
                // Skip hidden files
                if (entry.name.startsWith('.')) continue;

                const fullPath = `${dirPath}/${entry.name}`;
                const node: FileNode = {
                    name: entry.name,
                    path: fullPath,
                    isDirectory: !!entry.isDirectory,
                };

                if (entry.isDirectory) {
                    node.children = await this.listNotes(fullPath); 
                    // Use recursive for now, or load on demand?
                    // Recursive is easier for small counts. 
                    // But if deep, might be slow.
                    // Let's do recursive for now as notes unlikely to be huge.
                }
                nodes.push(node);
            }

            // Sort: Folders first, then files. Alphabetical.
            return nodes.sort((a, b) => {
                if (a.isDirectory === b.isDirectory) return a.name.localeCompare(b.name);
                return a.isDirectory ? -1 : 1;
            });
        } catch (e) {
            console.error("Failed to list notes:", e);
            return [];
        }
    },

    async createFolder(parentPath: string = NOTES_PATH, name: string): Promise<string | null> {
        const newPath = `${parentPath}/${name}`;
        try {
            await mkdir(newPath, { recursive: true });
            return newPath;
        } catch (e) {
            console.error("Failed to create folder:", e);
            return null;
        }
    },

    async createNote(parentPath: string = NOTES_PATH, name: string, content: string = ""): Promise<string | null> {
        // Ensure extension
        if (!name.endsWith('.md')) name += '.md';
        const newPath = `${parentPath}/${name}`;
        try {
            await writeTextFile(newPath, content);
            return newPath;
        } catch (e) {
            console.error("Failed to create note:", e);
            return null;
        }
    },

    async renameItem(oldPath: string, newName: string): Promise<boolean> {
        const parent = oldPath.substring(0, oldPath.lastIndexOf('/'));
        const newPath = `${parent}/${newName}`;
        try {
            await rename(oldPath, newPath);
            return true;
        } catch (e) {
           console.error("Failed to rename:", e);
           return false;
        }
    },

    async deleteItem(path: string): Promise<boolean> {
        try {
            // await remove(path, { recursive: true }); // 'recursive' for folders
            // remove signature in v2 might differ?
            // Usually remove(path, options).
            // Let's assume it handles files too.
             await remove(path, { recursive: true });
            return true;
        } catch (e) {
            console.error("Failed to delete:", e);
            return false;
        }
    },
    
    async readFile(path: string): Promise<string> {
        try {
            return await readTextFile(path);
        } catch(e) {
            console.error("Failed to read file", e);
            throw e;
        }
    },

    async saveFile(path: string, content: string): Promise<void> {
        try {
            await writeTextFile(path, content);
        } catch(e) {
             console.error("Failed to save file", e);
             throw e;
        }
    },

    async exists(path: string): Promise<boolean> {
        return await exists(path);
    },

    getNotesPath(): string {
        return NOTES_PATH;
    }
};
