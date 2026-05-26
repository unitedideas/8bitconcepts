# PNW SMB Outreach Queue Repair

Automation: `foundry-portfolio-marketing-daily`
Date: 2026-05-26 16:30 PT

Actions:

- Quoted the comma-bearing Miller's Heating & Air owner-role field in `marketing/pnw-smb-targets.csv`.
- Added Miller's Heating & Air to `marketing/pnw-enrichment-queue.json` because `info@millersheating.com` is role-based.
- Re-ran `python3 tools/verify-pnw-outreach-queue.py`.

Verification:

```json
{"linkedin_or_unenriched": 14, "pending_sendable": 0, "targets": 31, "unsent_role_based_blocked": 7}
```

Outcome:

No safe PNW SMB email send was due in this segment. The next action is personal-contact enrichment for the seven role-based blocked records.

Weighted touch: 1 for conversion/outreach queue repair and verified blocker state.
