# PNW SMB outreach check - 2026-05-18 04:00 PT

Automation: `foundry-portfolio-marketing-daily`

## Status

- Total targets: 31
- Already sent: 10
- Sendable targets: 4
- Pending sendable: 0
- Blocked or LinkedIn-only: 27
- Due follow-ups at 96 hours: 0

## Verification

`python3 tools/verify-pnw-outreach-queue.py` failed closed:

- `marketing/pnw-smb-targets.csv` line 9 has extra CSV columns.
- Miller's Heating & Air has a malformed email field: `since 1947)`.

No new outreach or follow-up was sent from this segment because the verifier failed before list expansion.

## Next actions

1. Repair the Miller's Heating & Air CSV quoting/field alignment, then rerun `python3 tools/verify-pnw-outreach-queue.py`.
2. Enrich the remaining LinkedIn-only records with named personal email routes before sending.
3. Keep follow-up sends gated by delivery status and the sync-state email lock history.
