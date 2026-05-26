# PNW SMB outreach refresh

Automation: `foundry-portfolio-marketing-daily`
Run time: 2026-05-26 13:30 PT

Actions:

- Ran `python3 tools/verify-pnw-outreach-queue.py`.
- Fixed the Miller's Heating & Air CSV quoting issue.
- Added Miller's Heating & Air to `marketing/pnw-enrichment-queue.json` as a role-based email blocker.
- Re-ran the verifier successfully.

Verifier result:

```json
{"linkedin_or_unenriched": 14, "pending_sendable": 0, "targets": 31, "unsent_role_based_blocked": 7}
```

Follow-up status:

- `tools/followup.py` already ran today at 2026-05-26T17:15Z.
- Eligible follow-ups after Resend probe: 0.
- Sent follow-ups in this segment: 0.

Call queue:

- Public main-line call queue is present at `marketing/pnw-call-queue.csv`.
- This recurring worker did not call because it has no phone tool and must not fake call outcomes.

Weighted touch: 1 point for queue repair/enrichment blocker, 1 point for verified PNW outreach status.
