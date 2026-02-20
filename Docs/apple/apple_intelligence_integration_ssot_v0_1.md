# Apple Intelligence Integration SSOT v0.1

## Decision
Chosen definition of "Apple Intelligence connected":
1) **Shortcuts path** (Siri/Shortcuts -> Sophia HTTP API)

Scope for v0.1 is only the Shortcuts path.
App Intents and Writing Tools are deferred.

## DoD (2-Stage)
### DoD-A1 (SIM)
Simulated request must satisfy:
1. Request enters `/chat/messages` with Shortcuts-identifying headers/user-agent.
2. Runtime logs include one GEN line with `trace_id`.
3. Response includes:
- `meta.generation.provider/model/route/capabilities`
- `meta.ethics.outcome/reason_codes`

### DoD-A2 (DEVICE)
Real iOS/macOS Shortcuts execution must satisfy:
0. Request body can be minimal:
   - `{"message":"DoD-A2 probe","mode":"chat"}`
1. Shortcuts success screen capture (1 image).
2. Server log capture (2 lines):
- GEN line (`trace_id` 포함)
- `CTX_SAVED` or `ETHICS_FIX_COMMITTED`
3. Response JSON capture:
- `meta.generation`
- `meta.ethics`
4. Evidence must correlate by same `trace_id` (or `request_id` if introduced later).

## Connection Status
- `UNVERIFIED`: DoD-A1 only
- `VERIFIED`: DoD-A2 passed

## Implementation Path
- Detection layer: `/Users/dragonpd/Sophia/core/llm/generation_meta.py`
- Injection points:
  - `/Users/dragonpd/Sophia/api/chat_router.py`
  - `/Users/dragonpd/Sophia/api/work_router.py`
  - `/Users/dragonpd/Sophia/api/ai_router.py`
- Ethics enforcement:
  - `/Users/dragonpd/Sophia/core/ethics/gate.py`

## Signature Policy (v1.1)
- Header:
  - `X-Sophia-Timestamp: <unix_ms>` (권장)
  - `X-Sophia-Shortcut-Signature`
- Preferred signature:
  - `HMAC_SHA256("{method}\n{path}\n{timestamp}\n{sha256(body)}", SHORTCUT_SECRET)`
- Backward compatibility:
  - `HMAC_SHA256(body, SHORTCUT_SECRET)` 허용
- Only signature-verified Shortcuts requests can set:
  - `provider=apple_shortcuts`
  - `route=proxy`
- Signature failure path:
  - `provider=unknown`
  - `route=proxy`
  - ethics outcome should converge to `PENDING` with `CAPABILITY_MISMATCH`

## Risks
- NETWORK: iOS device cannot reach host/port
- AUTH: bearer token mismatch
- CORS/HTTPS: iOS transport/security policy blocks request
- ROUTE: user-agent/header not passed, route falls back
- GATE: missing generation meta or capability mismatch -> PENDING

## Out of Scope (v0.1)
- Native App Intents
- Writing Tools extension pipeline
- dual-run multi-model verification

## Next Trigger
Move to App Intents only after Track A DoD evidence is collected from real iOS/macOS Shortcuts execution.
