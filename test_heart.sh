#!/bin/bash
# Manual CLI Test Script for Heart Engine
# 1. Reset DB
rm -f sophia.db

# 2. Ingest
echo "=== 1. Ingest ==="
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python core/engine/cli.py ingest "heart_test_001" > ingest_heart.txt
EP_ID=$(cat ingest_heart.txt | grep "Created Episode" | awk '{print $3}')
echo "Episode ID: $EP_ID"

# 3. Propose Low Confidence (Should trigger P3)
echo "=== 2. Propose Low Confidence ==="
PYTHONPATH=. /Users/dragonpd/Sophia/.venv/bin/python core/engine/cli.py propose "$EP_ID" --text "Unknown stuff"
# Expect P3 message in queue

# 4. Propose & Adopt Conflict (Should trigger P1)
echo "=== 3. Conflict Trigger ==="
# Inject two conflicting candidates via python script for precision
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
ep_id = "$EP_ID"

# 1. Propose & Adopt D=EQUIVALENCE
c_ids_1 = workflow.propose(ep_id, [{
    "backbone_bits": ChunkD.EQUIVALENCE, 
    "facets": [{"id": FacetID.CERTAINTY, "value": FacetValueCertainty.PENDING}],
    "note": "Force Equivalence",
    "confidence": 90
}], source="heart_test")
workflow.adopt(ep_id, c_ids_1[0])

# 2. Propose & Adopt D=OPPOSITIONAL
c_ids_2 = workflow.propose(ep_id, [{
    "backbone_bits": ChunkD.OPPOSITIONAL, 
    "facets": [{"id": FacetID.CERTAINTY, "value": FacetValueCertainty.PENDING}],
    "note": "Force Opposition",
    "confidence": 90
}], source="heart_test")

try:
    workflow.adopt(ep_id, c_ids_2[0])
    print("Conflict Adopted.")
except Exception as e:
    print(f"Adoption Error: {e}")

# Check MessageQueue
msgs = session.query(MessageQueue).all()
print(f"Total Messages: {len(msgs)}")
for m in msgs:
    print(f"[{m.priority}] {m.type}: {m.content}")

session.close()
EOF
