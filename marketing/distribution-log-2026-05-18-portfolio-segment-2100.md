# 8bitconcepts portfolio segment - 2026-05-18 21:00 PT

Automation: `foundry-portfolio-marketing-daily`

## Completed

- Repaired malformed PNW SMB CSV row for `Miller's Heating & Air`; the owner-role field contained an unquoted comma.
- Added `Miller's Heating & Air <info@millersheating.com>` to the enrichment blocker queue as `role_based_email`.
- Reran `tools/verify-pnw-outreach-queue.py`: 31 targets, 0 pending sendable, 7 unsent role-based blocked, 14 LinkedIn/unenriched.
- Reran `tools/followup.py --dry-run`: 23 candidates checked, 0 eligible sends, 0 API failures.
- Verified `https://8bitconcepts.com/work-with-us.html`: HTTP 200.

## Blockers

- No PNW SMB email sent: there are no safe pending sendable records and no eligible due follow-ups.
- Remaining outreach work is enrichment: role-based addresses need direct decision-maker business emails before Resend sends.

## Touch Accounting

- Raw touches: 4.
- Weighted points: 4.
