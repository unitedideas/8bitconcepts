# Portfolio marketing segment - 2026-05-21 23:00 PT

Automation: `foundry-portfolio-marketing-daily`

## Completed

- Submitted 39 8bit local/research URLs to IndexNow: HTTP 200.
- Probed PNW SMB follow-ups through Resend status API: 23 candidates, 0 eligible after bounce/suppression/dedupe checks, 0 sent.
- Repaired PNW target CSV parsing for Miller's Heating & Air by quoting the comma-bearing role field.
- Added Miller's Heating & Air to the enrichment blocker queue instead of sending to a role-based `info@` inbox.
- Verified PNW outreach queue: 31 targets, `pending_sendable=0`, `unsent_role_based_blocked=7`, `linkedin_or_unenriched=14`.
- Verified conversion routes:
  - `OPTIONS https://aidevboard.com/api/v1/lead`: HTTP 200.
  - `https://8bitconcepts.com/diagnostic.html`: HTTP 200.

## Blockers

- No public business calls at 23:00 PT; outside normal call hours.
- No new PNW email sends; remaining addresses are role-based, LinkedIn-only, or enrichment-blocked.
- Portfolio social queue was refreshed, then not committed or drained because the generated copy was not social-editor approved and live X/LinkedIn publishing belongs to the split channel publishers.
