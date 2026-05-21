# Portfolio marketing segment - 2026-05-21 05:00 PT

Automation: `foundry-portfolio-marketing-daily`

## Completed

- Regenerated `marketing/daily-portfolio-social-queue.json` for 2026-05-21.
- Updated `marketing/social-post-ledger.json` with queued X/LinkedIn candidates for the five active businesses in `systems/foundry-business-index.md`.
- Kept Geo Agent out of the social queue because the business index says `Do not market`.
- Verified PNW outreach queue health with `tools/verify-pnw-outreach-queue.py`.
- Refreshed PNW status and follow-up eligibility with `marketing/pnw-outreach.py`.

## PNW status

- Total targets: 31.
- Already sent: 10.
- Pending sendable: 0.
- Unsent role-based blocked: 7.
- LinkedIn-only or unenriched: 14.
- Follow-ups due in the 96-hour window: 0.

## Route checks

- `https://8bitconcepts.com/work-with-us.html` returned HTTP 200.
- `https://8bitconcepts.com/diagnostic.html` returned HTTP 200.

## Blockers

- No safe 8bit email sends or follow-ups were due.
- Public business main-line calls remain in `marketing/pnw-call-queue.csv`, but this launchd worker has no phone/call tool.
- X and LinkedIn public posting remains delegated to the split publishers; this segment only queued candidates.

## Channel specialist closeout

- X: `agent-x-operator` expertise read; no scoped memory update needed.
- LinkedIn: `agent-linkedin-operator` expertise read; no scoped memory update needed.
- Reddit: `agent-reddit-operator` expertise read; no scoped memory update needed.
- Social editor: `agent-social-editor` expertise and Shane voice read; no scoped memory update needed.
