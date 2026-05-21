# Portfolio marketing segment

Automation: `foundry-portfolio-marketing-daily`
Time: 2026-05-21 12:05 PT

## Completed

- Regenerated `marketing/daily-portfolio-social-queue.json` from the current active business index.
- Queued 10 social ledger rows for the split X/LinkedIn publishers across 5 active businesses: Agentic Evidence, Bring Your AI, AI Dev Board, Not Human Search, and 8bitconcepts.
- Geo Agent was excluded because the current business index says `Do not market`.
- Ran the 8bit PNW follow-up sender in dry-run mode with live Resend status checks: 23 candidates checked, 0 eligible follow-ups, 0 sends.
- Fixed `marketing/pnw-smb-targets.csv` so Miller's Heating & Air parses correctly.
- Added Miller's Heating & Air to `marketing/pnw-enrichment-queue.json` as a blocked role-based address.
- Re-ran `tools/verify-pnw-outreach-queue.py`: 31 targets, 0 pending sendable, 7 unsent role-based blocked, 14 LinkedIn/un-enriched.

## Agentic Discovery

- Verified the active portfolio agent/commerce/catalog surfaces return 200 JSON for:
  - Bring Your AI
  - Agentic Evidence
  - AI Dev Board
  - Not Human Search
  - 8bitconcepts
- Submitted `https://bringyour.ai/codex-import-checklist` to Not Human Search: HTTP 201.
- Stopped the cross-business NHS proof-route batch after the public submit endpoint returned HTTP 429 for the remaining 6 URLs.

## Blockers

- LinkedIn publisher remains blocked on signed-out/stale browser state from the prior publisher run; this segment did not use browser recovery.
- X publisher is throttled by the 6-hour cap after the 16:54 UTC post.
- Reddit API credentials are missing; no Reddit live action from the recurring worker.

## Channel Specialist Closeout

- X: No scoped memory update needed.
- LinkedIn: No scoped memory update needed.
- Reddit: No scoped memory update needed.
- HN: No scoped memory update needed.
- Social editor: No scoped memory update needed.
