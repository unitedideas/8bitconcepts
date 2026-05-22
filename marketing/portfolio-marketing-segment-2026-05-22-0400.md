# Portfolio marketing segment - 2026-05-22 04:00 PT

Automation: `foundry-portfolio-marketing-daily`

## 8bitconcepts

- Submitted 39 local/research URLs to IndexNow: HTTP 200.
- Rebuilt `marketing/daily-portfolio-social-queue.json` for 2026-05-22 from the sync-state business index; 5 queued portfolio items, Geo Agent excluded because the current business index says not to market it.
- Updated `marketing/social-post-ledger.json` with queued fingerprints for the split X/LinkedIn publishers. Posting is left to `8bit-x-agent-publisher` and `8bit-linkedin-agent-publisher`.
- Refreshed PNW SMB outreach safety:
  - Fixed the Miller's Heating & Air CSV parse break by quoting the owner-role field.
  - Added Miller's role-based `info@` address to the enrichment blocker list.
  - `tools/verify-pnw-outreach-queue.py` is green: 31 targets, 0 pending sendable, 7 role-based blocked, 14 LinkedIn/unenriched.
- Ran 8bit editorial follow-up dry run with Resend status probes: 23 candidates, 0 eligible sends, 0 API failures. No live follow-up sent.

## Channel boundaries

- Public social copy still requires the channel publisher's account identity verification and social-editor gate before posting.
- Reddit/HN/X/LinkedIn live posting was not attempted from this recurring worker.
