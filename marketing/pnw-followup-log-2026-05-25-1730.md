# 2026-05-25 17:30 PT PNW outreach refresh

Automation: `foundry-portfolio-marketing-daily`

## Completed

- Repaired CSV quoting for `Miller's Heating & Air` in `marketing/pnw-smb-targets.csv`.
- Added the exact role-based blocker for `Miller's Heating & Air <info@millersheating.com>` to `marketing/pnw-enrichment-queue.json`.
- Re-ran `python3 tools/verify-pnw-outreach-queue.py`.
- Result: `targets=31`, `pending_sendable=0`, `unsent_role_based_blocked=7`, `linkedin_or_unenriched=14`.
- Refreshed due follow-up eligibility with `python3 tools/followup.py --dry-run --limit 10`.
- Result: `eligible=0`, `sent=0`, `failed=0`, `api_fail=0`.
- Re-ran `python3 tools/submit-indexnow.py`.
- Result: 39 8bitconcepts consulting/local/research URLs submitted to IndexNow, HTTP 200.

## Blockers

- No safe PNW SMB email sends are due. Remaining unsent email addresses are role-based or need enrichment.
- Calls were not attempted in this segment because no call-queue row was advanced with source URL plus DNC/consent notes.
- X/LinkedIn posting remains with the split publishers; this portfolio worker did not use browser/Computer Use.

## Counting basis

- Raw completed touches: 42.
- Weighted touch points: 84.

## Next highest-impact 8bc actions

1. Enrich the 7 role-based PNW targets with verified personal business emails before any further email send.
2. Convert the 14 LinkedIn/un-enriched PNW rows into sourced call-queue or direct-email records.
3. Add Cal.com booking once the account exists, then swap the current intro-call CTA across `work-with-us` and local pages.
