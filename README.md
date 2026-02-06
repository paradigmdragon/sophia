# Sophia

**"Sophia is a local-first AI workspace, not a chatbot."**

## Overview
Sophia is a desktop application designed to provide a privacy-focused, local-first AI environment for transcription and refinement tasks. It leverages local models (like Faster-Whisper) to process data without leaving your machine.

## Project Structure
- `core/`: Python-based core engine (ASR, Refinement, Pipeline).
- `apps/`: Frontend applications (e.g., `desktop` Tauri app).
## Sophia Workspace Specification v0.1
Sophia is defined not as a simple program but as a **Shared Workspace** between agents.

### Core Principles
1.  **Workspace-First**: All features are represented by file operations.
2.  **Shared Environment**: OSS (Local LLM) and IDE Agents share the same workspace.
3.  **Permission Model**: Distinguished by file modification rights.

### Directory Structure
- `workspace/`: The actual working area.
    - `inbox/`: Input media/scripts.
    - `outputs/`: Generated subtitles and reports.
    - `sone/`: SonE documents (Generated/Manual).
    - `tasks/`: Task definitions (JSON).
    - `events/`: Event streams.
- `apps/`: Frontend applications.
- `core/`: Python-based core engine.

For full details, please refer to [Sophia Workspace Specification v0.1](Docs/Sophia_Workspace_Spec_v0.1.md).

## Getting Started
(Usage instructions to be added)
