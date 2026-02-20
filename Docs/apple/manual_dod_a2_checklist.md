# Manual DoD-A2 Checklist (Device)

Purpose: verify real iOS/macOS Shortcuts run for Apple path.

## Preconditions
- Sophia API server running
- `SHORTCUT_SECRET` configured
- `SOPHIA_SHORTCUTS_STATUS=UNVERIFIED` (before test)
- Shortcut configured per `shortcuts_bridge_v0_1.md`

## Steps
1. Execute Shortcut on real device (iOS/macOS).
2. Capture Shortcuts success screen (1 image).
3. Capture server log lines (same request window):
- GEN line with `trace_id`
- `CTX_SAVED` or `ETHICS_FIX_COMMITTED`
4. Capture response JSON excerpt including:
- `meta.generation`
- `meta.ethics`
5. Confirm evidence correlation by same `trace_id` (or request_id if available).

## Pass Criteria
- All captures exist and correlate.
- `meta.generation.provider=apple_shortcuts`
- `meta.generation.route=proxy`
- `meta.ethics.outcome` present.

## Failure Classification (single root-cause)
- NETWORK
- AUTH
- CORS/HTTPS
- ROUTE
- GATE

## Post-Verification
- Set status to `VERIFIED` (`SOPHIA_SHORTCUTS_STATUS=VERIFIED`) only after pass.
