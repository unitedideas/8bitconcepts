# PNW SMB outreach check - 2026-05-18 10:00 PT

Automation: `foundry-portfolio-marketing-daily`

## Status

- Total targets: 31
- Already sent: 10
- Sendable targets: 4
- Pending sendable: 0
- Blocked or LinkedIn-only: 27
- Due follow-ups at 96 hours: 0

## Repair

- Fixed Miller's Heating & Air CSV field alignment by quoting `Owner (family, since 1947)`.
- Added Miller's Heating & Air to `marketing/pnw-enrichment-queue.json` as `role_based_email`.
- Verification now passes:
  - `python3 tools/verify-pnw-outreach-queue.py`
  - result: `{"linkedin_or_unenriched": 14, "pending_sendable": 0, "targets": 31, "unsent_role_based_blocked": 7}`

## Follow-up check

- `python3 marketing/pnw-outreach.py followup --hours 96 --limit 5`
- result: no follow-ups due.

## Blockers

- Public business main-line calls are due during business hours, but this launchd worker has no phone/call tool. Call queue remains in `marketing/pnw-call-queue.csv`.
- Remaining email growth is blocked on personal-contact enrichment; role-based addresses stay blocked.
