# PNW SMB outreach maintenance - 15:20 segment

Automation: `foundry-portfolio-marketing-daily`

Completed:
- Repaired malformed `pnw-smb-targets.csv` row for Miller's Heating & Air by quoting the role field containing a comma.
- Added Miller's Heating & Air to `pnw-enrichment-queue.json` as `role_based_email`.
- Re-ran `tools/verify-pnw-outreach-queue.py`: 31 targets, 0 pending sendable, 7 unsent role-based records blocked for enrichment, 14 LinkedIn-only or unenriched.
- Re-ran `marketing/pnw-outreach.py status`: 10 already sent, 4 sendable total, 0 pending sendable, 27 blocked or LinkedIn-only.
- Re-ran `marketing/pnw-outreach.py followup --hours 96`: no due follow-ups.

No email was sent in this segment.
