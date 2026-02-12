# Walkthrough - UI Structure Reset & Title Bar Fix

## Summary
The application has been refactored to use a strict 5-route structure with a custom macOS Title Bar, replacing the native one. The Editor page has been cleaned up to provide a minimal writing environment.

## Changes

### 1. Title Bar Overhaul
- **Removed Native Title Bar**: Configured `tauri.conf.json` to use `Overlay` style.
- **Added Custom Title Bar**: Implemented `TitleBar.tsx` with:
    - **Sophia Text**: Added application name "Sophia" to the left.
    - **Full Drag Region**: Ensured the entire bar (except buttons) is draggable using `WebkitAppRegion: "drag"`.
    - Navigation icons (Editor, Captions, Settings) with `no-drag` region.
    - Traffic light padding (macOS).

### 2. Route Structure
- **5 Distinct Routes**:
    - `/` (Editor): Minimal markdown editor.
    - `/hearing`: Dedicated hearing page (moved from sidebar).
    - `/note`: (Placeholder/Future Use)
    - `/chat`: Chat interface.
    - `/settings`: Settings page (restored full Korean UI).

### 3. Editor Cleanup
- **Removed Sidebars**: No more Context/Hearing tabs in the editor.
- **Removed Big Headers**: Deleted the large date and "Start thinking" headers.
- **Minimal Header**: Now just shows `YYYY-MM-DD.md`.

### 4. Layout Fixes
- **Hearing Page**: Removed the redundant header that was causing alignment issues ("leaning to one side").
- **HearingTab Content**: Refactored `FileQueue` and `StatusPanel` to use full-width flex layout (50/50 split), fixing the issue where half the screen was empty.

### 5. File Sidebar (New Feature & Enhancements)
- **Implemented macOS Notes-style Sidebar**:
    - **Resizable**: Drag the right edge to adjust width.
    - **Renaming**: Double-click to rename.
    - **Clean UI**: Removed "FOLDERS" text.
    - **Auto-Create**: Automatically creates `Welcome.md` if empty.

### 6. Bug Fixes & Refinements
- **Title Bar Drag & Traffic Lights**: 
    - Restored native macOS "Traffic Lights" (🔴🟡🟢) by reverting to `titleBarStyle: "Overlay"` in `tauri.conf.json`.
    - Fixed drag issues by using `<header>` with `data-tauri-drag-region`, setting `z-index: 100`.
    - **Crucial Fix**: Added `WebkitAppRegion: "drag"` CSS property as a fallback for macOS.
- **File System Permissions**: Added missing `fs:allow-mkdir`, `fs:allow-remove`, and `fs:allow-rename` permissions.
- **Auto-Create**: The app automatically creates a "Welcome.md" note.

## Verification Results

### Automated Checks
- `npm run build`: **PASSED** (Error-free build).

### Manual Verification Required
- Launch the app and check:
    1. **Title Bar Text**: "Sophia" visible?
    2. **Window Dragging**: Works everywhere on title bar?
    3. **Hearing Page**:
        - Is the header gone and layout aligned?
        - **Does the content fill the full width?** (No more empty right side)
    4. **Settings Page**: Korean UI intact?
