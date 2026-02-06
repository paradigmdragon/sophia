use tauri::{AppHandle, Manager, Emitter};
use std::process::{Command, Stdio};
use std::io::{BufRead, BufReader};
use std::thread;
use std::sync::{Arc, Mutex};
use std::path::PathBuf;

#[derive(Clone, serde::Serialize)]
struct Payload {
    event: String,
    data: Option<serde_json::Value>,
}

pub fn run_python_transcription(
    app: AppHandle,
    python_path: String,
    script_path: String,
    files: Vec<String>,
    outdir: String,
    config: Option<String>,
) -> Result<(), String> {
    
    thread::spawn(move || {
        let mut cmd = Command::new(&python_path);
        
        // Arguments
        cmd.arg("-m")
           .arg("app.cli")
           .arg("transcribe")
           .arg("--files")
           .arg(files.join(","))
           .arg("--outdir")
           .arg(&outdir);
           
        if let Some(cfg) = config {
            cmd.arg("--config").arg(cfg);
        }

        // Set CWD to core directory to allow module imports
        // Assuming script_path is absolute path to core directory or similar
        // Ideally we run from 'core' dir where 'app' package resides
        let core_dir = PathBuf::from(&script_path); // script_path passed as core root
        cmd.current_dir(&core_dir);

        // Environment setup if needed (PYTHONPATH etc)
        cmd.env("PYTHONUNBUFFERED", "1");
        // Add core to PYTHONPATH to ensure app module is found
        // cmd.env("PYTHONPATH", core_dir.to_str().unwrap());

        cmd.stdout(Stdio::piped());
        cmd.stderr(Stdio::piped());

        let mut child = match cmd.spawn() {
            Ok(c) => c,
            Err(e) => {
                let _ = app.emit("run_error", format!("Failed to spawn python: {}", e));
                return;
            }
        };

        // Clone app handle for stderr thread
        let app_stderr = app.clone();

        if let Some(stdout) = child.stdout.take() {
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                if let Ok(l) = line {
                    // Try to parse as JSON log
                    if let Ok(json_val) = serde_json::from_str::<serde_json::Value>(&l) {
                        if let Some(event_type) = json_val.get("event").and_then(|v| v.as_str()) {
                            let _ = app.emit(event_type, &json_val);
                        } else {
                            let _ = app.emit("log", &json_val);
                        }
                    } else {
                        let _ = app.emit("log_raw", l);
                    }
                }
            }
        }

        // Handle stderr in a separate thread or just read it (blocking here would block stdout loop if strict separation needed, but thread spawn is easier)
        // For simplicity, let's just create another thread for stderr since piped streams are blocking
        // But wait, the current closure is already in a thread. We can't block on both stdout and stderr in same thread easily without async or select.
        // Simple fix: spawn a mini thread for stderr
        
        if let Some(stderr) = child.stderr.take() {
            thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines() {
                    if let Ok(l) = line {
                        let _ = app_stderr.emit("log_raw", format!("STDERR: {}", l));
                    }
                }
            });
        }

        // Wait for finish
        let status = child.wait();
        match status {
            Ok(s) => {
                let _ = app.emit("process_exit", format!("Exit code: {}", s));
            },
            Err(e) => {
                let _ = app.emit("process_error", format!("Wait error: {}", e));
            }
        }
    });

    Ok(())
}
