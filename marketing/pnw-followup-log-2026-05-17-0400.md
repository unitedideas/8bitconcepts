# PNW SMB outreach maintenance - 04:00 segment

Automation: `foundry-portfolio-marketing-daily`
Timestamp: 2026-05-17T11:04:00Z

## Actions

- Repaired the malformed Miller's Heating & Air CSV row by quoting the role field containing a comma.
- Added Miller's Heating & Air to `marketing/pnw-enrichment-queue.json` as `role_based_email`.
- Re-ran `tools/verify-pnw-outreach-queue.py`.
- Re-ran `marketing/pnw-outreach.py status`.
- Re-ran `marketing/pnw-outreach.py followup --hours 96`.
- Submitted the 8bitconcepts URL batch through `tools/submit-indexnow.py`.

## Results

- Queue validator: 31 targets, 0 pending sendable, 7 unsent role-based records blocked for enrichment, 14 LinkedIn-only or unenriched.
- Outreach status: 10 already sent, 4 sendable total, 0 pending sendable, 27 blocked or LinkedIn-only.
- Follow-ups: no follow-ups due in the 96-hour window.
- IndexNow: HTTP 200 for 39 URLs.

## Blockers

- Remaining PNW SMB email work needs personal/direct business email enrichment before more automated sends. Role-based addresses stay blocked.
- Not Human Search submit returned HTTP 429 for the 8bit URL batch in this segment.
