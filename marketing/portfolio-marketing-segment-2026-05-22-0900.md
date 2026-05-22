# Portfolio marketing segment - 2026-05-22 09:00 PT

Automation: `foundry-portfolio-marketing-daily`

## 8bitconcepts

- Submitted 39 local/research URLs to IndexNow; response HTTP 200.
- Regenerated `marketing/daily-portfolio-social-queue.json` and queued 10 X/LinkedIn portfolio candidates.
- Ran social-editor review on the queue. Initial review blocked three truncated candidates; repaired the queue copy and matching ledger fingerprints; second review approved.
- Repaired the Miller's Heating & Air CSV row in `marketing/pnw-smb-targets.csv`.
- Added Miller's Heating & Air to `marketing/pnw-enrichment-queue.json` as `role_based_email`, so the outreach verifier fails closed instead of sending to `info@`.
- Verified PNW outreach queue: 31 targets, 0 pending sendable, 7 role-based blocked, 14 LinkedIn/unenriched.
- Probed due editorial follow-ups in dry-run mode: 23 candidates, 0 eligible sends, 0 API failures.

## Portfolio Agent Discovery

- `foundry-agent-surface-smoke` passed for Agentic Evidence, Bring Your AI, AI Dev Board, Not Human Search, and 8bitconcepts across `/llms.txt`, aliases, `/.well-known/agent.json`, `/.well-known/commerce.json`, and `/api/v1/catalog`.
- Submitted 9 non-BYA proof/discovery URLs to Not Human Search; all returned HTTP 201:
  - `https://agentic-evidence.fly.dev/hatchways`
  - `https://agentic-evidence.fly.dev/hatchways/packet.json`
  - `https://agentic-evidence.fly.dev/github-action.yml`
  - `https://aidevboard.com/api/v1/catalog`
  - `https://aidevboard.com/.well-known/agent.json`
  - `https://nothumansearch.ai/score`
  - `https://nothumansearch.ai/.well-known/agent.json`
  - `https://8bitconcepts.com/work-with-us.html`
  - `https://8bitconcepts.com/diagnostic.html`

## Channel Boundaries

- X/LinkedIn queue only; no public post was made from this recurring worker.
- X operator closeout: No scoped memory update needed.
- LinkedIn operator closeout: No scoped memory update needed.
- Reddit operator closeout: No scoped memory update needed.
- HN operator closeout: No scoped memory update needed.
- Social editor closeout: No scoped memory update needed.
