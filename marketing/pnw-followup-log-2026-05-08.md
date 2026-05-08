# PNW SMB outreach guard repair - 2026-05-08

Automation: `business-agent-8bitconcepts`

No external email was sent in this run.

## Repair

- Restored the eight 2026-05-06 follow-up records that were removed by stale commit `bb25a2f`.
- Preserved the suppressed and bounced records as follow-up blocked.
- Changed `marketing/_outreach_guards.py` so role-based local parts are not sendable by the recurring worker.
- Added `marketing/pnw-enrichment-queue.json` for the six remaining role-based SMB records that need direct-contact enrichment before any more email sends.

## Verification

- `python3 -m py_compile marketing/pnw-outreach.py marketing/_outreach_guards.py`
- `python3 marketing/pnw-outreach.py followup --hours 96`
- `python3 marketing/pnw-outreach.py send --dry-run`

Expected result: no follow-ups due and no pending sendable targets.

## Portfolio routine repair

Automation: `foundry-portfolio-marketing-daily`

No external email was sent in this run. The sync-state lock
`public-action-locks/email-outreach/87845d241a85a2af.json` already records
the 8 follow-up sends from 2026-05-06, so resending would have duplicated
buyer touches.

## Repair

- Added a narrow `marketing/pnw-outreach.py followup --send` path for future
  safe follow-up sends through Resend.
- The new send path excludes bounced, suppressed, locally suppressed, and
  role-based addresses before any API call.
- Restored the ignored local `marketing/pnw-outreach-sent.json` follow-up
  markers from the 2026-05-06 sync-state lock message ids.

## Verification

- `python3 -m py_compile marketing/pnw-outreach.py marketing/_outreach_guards.py`
- `python3 marketing/pnw-outreach.py followup --hours 96`
- `python3 marketing/pnw-outreach.py send --dry-run`

Expected result: no follow-ups due and no pending sendable targets.
