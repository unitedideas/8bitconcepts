# Portfolio marketing segment - 2026-05-17 22:00 PDT

Automation: `foundry-portfolio-marketing-daily`

## Completed

- Repaired the Miller's Heating & Air CSV row by quoting `Owner (family, since 1947)`.
- Added Miller's Heating & Air to `marketing/pnw-enrichment-queue.json` as a role-based-email blocker.
- Re-ran `python3 tools/verify-pnw-outreach-queue.py`: `targets=31`, `pending_sendable=0`, `unsent_role_based_blocked=7`, `linkedin_or_unenriched=14`.
- Checked PNW follow-ups with a 96-hour window: no follow-ups due.
- Confirmed `python3 marketing/pnw-outreach.py send --limit 5` has no pending targets.
- Verified conversion routes: `https://8bitconcepts.com/work-with-us.html`, `https://8bitconcepts.com/diagnostic.html`, and `https://8bitconcepts.com/llms.txt` returned HTTP 200.

## Blockers

- Remaining PNW email candidates are role-based or LinkedIn-only. Next action is enrichment to direct business emails or verified non-recurring LinkedIn route.
- X/LinkedIn posting is queue-backed, but this non-desktop portfolio worker cannot verify account identity for live posts.

## Touch Accounting

- Raw touches completed: 4.
- Weighted touch points: 4.
