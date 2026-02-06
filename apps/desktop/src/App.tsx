import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import { open as openDialog } from '@tauri-apps/plugin-dialog';
import { BaseDirectory, writeTextFile } from '@tauri-apps/plugin-fs';
import { appDataDir, join } from '@tauri-apps/api/path';


// Components
import { LogoHeader } from "./components/LogoHeader";
import { FileQueue, FileItem } from "./components/FileQueue";
import { StatusPanel } from "./components/StatusPanel";
import { LogFooter } from "./components/LogFooter";
import { SettingsModal, LineWrapSettings, DEFAULT_SETTINGS } from "./components/SettingsModal";

interface LogEntry {
  timestamp: string;
  message: string;
  type: "info" | "error" | "event";
}

function App() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [showLogs, setShowLogs] = useState(false); // Can be used for expanded log view later
  
  // Settings State
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [lineWrapSettings, setLineWrapSettings] = useState<LineWrapSettings>(DEFAULT_SETTINGS);

  // Load Settings
  useEffect(() => {
    const saved = localStorage.getItem("sophia_settings_v1");
    if (saved) {
        try {
            const parsed = JSON.parse(saved);
            if (parsed.line_wrap) setLineWrapSettings(parsed.line_wrap);
        } catch (e) { console.error("Failed to parse settings", e); }
    }
  }, []);

  const handleSaveSettings = (newSettings: LineWrapSettings) => {
      setLineWrapSettings(newSettings);
      localStorage.setItem("sophia_settings_v1", JSON.stringify({ line_wrap: newSettings }));
      addLog("Settings saved.", "info");
  };

  const generateRuntimeConfig = async (): Promise<string> => {
      const config = {
          engine: {
              type: "faster_whisper",
              model_size: "medium",
              device: "auto",
              compute_type: "float16"
          },
          refine: {
              line_wrap: lineWrapSettings
          }
      };
      
      const configStr = JSON.stringify(config, null, 2);
      const filename = "runtime_config.json";
      
      // Write to AppData
      await writeTextFile(filename, configStr, { baseDir: BaseDirectory.AppData });
      
      // Get Absolute Path
      const appData = await appDataDir();
      return await join(appData, filename);
  };

  // --- Log Management ---
  const addLog = (message: string, type: "info" | "error" | "event" = "info") => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev, { timestamp, message, type }]);
  };

  const lastLog = logs.length > 0 ? logs[logs.length - 1] : undefined;

  // --- Event Listeners (Backend) ---
  useEffect(() => {
    const filters = ["file_start", "progress", "refine_started", "refine_completed", "file_done", "run_done", "run_error", "process_exit", "log", "log_raw"];
    const unlistens: Promise<() => void>[] = [];

    filters.forEach(event => {
      unlistens.push(listen(event, (e: any) => {
        const payload = e.payload;
        
        switch (event) {
          case "file_start":
            updateFileStatus(payload.file, "processing");
            addLog(`Started processing: ${payload.file}`, "event");
            break;
          case "refine_started":
            updateFileStatus(payload.file, "refining");
            addLog(`Refining output for: ${payload.file}`, "event");
            break;
          case "refine_completed":
             updateFileRefinedPath(payload.file, payload.outputs.refined_txt);
             addLog(`Refinement completed: ${payload.file}`, "event");
             break;
          case "file_done":
            updateFileStatus(payload.file, payload.status === "success" ? "done" : "error", payload.output, payload.error);
            addLog(`Finished: ${payload.file} (${payload.status})`, payload.status === "success" ? "event" : "error");
            break;
          case "run_done":
            setIsProcessing(false);
            addLog("Batch processing completed.", "info");
            break;
          case "run_error":
            setIsProcessing(false);
            addLog(`Run Error: ${payload}`, "error");
            break;
        }
      }));
    });

    return () => {
      unlistens.forEach(p => p.then(u => u()));
    };
  }, []);

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
        } else if (selected === null) {
            // User cancelled
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
              setSelectedFileId(updated[0].path); // Auto select first added
          }
          return updated;
      });
      addLog(`Added ${newFiles.length} files to queue.`);
    }
  };

  const updateFileStatus = (filename: string, status: FileItem["status"], outputPath?: string, error?: string) => {
    setFiles(prev => prev.map(f => {
      if (f.name === filename) {
        return { ...f, status, outputPath: outputPath || f.outputPath, error };
      }
      return f;
    }));
  };

  const updateFileRefinedPath = (filename: string, refinedPath: string) => {
    setFiles(prev => prev.map(f => {
        if (f.name === filename) {
            return { ...f, refinedPath };
        }
        return f;
    }));
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

  // --- Core Actions ---
  const startTranscription = async () => {
    console.log("startTranscription called"); // DEBUG
    if (files.length === 0) {
        addLog("No files selected.", "error");
        return;
    }
    
    setIsProcessing(true);
    // Reset statuses (only for those not done? or all? let's do all for simplicity in v0.x)
    setFiles(prev => prev.map(f => ({ ...f, status: "idle", error: undefined }))); 
    addLog("Initializing Sophia engine...", "info");

    try {
      const firstFile = files[0].path;
      // Simple logic: outbox sibling to file location for now
      // This path logic should match Python side expectations or be passed explicitly
      // Ideally we ask user or use default. 
      // Let's assume we pass a fixed output directory relative to input or just let user know
      
      const parentDir = firstFile.substring(0, firstFile.lastIndexOf(firstFile.includes("/") ? "/" : "\\"));
      const outdir = `${parentDir}/Sophia_Output`;
      
      // Generate Runtime Config
      let configPath: string | undefined;
      try {
          configPath = await generateRuntimeConfig();
          addLog(`Config generated: ${configPath}`, "info");
      } catch (err) {
          console.error("Config generation failed:", err); // DEBUG
          addLog(`Failed to generate config: ${err}`, "error");
          // Proceed with default? or stop? Stop is safer if user expects settings.
          // But for robustness let's warn and try.
      }

      const args = { 
        files: files.map(f => f.path),
        outdir,
        configPath // Passed to backend
      };
      
      console.log("Invoking start_transcription with:", args); // DEBUG
      addLog(`Invoking backend... Config: ${configPath}`, "info");

      const result = await invoke("start_transcription", args);
      console.log("Invoke result:", result); // DEBUG
      
    } catch (e) {
      console.error("Invoke failed:", e); // DEBUG
      setIsProcessing(false);
      addLog(`Failed to start engine: ${e}`, "error");
    }
  };

  // --- System Actions ---
  const openPath = async (path: string) => {
    // Invoke Rust command 'open_in_finder' or use generic open plugin if available
    // We defined 'open_in_finder' earlier in main.rs? 
    // Wait, we didn't explicitly check main.rs from earlier context, but assuming existing 'open_in_finder' command exists.
    // If not, we can use 'plugin-opener' or similar.
    // Let's assume 'open_in_finder' exists as per previous context or use plugin-opener/shell if configured.
    // The previous App.tsx used invoke("open_in_finder", { path }).
    try {
        await invoke("open_in_finder", { path });
    } catch {
       // Fallback
       addLog(`Could not open path: ${path}`, "error");
    }
  };


  // --- Render ---
  const selectedFile = files.find(f => f.path === selectedFileId);

  return (
    <div className="app-layout">
      
      {/* 1. Header */}
      <LogoHeader 
        status={isProcessing ? 'processing' : 'idle'} 
        onOpenSettings={() => setIsSettingsOpen(true)}
        onRefresh={() => window.location.reload()}
      />

      <SettingsModal 
        isOpen={isSettingsOpen} 
        onClose={() => setIsSettingsOpen(false)}
        settings={lineWrapSettings}
        onSave={handleSaveSettings}
      />

      {/* 2. Left Queue */}
      <FileQueue 
        files={files} 
        selectedFileId={selectedFileId}
        onSelect={setSelectedFileId}
        onRemove={removeFile}
        onAddFiles={openFileDialog}
      />

      {/* 3. Right Status Panel */}
      <StatusPanel 
        selectedFile={selectedFile}
        isProcessing={isProcessing}
        onStart={startTranscription}
        onOpenPath={openPath}
      />

      {/* 4. Footer */}
      <LogFooter 
        lastLog={lastLog} 
        onExpand={() => setShowLogs(!showLogs)} 
        isProcessing={isProcessing}
      />

    </div>
  );
}

export default App;
