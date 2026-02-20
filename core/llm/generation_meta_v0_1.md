# generation_meta v0.1 (SSOT)

## Purpose
`generation_meta` is mandatory evidence for provider/model/route/capability provenance.
If missing, runtime must treat response as unresolved engine state.

## Required fields
- `provider`: `ollama | openai | apple | apple_shortcuts | mock | unknown`
- `model`: string
- `route`: `local | server | os | proxy`
- `capabilities`: object
: `web_access` bool
: `file_access` bool
: `exec_access` bool
: `device_actions` bool
- `latency_ms`: integer
- `tokens_in`: integer or null
- `tokens_out`: integer or null
- `trace_id`: string
- `created_at`: ISO8601 string

## Optional fields (v1.1)
- `shortcuts_request`: bool
- `shortcuts_signature_valid`: bool | null
- `shortcuts_status`: `UNVERIFIED | VERIFIED`
- `integration.apple.shortcuts`: `UNVERIFIED | VERIFIED`

## Hard rule
- If `generation_meta` is missing, force `reason_code=NO_PROVIDER_META`.
- Missing meta must not pass as `ALLOW`.

## Compatibility
- New optional fields may be added.
- Existing fields must not be removed or semantically redefined.
