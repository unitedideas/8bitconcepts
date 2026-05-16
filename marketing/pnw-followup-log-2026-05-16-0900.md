# PNW SMB outreach maintenance - 09:00 segment

Automation: `foundry-portfolio-marketing-daily`

Timestamp: 2026-05-16T16:00Z

Completed:

- Repaired malformed `marketing/pnw-smb-targets.csv` row for Miller's Heating & Air by quoting the role field containing a comma.
- Added Miller's Heating & Air to `marketing/pnw-enrichment-queue.json` as `role_based_email`.
- Re-ran `tools/verify-pnw-outreach-queue.py`: 31 targets, 0 pending sendable, 7 unsent role-based records blocked for enrichment, 14 LinkedIn-only or unenriched.
- Re-ran `marketing/pnw-outreach.py status`: 10 already sent, 4 sendable total, 0 pending sendable, 27 blocked or LinkedIn-only.
- Re-ran `marketing/pnw-outreach.py followup --hours 96`: no due follow-ups.
- Re-ran editorial `tools/followup.py --limit 3`: 23 candidates probed through Resend, 0 eligible, 0 sent, 0 API failures.

No email was sent. The remaining PNW gap is enrichment, not delivery.
