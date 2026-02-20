# Sophia Forest v2.0 Architecture Spec
Version: 2.0.0 (refined for current codebase)
Core Concept: Focus-enforcing State Synchronization Server

## 1) Identity
Sophia Forest is a control system, not a passive dashboard.

Goals:
1. Sync context between user and agent.
2. Enforce focus (WIP guard).
3. Separate drafts from canonical/committed state.

## 2) Current-Code Compatibility
This repository already has:
- Work state backbone: `READY/IN_PROGRESS/DONE/BLOCKED/FAILED` (`work_packages`)
- Focus lock policy and WIP checks in API (`focus_policy_service`)
- Forest analysis and canopy data generation (`core/forest/grove.py`, `core/forest/canopy.py`)

v2 introduces a logical abstraction layer:
- `DRAFT/ACTIVE/DONE/FROZEN/BLOCKED` (logical state machine)
- mapped to existing persistence without breaking current endpoints.

Mapping (v2 logical -> existing operational):
- `ACTIVE` -> `IN_PROGRESS`
- `DONE` -> `DONE`
- `BLOCKED` -> `BLOCKED|FAILED`
- `DRAFT` -> `READY` (until dedicated node table is introduced)
- `FROZEN` -> idea records in `mind_items` (`freeze_status:*`)

## 3) Core Models (v2 logical contract)
### 3.1 Constitution
- `l1_anchor` (<= 200 chars)
- `l2_rules` (list of hard constraints)
- `l3_knowledge_index` (refs only)

### 3.2 Node
- `id`, `title`
- `state` (`DRAFT|ACTIVE|DONE|FROZEN|BLOCKED`)
- `priority` (`P0|P1|P2`)
- `validation_status` (`PENDING|PASSED|FAILED`)
- `owner_agent_id`
- `goal`, `constraints`, `next_action`

### 3.3 ChangeRequest
- `target_node_id`, `reason`, `risk_level`, `status`
- mandatory gate to reopen `DONE -> ACTIVE`

## 4) Mandatory Policies
### 4.1 WIP Policy
- Default `WIP_LIMIT = 1`
- second active mission requires explicit override
- server-side enforcement only (UI controls are informational)

### 4.2 State Transition Rules
- `DRAFT -> ACTIVE`: allowed only if WIP permits
- `DRAFT -> FROZEN`: always allowed
- `ACTIVE -> DONE`: allowed only when validation passed
- `ACTIVE -> BLOCKED`: hard rule fail or blocker
- `DONE -> ACTIVE`: requires approved change request

## 5) Agent Handshake Contract
### A) `POST /sync/handshake/init`
Input: agent intent

Checks:
- anchor/rules load
- WIP limit
- L2 rule violation precheck

Output:
- allow: context snapshot + mission lock info
- deny: structured reason (`WIP_LIMIT_REACHED`, `L2_RULE_VIOLATION`, etc.)

### B) `POST /sync/progress`
- append progress + refresh `next_action`
- raise critical notifications for P0 blockers

### C) `POST /sync/commit`
- run validation gates
- pass -> `DONE`
- fail -> `BLOCKED` + reason

## 6) Human vs AI Surface Contract
### Human View (simple by default)
- now_problem
- now_building
- next_decision
- current mission summary + status badge

### AI View (diagnostic contract)
- focus_lock
- active mission ids
- risk clusters
- progress sync details
- traceable reason payloads

## 7) Execution Plan (safe rollout)
Phase 1:
- add logical state machine module (`core/forest_logic.py`)
- add unit tests for WIP + transitions

Phase 2:
- implement `/sync/handshake/init`, `/sync/progress`, `/sync/commit` as adapter endpoints
- keep existing `/forest/*` and `/work/*` operational

Phase 3:
- switch UI action path to `/sync/*` while maintaining backward compatibility

## 8) Non-goals in this step
- replacing all current forest/work persistence
- removing existing canopy/grove endpoints
- forced DB migration for new node tables

