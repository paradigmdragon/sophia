import { writeTextFile, readTextFile, exists } from '@tauri-apps/plugin-fs';
import { Task, AppEvent, TaskStatus } from '../types';

// Constants
const WORKSPACE_ROOT = '/Users/dragonpd/Sophia/workspace'; // Absolute path for now as per user instruction to fix scope later or use env
const TASKS_DIR = `${WORKSPACE_ROOT}/tasks`;
const EVENTS_DIR = `${WORKSPACE_ROOT}/events`;

export const taskManager = {
    /**
     * Creates a new task file in workspace/tasks
     */
    async submitTask(files: string[], configSnapshot: any): Promise<string> {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const taskId = `task_${timestamp}`;
        const fileName = `${taskId}.task.json`;
        const filePath = `${TASKS_DIR}/${fileName}`;

        const task: Task = {
            task_id: taskId,
            run_id: `run_${Date.now()}`, // Initial run_id, might be updated by runner but okay for creation
            created_at: new Date().toISOString(),
            status: 'queued',
            type: 'transcription',
            requested_by: 'desktop-user',
            tool: 'sophia-desktop',
            config_snapshot: configSnapshot,
            input: {
                media: files[0], // Handle single file for v0.1
            },
            pipeline: ['asr', 'refine'],
            output: {}, // Empty initially
        };

        try {
            // Ensure directory exists - fs plugin might fail if dir doesn't exist, 
            // but Core setup ensured it. We assume it exists.
            await writeTextFile(filePath, JSON.stringify(task, null, 2));
            console.log(`Task submitted: ${filePath}`);
            return taskId;
        } catch (error) {
            console.error('Failed to submit task:', error);
            throw error;
        }
    },

    /**
     * Polls events directory for updates.
     * Returns a cleanup function to stop polling.
     */
    watchEvents(onEvent: (event: AppEvent) => void): () => void {
        let isWatching = true;
        const processedEvents = new Set<string>(); // Keep track of processed events to avoid duplicates
        // Ideally we track by file offset, but for v0.1 simple polling is enough.
        // Or tracking run_id/task_id + ts.

        const poll = async () => {
            if (!isWatching) return;

            try {
                // Get today's event file
                const dateStr = new Date().toISOString().split('T')[0];
                const eventFile = `${EVENTS_DIR}/${dateStr}_events.jsonl`;

                if (await exists(eventFile)) {
                    const content = await readTextFile(eventFile);
                    const lines = content.split('\n').filter(line => line.trim());
                    
                    for (const line of lines) {
                        try {
                            const event: AppEvent = JSON.parse(line);
                            // Simple dedupe key
                            const key = `${event.ts}_${event.task_id}_${event.type}`;
                            
                            if (!processedEvents.has(key)) {
                                processedEvents.add(key);
                                onEvent(event);
                            }
                        } catch (e) {
                            // Ignore parse errors (partial lines)
                        }
                    }
                }
            } catch (error) {
                console.warn('Event polling error:', error);
            }

            if (isWatching) {
                setTimeout(poll, 1000); // Poll every second
            }
        };

        poll();

        return () => {
            isWatching = false;
        };
    },

    async getTaskStatus(_taskId: string): Promise<TaskStatus | null> {
        // Find file
        // Pattern: *_{taskId}.task.json
        // Listing dir is expensive if many files. 
        // For v0.1 rely on events. 
        // Providing dummy impl.
        return null;
    }
};
