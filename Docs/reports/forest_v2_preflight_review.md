# Sophia Forest v2 Preflight Review (Current-State Aligned)

Date: 2026-02-18  
Scope: validate v2 spec before direct execution

## 1. What exists now (fact-based)
- Forest analysis pipeline exists:
  - `POST /forest/projects/{name}/grove/analyze`
  - writes SonE artifacts (`last_delta.sone.json`, `dependency_graph.json`, `risk_snapshot.json`)
- Canopy control payload exists:
  - `GET /forest/projects/{name}/canopy/data`
  - split response: `human_view` + `ai_view`
- Focus policy exists with server enforcement:
  - WIP lock and hard/soft lock in `focus_policy_service`
  - checked by work/forest endpoints
- Idea freeze lifecycle exists:
  - freeze/list/promote APIs

## 2. Gaps vs v2 target
1. No dedicated `/sync/*` handshake endpoints yet.
2. No explicit v2 node state model API contract (`DRAFT/ACTIVE/FROZEN`) exposed to clients.
3. ChangeRequest is not yet first-class in API flow for `DONE -> ACTIVE`.
4. Current DB persists operational states (`READY/IN_PROGRESS/...`) not v2 logical states.

## 3. Risk if spec is applied directly (no adaptation)
1. Endpoint duplication/conflict with existing `/forest/*` and `/work/*`.
2. Immediate model replacement would break current UI and tests.
3. Existing pipeline and user workflow would pause during migration.

## 4. Recommended development process (incremental)
Phase A (now):
- introduce v2 logical layer only:
  - `core/forest_logic.py`
  - transition/WIP/handshake policy unit tests

Phase B:
- add adapter `/sync/*` endpoints that map to existing services.
- keep legacy endpoints alive.

Phase C:
- move UI action buttons to `/sync/*` gradually.
- retain canopy human-view default.

## 5. SonE decision
- Keep SonE in v2 as a selective verification gate.
- Use SonE strongly for:
  - module boundary changes
  - dependency-impact change
  - rename/merge/split level refactors
- Allow fast-path without deep SonE for low-risk micro tasks.

## 6. Acceptance criteria for starting v2 backend work
1. v2 logical state module exists and tests pass.
2. Existing forest/work tests stay green.
3. No breaking change to current canopy/focus UX.

