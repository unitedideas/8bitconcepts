# 2026-05-17 portfolio segment

Automation: `foundry-portfolio-marketing-daily`

## Completed

- Submitted 39 8bitconcepts consulting/local/research URLs to IndexNow: HTTP 200.
- Repaired `marketing/pnw-smb-targets.csv` so Miller's Heating & Air parses as 11 CSV fields instead of splitting `Owner (family, since 1947)`.
- Added Miller's Heating & Air to the enrichment blocker list because `info@millersheating.com` is role-based and must not be sent by recurring outreach.
- Re-ran `python3 tools/verify-pnw-outreach-queue.py`: `targets=31`, `pending_sendable=0`, `unsent_role_based_blocked=7`, `linkedin_or_unenriched=14`.
- Verified consulting conversion routes:
  - `https://8bitconcepts.com/work-with-us.html` HTTP 200
  - `https://8bitconcepts.com/diagnostic.html` HTTP 200

## Counts

- Raw touches: 39 IndexNow URL submissions, 1 conversion/data repair, 2 route checks.
- Weighted points: 45.

## Next actions

1. Enrich the 7 role-based PNW SMB records with direct personal business emails before any new send.
2. Use the call queue only during business hours and only for public business main numbers with source notes.
3. Keep X/LinkedIn social draining through the split publisher automations; this segment did not attempt browser posting.
