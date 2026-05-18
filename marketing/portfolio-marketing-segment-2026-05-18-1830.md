# Portfolio marketing segment - 2026-05-18 18:30Z

Actions:
- Regenerated `marketing/daily-portfolio-social-queue.json` from the current sync-state business index.
- Queued 10 duplicate-false X/LinkedIn candidates in `marketing/social-post-ledger.json`.
- Repaired the malformed Miller's Heating & Air CSV row by quoting the role field with a comma.
- Added Miller's Heating & Air to `marketing/pnw-enrichment-queue.json` as `role_based_email`.
- Verified PNW outreach queue: 31 targets, 0 pending sendable, 7 unsent role-based records blocked for enrichment, 14 LinkedIn-only or unenriched.
- Checked PNW follow-ups with a 96-hour window: no follow-ups due.

Channel blockers:
- X: queued candidates only; live posting belongs to `8bit-x-agent-publisher`.
- LinkedIn: cadence cap active; live posting belongs to `8bit-linkedin-agent-publisher`.
- Reddit: API credentials missing and recurring browser posting is forbidden.
- HN: browser login verification required, and recurring worker cannot use browser/Computer Use.
