# 8bitconcepts portfolio segment - 2026-05-23 17:30 PT

Automation: `foundry-portfolio-marketing-daily`

## Completed touches

- Refreshed PNW SMB outreach status:
  - 31 total targets
  - 10 already sent
  - 4 sendable targets
  - 27 blocked or LinkedIn-only
  - 0 pending sendable
- Checked PNW due follow-ups at the 96-hour window: 0 due.
- Checked editorial/direct-outreach follow-up path: blocked by malformed historical sent rows missing `email`; no send attempted.
- Verified consulting conversion routes:
  - `https://8bitconcepts.com/work-with-us.html` HTTP 200
  - `https://8bitconcepts.com/diagnostic.html` HTTP 200

Raw touches: 7.
Weighted points: 9.

## Blockers

- PNW queue has no unsent sendable records left without enrichment.
- `marketing/outreach.py status` and `marketing/outreach.py follow-up --dry-run` fail on historical rows missing `email`.
- X/LinkedIn API credentials missing; recurring browser posting is forbidden in this worker.

## Next actions

1. Repair `marketing/outreach.py` to tolerate legacy rows missing `email`, then rerun dry-run follow-up.
2. Enrich blocked PNW rows into personal email or public-main-line call records.
3. During business hours, call only public business main lines already present in `marketing/pnw-call-queue.csv` after source/DNC notes are confirmed.
