# Shortcuts Bridge v0.1

## Goal
Use iOS/macOS Siri Shortcuts to call Sophia API with the shortest path.

## Shortcut Flow
1. Add action: `Get Contents of URL`
2. Method: `POST`
3. URL: `https://<your_domain>/chat/messages` (prod ingress)
  - local dev fallback: `http://127.0.0.1:8090/chat/messages`
4. Headers:
- `Authorization: Bearer <token>`
- `Content-Type: application/json`
- `X-Sophia-Source: shortcuts` (권장)
- `X-Sophia-Timestamp: <unix_ms>` (권장)
- `X-Sophia-Shortcut-Signature: <signature>`
5. Signature (v1.1 preferred):
```text
signing_string = "{method}\n{path}\n{timestamp}\n{sha256(body)}"
signature = HMAC_SHA256(signing_string, SHORTCUT_SECRET)
```
  - backward compatibility: `HMAC_SHA256(body, SHORTCUT_SECRET)`도 허용
6. Request Body (JSON, DoD-A2 minimal):
```json
{
  "message": "DoD-A2 probe",
  "mode": "chat"
}
```
  - compatibility: `role/content/context_tag` payload도 허용

## Response Parse
- Parse JSON body
- Read `messages[-1].content` (role=`sophia`) and display/speak
- Optional evidence: `messages[-1].meta.generation` and `messages[-1].meta.ethics`

## Notes
- If your deployment expects `role/content/context_tag`, convert body before POST.
- Keep token in secure Shortcut variable/keychain if available.
- `provider=apple_shortcuts`는 서명 검증 성공 시에만 부여됨.
- 상태 플래그: `SOPHIA_SHORTCUTS_STATUS=UNVERIFIED|VERIFIED`
