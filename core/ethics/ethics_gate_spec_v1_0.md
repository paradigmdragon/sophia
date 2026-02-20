# Ethics Gate Spec v1.0

## Input Contract
- `draft_text: str`
- `task: reply|action|commit`
- `mode: chat|report|instruction|json|other`
- `risk_level: none|low|med|high`
- `context_refs: str[]`
- `capabilities: object`
- `user_rules_ref: str|null`
- `commit_allowed: bool`
- `commit_allowed_by: none|user|policy`

## Output Contract
- `outcome: ALLOW|ADJUST|PENDING|BLOCK|FIX`
- `reason_codes: string[]`
- `required_inputs?: string[]`
- `next_action?: object`
- `patch?: { kind: rewrite, content: string }`
- `commit_meta?: CommitMeta`

## Hard Rules
- pre-output: no `FIX`
- pre-commit: `FIX` only if commit policy passes
- uncertainty => `PENDING`
- high-risk actions => `BLOCK` or `PENDING`

## Call Sites (Mandatory)
1) immediately before reply/action persistence (`pre_output_gate`)
2) immediately before database commit (`pre_commit_gate`)

## Fix Lock
- `FIX` only creates commit packet metadata
- Canon promotion is out-of-band and forbidden in ethics gate path
