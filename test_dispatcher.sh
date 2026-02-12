#!/bin/bash
# Manual CLI Test Script for Heart Dispatcher
# 1. Reset DB
rm -f sophia.db

# 2. Ingest
echo "=== 1. Ingest ==="
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python core/engine/cli.py ingest "dispatch_test_001" > ingest_disp.txt
EP_ID=$(cat ingest_disp.txt | grep "Created Episode" | awk '{print $3}')

# 3. Trigger Messages (P3 and P1)
echo "=== 2. Trigger Messages ==="
# P3: Low Confidence
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python core/engine/cli.py propose "$EP_ID" --text "Unknown stuff"
# P1: Conflict (via python script injection)
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python <<EOF
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.engine.workflow import WorkflowEngine
from core.engine.schema import MessageQueue
from core.engine.constants import ChunkD, FacetID, FacetValueCertainty

engine = create_engine('sqlite:///sophia.db')
Session = sessionmaker(bind=engine)
session = Session()
workflow = WorkflowEngine(lambda: session)
workflow.heart.trigger_message("P1", "NOTICE", "conflict_check", "Simulated Conflict", "$EP_ID")
session.close()
EOF

# 4. Check Status (FOCUS Mode)
echo "=== 3. Status (FOCUS) ==="
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python core/engine/cli.py status

# 5. Dispatch (Should only process P1)
echo "=== 4. Dispatch (Expected P1) ==="
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python core/engine/cli.py dispatch

# 6. Dispatch Again (Should be empty due to Cooldown)
echo "=== 5. Dispatch Again (Expected Empty - Cooldown) ==="
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python core/engine/cli.py dispatch

# 7. Change State to IDLE
echo "=== 6. Set State IDLE ==="
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python core/engine/cli.py set_state IDLE

# 8. Dispatch (Should process P3)
echo "=== 7. Dispatch (Expected P3) ==="
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python core/engine/cli.py dispatch

# 9. Final Status
echo "=== 8. Final Status ==="
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python core/engine/cli.py status
