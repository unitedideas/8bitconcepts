# Portfolio marketing segment 2026-05-22 18:00 PDT

Automation: `foundry-portfolio-marketing-daily`

Actions:
- Regenerated `marketing/daily-portfolio-social-queue.json` for five active business posts.
- Regenerated `marketing/daily-ai-insights-queue.json` with five queued X/LinkedIn insight items.
- `agent-social-editor` reviewed the queues; three truncated portfolio items were repaired and re-approved.
- Submitted 39 8bitconcepts consulting/local/research URLs to IndexNow: HTTP 200.
- Refreshed PNW SMB outreach status. No safe due follow-ups were available; `tools/followup.py --dry-run --limit 10` found 0 eligible after Resend status probes.
- Repaired the Miller's Heating & Air CSV row and added the role-based address to `marketing/pnw-enrichment-queue.json`.
- Verified 8bit agent/discovery routes: `/`, `/llms.txt`, `/.well-known/agent.json`, and `/.well-known/commerce.json` returned HTTP 200; `/api/v1` redirects with HTTP 301.

Count:
- Raw touches: 55.
- Weighted points: 36.

Blockers:
- 8bit PNW email queue has 0 pending sendable records; 7 unsent role-based records are blocked for personal-email enrichment and 14 records are LinkedIn-only or unenriched.
- X/LinkedIn live posting was not attempted in this recurring segment because publishers are split into `8bit-x-agent-publisher` and `8bit-linkedin-agent-publisher`; the queue is ready for those workers.

Channel specialist closeout:
- `agent-social-editor`: queue approved after repair.
- No scoped memory update needed for `x-operator`, `linkedin-operator`, `reddit-operator`, `hn-operator`, or `social-editor`.
