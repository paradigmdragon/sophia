#!/bin/bash
# Sophia CLI Wrapper

# 1. Project Root
cd "$(dirname "$0")"

# 2. Check for Virtual Environment
VENV_PYTHON="./.venv/bin/python"
SYSTEM_PYTHON="python3"

if [ -f "$VENV_PYTHON" ]; then
    PYTHON_EXEC="$VENV_PYTHON"
else
    PYTHON_EXEC="$SYSTEM_PYTHON"
fi

# 3. Set PYTHONPATH
export PYTHONPATH=$(pwd)

# 4. Handle Commands
if [ "$1" = "start" ]; then
    echo "[Sophia] Killing stale processes..."
    pkill -f "python api/server.py" || true
    pkill -f "tauri" || true
    pkill -f "vite" || true
    
    echo "[Sophia] Starting Backend..."
    ./start_server.sh &
    
    echo "[Sophia] Starting Frontend..."
    ./start_desktop.sh &
    
    wait
else
    # Run CLI
    exec $PYTHON_EXEC core/engine/cli.py "$@"
fi
