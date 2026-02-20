# AI Self-Ethics Protocol for Sophia (SSOT v1.0)

## Purpose
All Sophia reply/action/commit paths must pass ethical structure checks.
This protocol evaluates structural safety only, not moral value judgment.

## Fixed Outcomes
`EthicsOutcome = ALLOW | ADJUST | PENDING | BLOCK | FIX`

- Internal checks (仁義禮智) are implementation detail.
- External SSOT is the 5 outcomes only.

## Mandatory Gate Positions
1. `pre_output_gate`: immediately before user-visible output
2. `pre_commit_gate`: immediately before DB/ledger/audit commit

### Output Restriction
- `FIX` is forbidden at `pre_output_gate`.
- `pre_output_gate` must converge to `ALLOW|ADJUST|PENDING|BLOCK` only.

## Mixed Gate Rule
- 仁/禮 => prefer `ADJUST`
- 義/智 => prefer `PENDING` or `BLOCK`
- 信 => `FIX` only, and only in `pre_commit_gate`

## Yi(義) v1 Scope
- User rule conflicts
- Bit validator violations
- SSOT/commit policy violations

## Zhi(智) Rule
If uncertain, no speculative answer.
Outcome must be `PENDING` with one of:
- `required_inputs[]`
- `next_action` verification route

## FIX != CANON
- `FIX` means commit packet creation and audit eligibility only.
- Canon/SSOT promotion must be separate review flow.
- `ssot.promote()` auto-call is forbidden.
- Ethics gate path must not import promotion module.

## commit.allowed Ownership
`commit.allowed` can be true only by user approval or higher policy layer.
Ethics gate and model output cannot self-upgrade this flag.

## CommitMeta v1.0
Required fields:
- `event_id`
- `timestamp`
- `subject`
- `source`
- `facet`
- `refs`
- `hash`
- `policy_version`
- `redaction`
- `review`

## Operational Limits
- `ADJUST_MAX_ITER = 2`
- `PENDING_QUESTION_MAX = 3`
- session `FIX` rate limit configurable
- high-risk actions default `PENDING/BLOCK` (no direct `ALLOW`)
