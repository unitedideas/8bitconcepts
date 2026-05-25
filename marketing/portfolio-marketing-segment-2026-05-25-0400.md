# 8bitconcepts portfolio segment: PNW queue repair and coverage check

Automation: `foundry-portfolio-marketing-daily`
Time: 2026-05-25 04:00 PDT

Actions:

- Repaired `marketing/pnw-smb-targets.csv` so Miller's Heating & Air has a quoted role field.
- Added Miller's Heating & Air to `marketing/pnw-enrichment-queue.json` as `role_based_email`; `info@millersheating.com` remains blocked from recurring sends until a direct personal business email is verified.
- Re-ran `python3 tools/verify-pnw-outreach-queue.py`: `targets=31`, `pending_sendable=0`, `unsent_role_based_blocked=7`, `linkedin_or_unenriched=14`.
- Re-ran `python3 marketing/pnw-outreach.py status`: 10 already sent, 4 sendable total, 0 pending sendable.
- Re-ran `python3 marketing/pnw-outreach.py followup --hours 96 --limit 10`: no follow-ups due.
- Re-ran editorial follow-up dry-run: 23 candidates checked, 0 eligible after Resend status review, 0 sent.
- Rebuilt the portfolio social queue with `python3 tools/generate-portfolio-social-queue.py`; it was already current, so no queue diff was produced.
- Verified 7 live 8bit conversion and agent-discovery routes with HTTP 200:
  - `https://8bitconcepts.com/`
  - `https://8bitconcepts.com/work-with-us.html`
  - `https://8bitconcepts.com/diagnostic.html`
  - `https://8bitconcepts.com/llms.txt`
  - `https://8bitconcepts.com/.well-known/agent.json`
  - `https://8bitconcepts.com/.well-known/commerce.json`
  - `https://8bitconcepts.com/api/v1/catalog`

Counting basis:

- Raw touches: 12.
- Weighted points: 12.
- No email was sent; no safe due follow-up or pending sendable PNW recipient exists.
