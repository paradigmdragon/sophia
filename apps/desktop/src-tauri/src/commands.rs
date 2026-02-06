use tauri::AppHandle;
use std::process::Command;
use crate::process::run_python_transcription;

#[tauri::command]
pub fn start_transcription(
    app: AppHandle,
    files: Vec<String>,
    outdir: String,
    config_path: Option<String>,
) -> Result<String, String> {
    // Determine python path and core script path
    // For v0.1.2 development, assume we are running in dev mode
    // We need to point to the virtual environment created in root
    // Root is ../../.. from src-tauri/target/debug/... but better to use absolute paths or relative to project root
    
    // Hardcode for dev environment:
    // Python: <project_root>/Sophia/.venv/bin/python
    // Script Dir: <project_root>/Sophia/core
    
    // In production bundle, this logic needs to be more robust (sidecar or resource)
    
    let home_dir = std::env::var("HOME").unwrap_or_else(|_| "/Users/dragonpd".to_string());
    let project_root = format!("{}/Sophia", home_dir);
    let python_path = format!("{}/.venv/bin/python", project_root);
    let script_dir = format!("{}/core", project_root);
    
    let final_config_path = if let Some(path) = config_path {
        path
    } else {
        format!("{}/sone/subtitle.asr.sone", project_root)
    };
    
    // Log for debugging
    println!("Starting transcription with python: {}, core: {}, config: {}", python_path, script_dir, final_config_path);
    
    run_python_transcription(
        app,
        python_path,
        script_dir,
        files,
        outdir,
        Some(final_config_path)
    )?;
    
    Ok("Started".to_string())
}

#[tauri::command]
pub fn open_in_finder(path: String) {
    #[cfg(target_os = "macos")]
    {
        Command::new("open")
            .arg("-R")
            .arg(path)
            .spawn()
            .unwrap();
    }
}
