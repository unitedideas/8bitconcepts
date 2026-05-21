# PNW SMB outreach check - 2026-05-21 04:00 PT

Automation: `foundry-portfolio-marketing-daily`

## Status

- Repaired `Miller's Heating & Air` CSV parsing by quoting the role field `Owner (family, since 1947)`.
- Added `Miller's Heating & Air` to `marketing/pnw-enrichment-queue.json` as `role_based_email`.
- Verification now passes:
  - `python3 tools/verify-pnw-outreach-queue.py`
  - result: `{"linkedin_or_unenriched": 14, "pending_sendable": 0, "targets": 31, "unsent_role_based_blocked": 7}`
- PNW status:
  - total targets: 31
  - already sent: 10
  - sendable targets: 4
  - pending sendable: 0
  - blocked or LinkedIn-only: 27
- Follow-up check:
  - `python3 marketing/pnw-outreach.py followup --hours 96 --limit 5`
  - result: no follow-ups due.

## Blockers

- No safe email sends are due because all remaining sendable records are already sent, suppressed, bounced, or role-based pending enrichment.
- Public business main-line calls remain due during business hours, but this launchd worker has no phone/call tool. Call queue remains `marketing/pnw-call-queue.csv`.
