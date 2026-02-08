import { useState, useEffect } from "react";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import { open as openDialog } from '@tauri-apps/plugin-dialog';
import { invoke } from "@tauri-apps/api/core";

import { taskManager } from "../lib/taskManager";
import { AppEvent } from "../types";

import { FileQueue, FileItem } from "./FileQueue";
import { StatusPanel } from "./StatusPanel";
import { LogFooter } from "./LogFooter";

interface LogEntry {
  timestamp: string;
  message: string;
  type: "info" | "error" | "event";
}

export function HearingTab() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [showLogs, setShowLogs] = useState(false);

  // --- Log Management ---
  const addLog = (message: string, type: "info" | "error" | "event" = "info") => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev, { timestamp, message, type }]);
  };

  const lastLog = logs.length > 0 ? logs[logs.length - 1] : undefined;

  // --- Event Listeners (File System Watcher) ---
  useEffect(() => {
    const stopWatching = taskManager.watchEvents((event: AppEvent) => {
        handleAppEvent(event);
    });
    return () => stopWatching();
  }, []);

  const handleAppEvent = (event: AppEvent) => {
      switch (event.type) {
          case 'task.started':
               setIsProcessing(true);
               addLog(`Task Started: ${event.task_id}`, "event");
               break;
          case 'stage.progress':
              if (event.payload.msg) addLog(event.payload.msg, "info");
              break;
          case 'task.completed':
              setIsProcessing(false);
              addLog(`Task Completed. Duration: ${event.payload.duration_sec}s`, "event");
              setFiles(prev => prev.map(f => ({ ...f, status: 'done' })));
              break;
          case 'task.failed':
              setIsProcessing(false);
              addLog(`Task Failed: ${event.payload.error}`, "error");
              setFiles(prev => prev.map(f => ({ ...f, status: 'error', error: event.payload.error })));
              break;
          case 'log':
              addLog(event.payload.message, "info");
              break;
          case 'file_start':
              addLog(`Processing file: ${event.payload.file}`, "info");
              break;
          case 'refine_completed':
              addLog(`Refinement complete: ${event.payload.file}`, "info");
              if (event.payload.outputs && event.payload.outputs.txt) {
                 setFiles(prev => prev.map(f => {
                     return f.name === event.payload.file ? { ...f, refinedPath: event.payload.outputs.txt } : f;
                 }));
              }
              break;
          case 'file_done':
              if (event.payload.status === 'success') {
                  addLog(`Finished file: ${event.payload.file}`, "info");
                   setFiles(prev => prev.map(f => {
                     return f.name === event.payload.file ? { ...f, status: 'done', outputPath: event.payload.output } : f;
                 }));
              } else {
                  addLog(`Error processing file: ${event.payload.file} - ${event.payload.error}`, "error");
                  setFiles(prev => prev.map(f => {
                     return f.name === event.payload.file ? { ...f, status: 'error', error: event.payload.error } : f;
                  }));
              }
              break;
      }
  };

  // --- Drag & Drop ---
  useEffect(() => {
    const unlistenPromise = getCurrentWebview().onDragDropEvent((event) => {
        if (event.payload.type === 'drop') {
             const paths = event.payload.paths;
             handleFilesAdded(paths);
        }
    });
    return () => {
        unlistenPromise.then(unlisten => unlisten());
    };
  }, []);

  // --- File Actions ---
  const openFileDialog = async () => {
    try {
        const selected = await openDialog({
            multiple: true,
            filters: [{
                name: 'Audio/Video',
                extensions: ['mp3', 'wav', 'm4a', 'mp4', 'mov', 'mkv', 'flac', 'aac']
            }]
        });

        if (Array.isArray(selected)) {
            handleFilesAdded(selected);
        }
    } catch (err) {
        addLog(`Failed to open file dialog: ${err}`, "error");
    }
  };

  const handleFilesAdded = (paths: string[]) => {
    const newFiles = paths
      .filter(path => {
        const ext = path.split('.').pop()?.toLowerCase();
        return ["mp3", "wav", "m4a", "mp4", "mov", "mkv"].includes(ext || "");
      })
      .map(path => ({
        path,
        name: path.split(/[/\\]/).pop() || path,
        status: "idle" as const
      }))
      .filter(newItem => !files.some(f => f.path === newItem.path)); 

    if (newFiles.length > 0) {
      setFiles(prev => {
          const updated = [...prev, ...newFiles];
          if (!selectedFileId && updated.length > 0) {
              setSelectedFileId(updated[0].path); 
          }
          return updated;
      });
      addLog(`Added ${newFiles.length} files to queue.`);
    }
  };

  const removeFile = (path: string) => {
    setFiles(prev => {
        const next = prev.filter(f => f.path !== path);
        if (selectedFileId === path) {
            setSelectedFileId(next.length > 0 ? next[0].path : null);
        }
        return next;
    });
  };

  const startTranscription = async () => {
    if (files.length === 0) {
        addLog("No files selected.", "error");
        return;
    }
    
    setIsProcessing(true);
    setFiles(prev => prev.map(f => ({ ...f, status: "idle", error: undefined }))); 
    addLog("Submitting tasks...", "info");

    try {
      const config = {
          engine: { type: "faster_whisper", model_size: "medium", device: "auto", compute_type: "float16" },
          refine: { enabled: true } 
      };
      
      for (const file of files) {
          const taskId = await taskManager.submitTask([file.path], config);
          addLog(`Task submitted: ${taskId}`, "event");
          setFiles(prev => prev.map(f => f.path === file.path ? { ...f, status: 'processing' } : f));
      }
      addLog("All tasks submitted. Waiting for Core...", "info");
      
    } catch (e) {
      console.error("Task submission failed:", e);
      setIsProcessing(false);
      addLog(`Failed to submit task: ${e}`, "error");
    }
  };

  const openPath = async (path: string) => {
    try {
        await invoke("open_in_finder", { path });
    } catch {
       addLog(`Could not open path: ${path}`, "error");
    }
  };

  const selectedFile = files.find(f => f.path === selectedFileId);

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 flex overflow-hidden">
        <FileQueue 
          files={files} 
          selectedFileId={selectedFileId}
          onSelect={setSelectedFileId}
          onRemove={removeFile}
          onAddFiles={openFileDialog}
        />
        <StatusPanel 
          selectedFile={selectedFile}
          isProcessing={isProcessing}
          onStart={startTranscription}
          onCancel={() => { setIsProcessing(false); addLog("Cancelled", "error"); }}
          onOpenPath={openPath}
        />
      </div>
      <LogFooter 
        lastLog={lastLog} 
        onExpand={() => setShowLogs(!showLogs)} 
        isProcessing={isProcessing}
        onCancel={() => setIsProcessing(false)}
      />
      {showLogs && (
        <div className="h-48 bg-black text-xs font-mono p-2 overflow-y-auto border-t border-white/10">
            {logs.map((log, i) => (
                <div key={i} className={log.type === 'error' ? 'text-red-400' : log.type === 'event' ? 'text-blue-400' : 'text-gray-400'}>
                    [{log.timestamp}] {log.message}
                </div>
            ))}
        </div>
      )}
    </div>
  );
}
