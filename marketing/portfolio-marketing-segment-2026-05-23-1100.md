# Portfolio marketing segment - 2026-05-23 11:00 PT

Automation: `foundry-portfolio-marketing-daily`

## Completed

- Submitted 39 8bitconcepts local/research URLs to IndexNow: HTTP 200.
- Ran PNW outreach queue verifier: blocked on malformed CSV row for Miller's Heating & Air. The row has extra columns and a malformed email field (`since 1947)`), so no new SMB outreach was sent.
- Ran 8bit editorial follow-up dry run: 23 candidates checked, 0 eligible sends. Suppressed and bounced recipients were skipped.
- Verified 8bit agent-discovery surfaces through the portfolio agent-surface smoke: `/llms.txt`, `/llm.txt`, `/.well-known/llms.txt`, `/.well-known/llm.txt`, `/.well-known/agent.json`, `/.well-known/commerce.json`, and `/api/v1/catalog` all returned HTTP 200.

## Social queue

X/LinkedIn specialist read the scoped operator expertise and checked the portfolio queue/ledger. Queue drain should remain with `8bit-x-agent-publisher` and `8bit-linkedin-agent-publisher`; the queue has duplicate-marked portfolio candidates and the ledger records prior X/LinkedIn browser/API blockers.

## Blockers

- PNW SMB live outreach remains blocked on `marketing/pnw-smb-targets.csv` row repair.
- LinkedIn and X live posting were not attempted from this recurring worker; browser/Computer Use is forbidden here and the split publishers own the live posting path.
