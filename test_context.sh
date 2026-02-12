#!/bin/bash
# Manual CLI Test Script for Context Gate
# 1. Reset DB
rm -f sophia.db
rm -f heart_state.json

# 2. Ingest
echo "=== 1. Ingest ==="
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python core/engine/cli.py ingest "context_test_001" > ingest_ctx.txt
EP_ID=$(cat ingest_ctx.txt | grep "Created Episode" | awk '{print $3}')

# 3. Trigger Message with Context Requirement (via Python script)
echo "=== 2. Trigger Context Message ==="
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python <<EOF
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.engine.workflow import WorkflowEngine
from core.engine.schema import MessageQueue
from core.engine.constants import ChunkA

engine = create_engine('sqlite:///sophia.db')
Session = sessionmaker(bind=engine)
session = Session()

workflow = WorkflowEngine(lambda: session)
# Require ChunkA = STATE (1)
workflow.heart.trigger_message(
    "P2", "NOTICE", "ctx_msg", "Context Dependent Message", "$EP_ID", 
    context={"chunk_a": 1}
)
session.close()
EOF

# 4. Check Status (Expect Orange Indicator for P2)
echo "=== 3. Status (Expect 🟠) ==="
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python core/engine/cli.py status

# 5. Dispatch without Context (Should Fail)
echo "=== 4. Dispatch NO Context (Expect Fail) ==="
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python core/engine/cli.py dispatch

# 6. Dispatch with Wrong Context (Should Fail)
echo "=== 5. Dispatch Wrong Context (Expect Fail) ==="
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python core/engine/cli.py dispatch --chunk_a 2

# 7. Dispatch with Correct Context (Should Succeed)
echo "=== 6. Dispatch Correct Context (Expect Success) ==="
# Note: P2 is blocked by FOCUS state. We need to be in IDLE or P1.
# Let's switch to IDLE first.
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python core/engine/cli.py set_state IDLE

# Now dispatch with context
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python core/engine/cli.py dispatch --chunk_a 1

# 8. Auto-Push Test
echo "=== 7. Auto-Push Test ==="
# Trigger P1 message (no context req)
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python <<EOF
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.engine.workflow import WorkflowEngine
engine = create_engine('sqlite:///sophia.db')
Session = sessionmaker(bind=engine)
session = Session()
workflow = WorkflowEngine(lambda: session)
workflow.heart.trigger_message("P1", "NOTICE", "auto_msg", "Auto Push Message", "$EP_ID")
session.close()
EOF

# Reset state to FOCUS then back to IDLE to trigger auto-push
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python core/engine/cli.py set_state FOCUS
echo "--- Switching to IDLE (Expect Auto-Dispatch) ---"
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python core/engine/cli.py set_state IDLE
