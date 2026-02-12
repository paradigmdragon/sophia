#!/bin/bash
# Startup script for Sophia API Server

# 1. Project Root
cd "$(dirname "$0")"

# 2. Check for Virtual Environment
VENV_PYTHON="./.venv/bin/python"
SYSTEM_PYTHON="python3"

if [ -f "$VENV_PYTHON" ]; then
    PYTHON_EXEC="$VENV_PYTHON"
    echo "[Sophia] Using Virtual Environment: $VENV_PYTHON"
else
    PYTHON_EXEC="$SYSTEM_PYTHON"
    echo "[Sophia] Using System Python: $SYSTEM_PYTHON"
fi

# 3. Set PYTHONPATH to Include Core
export PYTHONPATH=$(pwd)

# 4. Run Server
echo "[Sophia] Starting API Server on Port 8090..."
exec $PYTHON_EXEC api/server.py
