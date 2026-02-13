import { writeTextFile, readDir, mkdir } from '@tauri-apps/plugin-fs';
import { Command } from '@tauri-apps/plugin-shell';

const LOG_DROP_DIR = '/Users/dragonpd/Sophia/sophia_workspace/ingest_drop/ide_logs';

export interface LogDropEntry {
    title: string;
    body: string;
    tags: string[];
}

export const logDropService = {
    async ensureDropDir() {
        try {
            await readDir(LOG_DROP_DIR);
        } catch {
            await mkdir(LOG_DROP_DIR, { recursive: true });
        }
    },

    async saveLog(entry: LogDropEntry): Promise<string | null> {
        try {
            await this.ensureDropDir();

            const date = new Date();
            const yyyy = date.getFullYear();
            const mm = String(date.getMonth() + 1).padStart(2, '0');
            const dd = String(date.getDate()).padStart(2, '0');
            const hh = String(date.getHours()).padStart(2, '0');
            const min = String(date.getMinutes()).padStart(2, '0');

            // Slugify title
            let slug = entry.title
                .toLowerCase()
                .replace(/[^a-z0-9]+/g, '_')
                .replace(/^_+|_+$/g, '');
            if (!slug) slug = "untitled";

            const filename = `${yyyy}${mm}${dd}_${hh}${min}_ide_${slug}.md`;
            const filePath = `${LOG_DROP_DIR}/${filename}`;

            const content = `# ${entry.title}

tags: [${entry.tags.map(t => `"${t}"`).join(', ')}]

---

${entry.body}
`;

            await writeTextFile(filePath, content);
            return filename;
        } catch (e) {
            console.error("Failed to save log drop:", e);
            throw e;
        }
    },

    async ingestLogs(): Promise<{ scanned: number, ingested: number, skipped: number }> {
        try {
            // "run-ingest-logs" matches the capability name in default.json
            // We configured it to run: .venv/bin/python scripts/ingest_ide_logs.py
            // Note: CWD for the command might depend on tauri context. 
            // Usually tauri shell command executes from the app bundle or needs absolute paths.
            // But we defined the cmd and args in capabilities.
            // Let's assume the capability definition handles the executable path.
            // However, the script path "scripts/ingest_ide_logs.py" is relative. 
            // Provide absolute path in capabilities would be safer, but let's try invoking the named command.
            
            const command = Command.create('run-ingest-logs');
            const output = await command.execute();
            
            if (output.code !== 0) {
                console.error("Ingest stderr:", output.stderr);
                throw new Error(`Ingest failed with code ${output.code}: ${output.stderr}`);
            }

            console.log("Ingest stdout:", output.stdout);
            
            try {
                // Parse last line of stdout which should be the JSON result
                // The script outputs debug lines then the JSON result.
                const lines = output.stdout.trim().split('\n');
                const lastLine = lines[lines.length - 1];
                const result = JSON.parse(lastLine);
                return {
                    scanned: result.scanned_files || 0,
                    ingested: result.ingested || 0,
                    skipped: result.skipped || 0
                };
            } catch (parseError) {
                console.warn("Could not parse ingest output JSON, returning raw success");
                return { scanned: -1, ingested: -1, skipped: -1 };
            }

        } catch (e) {
            console.error("Failed to ingest logs:", e);
            throw e;
        }
    }
};
