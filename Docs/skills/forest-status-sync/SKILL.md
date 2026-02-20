---
name: forest-status-sync
description: Synchronize current Sophia implementation status into Sophia Forest (progress snapshot + roadmap + canopy export) after coding work.
---

# Forest Status Sync

## Use this skill when
- A coding task is completed and current progress must be reflected in Sophia Forest.
- You need an updated roadmap snapshot before the next task.

## Workflow
1. Ensure worktree changes are in expected state.
2. Run status sync:
- `make forest-sync`
3. Verify outputs:
- `/Users/dragonpd/Sophia/forest/project/sophia/status/progress_snapshot.json`
- `/Users/dragonpd/Sophia/forest/project/sophia/status/progress_roadmap.md`
- `/Users/dragonpd/Sophia/forest/project/sophia/dashboard/index.html`
4. Confirm canopy API shows synced state:
- `GET /forest/projects/sophia/canopy/data` -> `progress_sync.status == "synced"`

## Notes
- This flow is append/update oriented and does not mutate source spec files.
- If sync fails, fix the underlying API/DB error first, then re-run.
