#!/bin/bash
set -euo pipefail

# Email domain warmup — 2-week sequence to establish sender reputation
# Usage: ./warmup-send.sh [--dry-run] [--day N]
# Scheduled via launchd: daily at 8am for 14 days

DOMAIN="${OUTREACH_DOMAIN:-8bitconcepts-outreach.com}"
SENDER_EMAIL="hello@${DOMAIN}"
RESEND_API_KEY="$(security find-generic-password -a foundry -s resend-api-key -w)"

DRY_RUN="${1:---dry-run}"
DAY="${2:-1}"

# Bounce monitors — safe inboxes used only for warmup
WARMUP_TARGETS=(
  "noreply@gmail.com"
  "noreply@outlook.com"
  "noreply@yahoo.com"
  "bounce@$DOMAIN"  # self-monitor
)

# Friendly warm prospects — existing ADB subscribers + engaged past contacts
WARM_PROSPECTS=(
  "hello@aidevboard.com"
  "shane-cheek_1pw@icloud.com"
  "support@8bitconcepts.com"
)

# Warmup schedule: days 1-7 (5/day bounce monitors), days 8-14 (10/day: 5 bounce + 5 warm)
send_warmup_batch() {
  local day=$1
  local send_count=0
  local target_count=$((day <= 7 ? 5 : 10))

  if [[ $day -le 7 ]]; then
    # Days 1–7: bounce monitors only
    for i in $(seq 0 $((target_count-1))); do
      local idx=$((i % ${#WARMUP_TARGETS[@]}))
      local to="${WARMUP_TARGETS[$idx]}"
      send_email_warmup "$to" "$day" "$send_count"
      send_count=$((send_count + 1))
    done
  else
    # Days 8–14: mix of bounce monitors + warm prospects
    for i in $(seq 0 $((target_count-1))); do
      local recipient
      if [[ $((i % 2)) -eq 0 ]]; then
        recipient="${WARMUP_TARGETS[$((i / 2 % ${#WARMUP_TARGETS[@]}))]}"
      else
        recipient="${WARM_PROSPECTS[$((i / 2 % ${#WARM_PROSPECTS[@]}))]}"
      fi
      send_email_warmup "$recipient" "$day" "$send_count"
      send_count=$((send_count + 1))
    done
  fi

  echo "Day $day: sent $send_count warmup emails"
}

send_email_warmup() {
  local to=$1
  local day=$2
  local index=$3

  local subject="Warmup test day $day [8bc outreach]"
  local body="Warmup mail $index on day $day from $SENDER_EMAIL to verify domain reputation."

  if [[ "$DRY_RUN" == "--dry-run" ]]; then
    echo "[DRY RUN] Would send to $to: $subject"
    return
  fi

  # Send via Resend API
  curl -s -X POST https://api.resend.com/emails \
    -H "Authorization: Bearer $RESEND_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
      \"from\": \"$SENDER_EMAIL\",
      \"to\": \"$to\",
      \"subject\": \"$subject\",
      \"text\": \"$body\"
    }" | jq -r '.id // .error.message' || echo "send_failed"
}

send_warmup_batch "$DAY"
