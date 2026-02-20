import argparse
import sys
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.engine.workflow import WorkflowEngine
from core.engine.encoder import CandidateEncoder
from core.engine.schema import Base, Episode, Candidate
from core.engine.search import search_episodes
from core.engine.constants import ChunkA, ChunkB, ChunkC, ChunkD

# Database Setup (Persistent File for CLI)
DB_PATH = "sqlite:///sophia.db"
engine = create_engine(DB_PATH)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def get_session():
    return Session()

workflow = WorkflowEngine(get_session)
encoder = CandidateEncoder()

def cmd_ingest(args):
    """
    sophia ingest <ref_uri>
    """
    # If ref_uri is simple filename, assume it's in SOPHIA_DOCS if exists
    import os
    from core.engine.constants import SOPHIA_DOCS
    
    target_uri = args.ref_uri
    if not os.path.exists(target_uri):
        potential = os.path.join(SOPHIA_DOCS, target_uri)
        if os.path.exists(potential):
            target_uri = potential
            
    log_ref = {"uri": target_uri, "type": "cli_manual"}
    ep_id = workflow.ingest(log_ref)
    print(f"Created Episode: {ep_id}")

def cmd_propose(args):
    """
    sophia propose <ep_id> --text "..."
    """
    text = args.text or "Default context for proposal"
    candidates_data = encoder.generate_candidates(text)
    
    c_ids = workflow.propose(args.ep_id, candidates_data, source="cli")
    
    print(f"Proposed {len(c_ids)} candidates based on text: '{text}'")
    
    session = get_session()
    try:
        for c_id in c_ids:
            cand = session.query(Candidate).filter_by(candidate_id=c_id).first()
            print(f"  - {c_id}: Confidence={cand.confidence}% | Note='{cand.note_thin}'")
            print(f"    Backbone: 0x{cand.backbone_bits:04X}")
    finally:
        session.close()

def cmd_adopt(args):
    """
    sophia adopt <ep_id> <cand_id>
    """
    try:
        bb_id = workflow.adopt(args.ep_id, args.cand_id)
        print(f"Adopted Backbone: {bb_id}")
    except Exception as e:
        print(f"Error adopting candidate: {e}")

def cmd_reject(args):
    """
    sophia reject <ep_id> <cand_id>
    """
    try:
        workflow.reject(args.ep_id, args.cand_id)
        print(f"Rejected Candidate: {args.cand_id}")
        print("Logged to data/error_patterns.jsonl")
    except Exception as e:
        print(f"Error rejecting candidate: {e}")

def cmd_search(args):
    """
    sophia search --mask_a 0xN ... --facet_id 0xN --facet_val 0xN
    """
    session = get_session()
    try:
        # Parse masks
        ma = int(args.mask_a, 16) if args.mask_a else None
        mb = int(args.mask_b, 16) if args.mask_b else None
        mc = int(args.mask_c, 16) if args.mask_c else None
        md = int(args.mask_d, 16) if args.mask_d else None
        
        # Parse facet (single filter support for CLI v0.1)
        facets = None
        if args.facet_id and args.facet_val:
            facets = [{"id": int(args.facet_id, 16), "value": int(args.facet_val, 16)}]
            
        results = search_episodes(session, ma, mb, mc, md, facets)
        print(f"Found {len(results)} episodes:")
        for ep in results:
            print(f"  - {ep.episode_id} ({ep.status})")
    finally:
        session.close()

def cmd_heart_status(args):
    """
    sophia status
    """
    summary = workflow.heart.get_status_summary()
    counts = summary['queue_counts']
    
    # Presence Indicator
    # If P1 > 0 -> Red Block (Urgent)
    # If P2 > 0 -> Orange Block (Pending)
    indicator = "○"
    if counts['P1'] > 0:
        indicator = "🔴" # P1 Urgent
    elif counts['P2'] > 0:
        indicator = "🟠" # P2 Pending

    print(f"=== Sophia Heart Status ({summary['state']}) {indicator} ===")
    print("Queue Counts:")
    for p, count in counts.items():
        print(f"  {p}: {count}")
    
    print("\nCooldowns (Remaining Seconds):")
    for p, rem in summary['cooldown_status'].items():
        print(f"  {p}: {rem:.1f}s")

def cmd_heart_dispatch(args):
    """
    sophia dispatch --chunk_a <int>
    """
    context = {}
    if args.chunk_a:
        context["chunk_a"] = int(args.chunk_a)
    if args.chunk_c:
        context["chunk_c"] = int(args.chunk_c)
        
    msg = workflow.heart.dispatch(current_context=context)
    if msg:
        print(f"Dispatched: [{msg.priority}] {msg.content}")
    else:
        print("No message dispatched (Gate/Cooldown/Context/Empty).")

def cmd_heart_state(args):
    """
    sophia set_state <state>
    """
    workflow.heart.set_state(args.state)
    print(f"Heart State set to: {args.state}")

def main():
    parser = argparse.ArgumentParser(description="Sophia Bit-Hybrid Engine CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Ingest
    p_ingest = subparsers.add_parser("ingest", help="Create new episode")
    p_ingest.add_argument("ref_uri", help="Reference URI (e.g., chat_log_id)")
    
    # Propose
    p_propose = subparsers.add_parser("propose", help="Propose candidates")
    p_propose.add_argument("ep_id", help="Episode ID")
    p_propose.add_argument("--text", help="Context text for proposal", default="")
    
    # Adopt
    p_adopt = subparsers.add_parser("adopt", help="Adopt candidate as backbone")
    p_adopt.add_argument("ep_id", help="Episode ID")
    p_adopt.add_argument("cand_id", help="Candidate ID")
    
    # Reject
    p_reject = subparsers.add_parser("reject", help="Reject candidate")
    p_reject.add_argument("ep_id", help="Episode ID")
    p_reject.add_argument("cand_id", help="Candidate ID")
    
    # Search
    p_search = subparsers.add_parser("search", help="Search episodes")
    p_search.add_argument("--mask_a", help="Chunk A Mask (Hex)")
    p_search.add_argument("--mask_b", help="Chunk B Mask (Hex)")
    p_search.add_argument("--mask_c", help="Chunk C Mask (Hex)")
    p_search.add_argument("--mask_d", help="Chunk D Mask (Hex)")
    p_search.add_argument("--facet_id", help="Facet ID (Hex)")
    p_search.add_argument("--facet_val", help="Facet Value (Hex)")

    # Heart Status
    p_status = subparsers.add_parser("status", help="Show Heart Engine status")

    p_dispatch = subparsers.add_parser("dispatch", help="Trigger Dispatcher")
    p_dispatch.add_argument("--chunk_a", help="Context Chunk A Value")
    p_dispatch.add_argument("--chunk_c", help="Context Chunk C Value")

    # Heart State
    p_state = subparsers.add_parser("set_state", help="Set Heart State (FOCUS, IDLE)")
    p_state.add_argument("state", help="State (FOCUS, IDLE, WRITING)")

    args = parser.parse_args()
    
    if args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "propose":
        cmd_propose(args)
    elif args.command == "adopt":
        cmd_adopt(args)
    elif args.command == "reject":
        cmd_reject(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "status":
        cmd_heart_status(args)
    elif args.command == "dispatch":
        cmd_heart_dispatch(args)
    elif args.command == "set_state":
        cmd_heart_state(args)
    # Bridge
    p_bridge = subparsers.add_parser("bridge", help="Trigger Codex Skill manually")
    p_bridge.add_argument("state_code", help="State Code (e.g. 0x6)")
    p_bridge.add_argument("--uri", help="Resource URI")

    args = parser.parse_args()
    
    if args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "propose":
        cmd_propose(args)
    elif args.command == "adopt":
        cmd_adopt(args)
    elif args.command == "reject":
        cmd_reject(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "status":
        cmd_heart_status(args)
    elif args.command == "dispatch":
        cmd_heart_dispatch(args)
    elif args.command == "set_state":
        cmd_heart_state(args)
    elif args.command == "bridge":
        cmd_bridge(args)
    else:
        parser.print_help()

def cmd_bridge(args):
    """
    sophia bridge <state_code> --uri ...
    """
    from core.engine.skill_bridge import SkillBridge
    bridge = SkillBridge()
    
    context = {}
    if args.uri:
        context['uri'] = args.uri
        
    result = bridge.check_and_trigger(args.state_code, context)
    if result:
        print(json.dumps(result, indent=2))
    else:
        print(f"No skill registered for state: {args.state_code}")

if __name__ == "__main__":
    main()
