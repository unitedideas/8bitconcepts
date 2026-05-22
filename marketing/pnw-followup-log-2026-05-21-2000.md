# PNW SMB follow-up segment 2026-05-21 20:00 PT

Automation: `foundry-portfolio-marketing-daily`

## Results

- Fixed the Miller's Heating & Air CSV row so the email field parses correctly.
- Added Miller's Heating & Air to the enrichment blocker queue because `info@millersheating.com` is role-based and must not be sent by the recurring email path.
- `tools/verify-pnw-outreach-queue.py` passed:
  - targets: 31
  - pending_sendable: 0
  - unsent_role_based_blocked: 7
  - linkedin_or_unenriched: 14
- `marketing/pnw-outreach.py status` returned:
  - total targets: 31
  - already sent: 10
  - sendable targets: 4
  - blocked or LinkedIn-only: 27
  - pending sendable: 0
- `marketing/pnw-outreach.py followup --hours 96 --limit 10` sent 0 follow-ups; no follow-ups were due.
- 8bit IndexNow submitted 39 local/research URLs: HTTP 200.

## Blockers

- No recurring SMB email send is safe until the remaining role-based and LinkedIn-only records are enriched with direct business contacts.
- Calls are limited to public main-line call-queue work during business hours with source/DNC notes; none were placed in this segment.
