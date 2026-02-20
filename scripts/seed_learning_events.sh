#!/usr/bin/env bash
set -euo pipefail

API_BASE="${SOPHIA_API_BASE:-http://127.0.0.1:8090}"
CHAT_ENDPOINT="${API_BASE%/}/chat/messages"
DB_PATH="${SOPHIA_DB_PATH:-/Users/dragonpd/Sophia/sophia.db}"

EVENTS=(
  "UNCONSCIOUS_HIT"
  "UNCONSCIOUS_PATTERN_SEEN"
  "TERM_MAPPING"
  "TOPIC_SEEN"
  "USER_PREFERENCE"
)

count_event() {
  local event_name="$1"
  sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM mind_working_logs WHERE event_type = '${event_name}';"
}

post_chat() {
  local label="$1"
  local text="$2"
  local body_file
  body_file="$(mktemp)"
  local payload
  payload=$(cat <<EOF
{"role":"user","content":"${text}","context_tag":"chat"}
EOF
)
  local status
  status="$(curl -sS -o "$body_file" -w "%{http_code}" -X POST "$CHAT_ENDPOINT" -H "Content-Type: application/json" --data "$payload")"
  if [[ "$status" != "200" ]]; then
    echo "[seed] ${label} failed (HTTP ${status})"
    cat "$body_file"
    rm -f "$body_file"
    exit 1
  fi
  echo "[seed] ${label} ok"
  rm -f "$body_file"
}

if [[ ! -f "$DB_PATH" ]]; then
  echo "DB file not found: $DB_PATH"
  exit 1
fi

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "sqlite3 command is required but not found."
  exit 1
fi

before_unconscious_hit="$(count_event "UNCONSCIOUS_HIT")"
before_unconscious_pattern_seen="$(count_event "UNCONSCIOUS_PATTERN_SEEN")"
before_term_mapping="$(count_event "TERM_MAPPING")"
before_topic_seen="$(count_event "TOPIC_SEEN")"
before_user_preference="$(count_event "USER_PREFERENCE")"

post_chat "PING_OK" "ping"
post_chat "SMOKE_OK" "smoke test"
post_chat "GREET" "안녕"

# Clarify seed: create one pending CLARIFY so the next sentence can be learned as TERM_MAPPING.
post_chat "TERM_MAPPING_PREP" "이거"

post_chat "TERM_MAPPING" "앞으로 작업이라고 하면 에디터 분석을 의미해"
post_chat "USER_PREFERENCE" "앞으로는 답변을 짧게 해줘"

# Preference seed: current detector keys on explicit tone/preference wording.
post_chat "USER_PREFERENCE_HINT" "말투는 짧고 간결한 답변을 선호해"

post_chat "TOPIC_SEEN" "에피도라 검증엔진 얘기 다시 해보자"

echo
echo "[Learning Seed Result]"
after_unconscious_hit="$(count_event "UNCONSCIOUS_HIT")"
after_unconscious_pattern_seen="$(count_event "UNCONSCIOUS_PATTERN_SEEN")"
after_term_mapping="$(count_event "TERM_MAPPING")"
after_topic_seen="$(count_event "TOPIC_SEEN")"
after_user_preference="$(count_event "USER_PREFERENCE")"

printf "UNCONSCIOUS_HIT: %s (delta %+d)\n" "$after_unconscious_hit" "$((after_unconscious_hit - before_unconscious_hit))"
printf "UNCONSCIOUS_PATTERN_SEEN: %s (delta %+d)\n" "$after_unconscious_pattern_seen" "$((after_unconscious_pattern_seen - before_unconscious_pattern_seen))"
printf "TERM_MAPPING: %s (delta %+d)\n" "$after_term_mapping" "$((after_term_mapping - before_term_mapping))"
printf "TOPIC_SEEN: %s (delta %+d)\n" "$after_topic_seen" "$((after_topic_seen - before_topic_seen))"
printf "USER_PREFERENCE: %s (delta %+d)\n" "$after_user_preference" "$((after_user_preference - before_user_preference))"
