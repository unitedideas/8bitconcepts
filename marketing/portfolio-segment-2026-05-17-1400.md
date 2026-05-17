# Portfolio marketing segment - 2026-05-17 14:00 PT

Automation: `foundry-portfolio-marketing-daily`

## Actions

- Regenerated `marketing/daily-portfolio-social-queue.json` for 2026-05-17 and refreshed queued social ledger rows for the split X/LinkedIn publishers.
- Preserved already-posted X/LinkedIn ledger records from earlier 2026-05-17 publisher runs.
- Fixed the malformed Miller's Heating & Air CSV row by quoting the role field containing a comma.
- Added Miller's Heating & Air to `marketing/pnw-enrichment-queue.json` as `role_based_email`.
- Re-ran `tools/verify-pnw-outreach-queue.py`.
- Re-ran `marketing/pnw-outreach.py status`.
- Re-ran `marketing/pnw-outreach.py followup --hours 96`.
- Submitted the 8bitconcepts 39-url IndexNow batch; IndexNow returned HTTP 200.

## Results

- Queue validator: 31 targets, 0 pending sendable, 7 unsent role-based records blocked for enrichment, 14 LinkedIn-only or unenriched.
- Outreach status: 10 already sent, 4 sendable total, 0 pending sendable, 27 blocked or LinkedIn-only.
- Follow-ups: no follow-ups due in the 96-hour window.
- Social queue: 10 portfolio X/LinkedIn candidate rows remain queued for the existing split publishers.

## Blockers

- Remaining PNW SMB email work needs personal/direct business email enrichment before more automated sends. Role-based addresses stay blocked.
- No X/LinkedIn public posts were attempted from this segment; the split publishers own draining queued posts.

## Touch accounting

- Raw touches completed: 54.
- Weighted points: 92.
