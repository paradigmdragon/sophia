import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.engine.schema import MessageQueue, Base
from core.engine.workflow import WorkflowEngine

# Setup
DB_PATH = "sqlite:///sophia_test_disp.db"
engine = create_engine(DB_PATH)
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

workflow = WorkflowEngine(lambda: Session())
ep_id = "ep_test"

print("=== 1. Setup & Trigger ===")
# Trigger P3 (Low Confidence)
workflow.heart.trigger_message("P3", "ASK", "low_conf", "Low Conf Msg", ep_id)
# Trigger P1 (Conflict)
workflow.heart.trigger_message("P1", "NOTICE", "conflict", "Conflict Msg", ep_id)

print("\n=== 2. Dispatch (FOCUS) ===")
# Default State is FOCUS. Only P1 should pass.
msg = workflow.heart.dispatch()
assert msg is not None
assert msg.priority == "P1"
print("✅ Dispatched P1 in FOCUS")

print("\n=== 3. Dispatch Again (FOCUS) ===")
# P1 served. P3 pending. State FOCUS blocks P3.
msg = workflow.heart.dispatch()
assert msg is None
print("✅ Blocked P3 in FOCUS")

print("\n=== 4. Change State to IDLE ===")
workflow.heart.set_state("IDLE")
# Now P3 should pass.
msg = workflow.heart.dispatch()
assert msg is not None
assert msg.priority == "P3"
print("✅ Dispatched P3 in IDLE")

print("\n=== 5. Cooldown Check ===")
# Trigger another P1
workflow.heart.trigger_message("P1", "NOTICE", "conflict2", "Conflict 2", ep_id)
# P1 Cooldown is 10m. Last P1 sent ~0s ago.
msg = workflow.heart.dispatch()
assert msg is None
print("✅ Blocked P1 due to Cooldown")

print("\n=== 6. Status Summary ===")
summary = workflow.heart.get_status_summary()
print(f"State: {summary['state']}")
print(f"Cooldown P1 Rem: {summary['cooldown_status']['P1']:.1f}s")
assert summary['cooldown_status']['P1'] > 500 # Should be ~600s
print("✅ Status Checked")

print("\nALL TESTS PASSED")
