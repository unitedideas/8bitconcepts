# Portfolio marketing segment 2026-05-24 05:00 PT

Automation: `foundry-portfolio-marketing-daily`

Actions:

- Repaired the Miller's Heating & Air CSV row by quoting `Owner (family, since 1947)`.
- Added Miller's Heating & Air to `marketing/pnw-enrichment-queue.json` as `role_based_email`; `info@millersheating.com` remains blocked from recurring sends.
- Re-ran `python3 tools/verify-pnw-outreach-queue.py`: 31 targets, 0 pending sendable, 7 unsent role-based blocked, 14 LinkedIn-only or unenriched.
- Re-ran `python3 tools/followup.py --dry-run --limit 5`: 23 candidates checked, 0 eligible sends, 0 API failures.

Blockers:

- No safe PNW email sends. Remaining email-ready records need personal-contact enrichment.
- No automated public social posting from this worker; X/LinkedIn publishers are outside posting hours and browser-backed posting is forbidden for this recurring segment.

Scoped specialist closeout:

- X operator: No scoped memory update needed.
- LinkedIn operator: No scoped memory update needed.
- Reddit operator: No scoped memory update needed.
- HN operator: No scoped memory update needed.
- Social editor: No scoped memory update needed.
