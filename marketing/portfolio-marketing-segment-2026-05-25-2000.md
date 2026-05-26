# Portfolio marketing segment - 2026-05-25 20:00 PT

Automation: `foundry-portfolio-marketing-daily`

## Completed

- Regenerated `marketing/daily-portfolio-social-queue.json` for the current active portfolio.
- Updated `marketing/social-post-ledger.json` with duplicate-gated queued X/LinkedIn candidates for the split publishers.
- Repaired `tools/generate-portfolio-social-queue.py` so long business-index cells do not create half-sentence post candidates.
- Validated PNW SMB outreach state with `tools/verify-pnw-outreach-queue.py`: `targets=31`, `pending_sendable=0`, `unsent_role_based_blocked=7`, `linkedin_or_unenriched=14`.
- Checked the 96-hour PNW follow-up window: no safe follow-ups due.
- Confirmed `marketing/pnw-enrichment-queue.json` includes Miller's Heating & Air as a role-based-address blocker.
- Ran `python3 -m py_compile tools/generate-portfolio-social-queue.py marketing/pnw-outreach.py marketing/_outreach_guards.py`.

## Portfolio Coverage

- Agentic Evidence, Bring Your AI, AI Dev Board, Not Human Search, and 8bitconcepts passed the sync-state agent-surface smoke for `/llms.txt`, `/llm.txt`, `/.well-known/llms.txt`, `/.well-known/llm.txt`, `/.well-known/agent.json`, `/.well-known/commerce.json`, and `/api/v1/catalog`.
- Geo Agent remained excluded from promotion because `systems/foundry-business-index.md` marks it `Do not market`.

## Blockers

- No PNW SMB email was sent: remaining unsent email addresses are role-based or need enrichment.
- No PNW calls were attempted: no call-queue row has source URL plus DNC/consent notes.
- X/LinkedIn live posts were left to `8bit-x-agent-publisher` and `8bit-linkedin-agent-publisher`; this recurring portfolio worker did not use browser or Computer Use.

## Counts

- Raw touches: 18.
- Weighted touch points: 18.

No scoped memory update needed for X, LinkedIn, Reddit, or social-editor.
