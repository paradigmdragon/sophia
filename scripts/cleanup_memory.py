from __future__ import annotations
import sys
import json
from hashlib import sha256
from pathlib import Path
from sqlalchemy import func
from core.memory.schema import Verse, create_session_factory, _normalize_db_path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def get_verse_hash(verse: Verse) -> str:
    # Use same hashing logic as migration script
    dt_str = verse.created_at.isoformat() if verse.created_at else ""
    payload = (
        f"{dt_str}|{verse.speaker}|{verse.perspective}|"
        f"{int(verse.is_constitution_active)}|{verse.content}"
    )
    return sha256(payload.encode("utf-8")).hexdigest()

def cleanup_duplicates(db_path: str = "sqlite:///sophia.db", dry_run: bool = True):
    print(f"Starting cleanup on {db_path} (Dry Run: {dry_run})")
    session_factory = create_session_factory(db_path)
    session = session_factory()
    
    try:
        # Group by Chapter
        chapters = session.query(Verse.chapter_id).distinct().all()
        total_removed = 0
        
        for (chap_id,) in chapters:
            verses = session.query(Verse).filter(Verse.chapter_id == chap_id).order_by(Verse.id.asc()).all()
            seen_hashes = set()
            duplicates = []
            
            for v in verses:
                h = get_verse_hash(v)
                if h in seen_hashes:
                    duplicates.append(v)
                else:
                    seen_hashes.add(h)
            
            if duplicates:
                print(f"Chapter {chap_id}: Found {len(duplicates)} duplicates.")
                for d in duplicates:
                    if not dry_run:
                        session.delete(d)
                total_removed += len(duplicates)
        
        if not dry_run:
            session.commit()
            print(f"Cleanup Complete. Removed {total_removed} verses.")
        else:
            print(f"Dry Run Complete. Would remove {total_removed} verses.")
            
    finally:
        session.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="sqlite:///sophia.db", help="Database path")
    parser.add_argument("--execute", action="store_true", help="Run in execute mode (default dry-run)")
    args = parser.parse_args()
    
    cleanup_duplicates(args.db, dry_run=not args.execute)
