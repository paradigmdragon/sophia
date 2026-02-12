#!/bin/bash
# Startup script for Sophia Desktop App (Frontend)

# 1. Project Root
cd "$(dirname "$0")"

# 2. Navigate to Frontend Directory
cd apps/desktop

# 3. Install dependencies if needed (optional)
# npm install

# 4. Run Tauri Dev
echo "[Sophia] Starting Desktop App..."
npm run tauri dev
