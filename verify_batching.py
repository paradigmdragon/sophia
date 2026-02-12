import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.engine.schema import MessageQueue, Base
from core.engine.workflow import WorkflowEngine

# Setup
DB_PATH = "sqlite:///sophia_test_batch.db"
engine = create_engine(DB_PATH)
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

workflow = WorkflowEngine(lambda: Session())
ep_id = "ep_batch"
workflow.heart.set_state("IDLE") # Ensure P3 can pass

print("=== 1. Setup & Trigger Batch ===")
# Trigger 3 P3 messages for same episode (Unique intents to bypass deduplication)
workflow.heart.trigger_message("P3", "ASK", "low_conf_1", "Msg 1", ep_id)
workflow.heart.trigger_message("P3", "ASK", "low_conf_2", "Msg 2", ep_id)
workflow.heart.trigger_message("P3", "ASK", "low_conf_3", "Msg 3", ep_id)

# Trigger 1 P3 for another episode
workflow.heart.trigger_message("P3", "ASK", "low_conf_other", "Msg Other", "ep_other")

print("\n=== 2. Dispatch Batch ===")
# Should pick up the batch for ep_batch first (created earlier/same time)
# Wait, sorting is by Priority then CreatedAt.
# We have 4 P3 messages.
# If My dispatcher iterates pending messages:
# 1. Msg 1 (P3, ep_batch). Batch check -> finds 3. Returns Summary.
msg = workflow.heart.dispatch()
assert msg is not None
print(f"Dispatched: {msg.content}")

assert "3 new updates" in msg.content
print("✅ Batch Summary Correct")

print("\n=== 3. Verify DB Status ===")
session = Session()
# Msg 1, 2, 3 should be SERVED.
count_served = session.query(MessageQueue).filter(
    MessageQueue.episode_id == ep_id, 
    MessageQueue.status == 'SERVED'
).count()
assert count_served == 3
print(f"✅ {count_served} messages marked SERVED")
session.close()

print("\n=== 4. Dispatch Next (Single) ===")
# Reset P3 Cooldown for testing
workflow.heart.dispatcher.last_sent["P3"] = None

# Should pick up msg for ep_other (P3)
# It has only 1 message, so no batch summary.
msg = workflow.heart.dispatch()
assert msg is not None
print(f"Dispatched: {msg.content}")
assert "Msg Other" in msg.content
print("✅ Single Message Dispatched")

print("\nALL TESTS PASSED")
