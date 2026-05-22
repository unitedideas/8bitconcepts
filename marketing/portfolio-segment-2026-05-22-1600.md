# 8bit portfolio marketing segment - 2026-05-22 16:00 PDT

Automation: `foundry-portfolio-marketing-daily`

Completed:
- Regenerated `marketing/daily-portfolio-social-queue.json` for 2026-05-22.
- Regenerated `marketing/daily-ai-insights.md` and `marketing/daily-ai-insights-queue.json` for 2026-05-22.
- Added 10 daily-insight X/LinkedIn ledger rows for the split publishers.
- Preserved the already-posted BYA X ledger row at `https://x.com/8BitConcepts/status/2057949302698430783`.
- Submitted 39 local/research/consulting URLs through `tools/submit-indexnow.py`; IndexNow returned HTTP 200.
- Repaired the PNW SMB enrichment blocker for Miller's Heating & Air and reran the outreach guard.

PNW outreach status:
- Targets: 31
- Already sent: 10
- Pending sendable: 0
- Unsent role-based blocked: 7
- LinkedIn or unenriched: 14
- Safe follow-ups due: 0

Portfolio checks:
- `foundry-agent-surface-smoke` passed for Agentic Evidence, Bring Your AI, AI Dev Board, Not Human Search, and 8bitconcepts agent surfaces.
- `foundry-agentic-seller-probe --dogfood --markdown` returned certified scores for all dogfood sellers; active sellers in this run were BYA 100, Agentic Evidence 100, 8bit 95, AI Dev Board 95, and Not Human Search 95.

Blocked:
- `https://agentic-evidence.fly.dev/health` and `/hatchways` returned HTTP 404 from Fly. Record as conversion-route drift for the Agentic Evidence business agent.
- No live X/LinkedIn post in this segment. Split publishers own live posting and require account identity verification before public action.
- Reddit API credentials are still missing; no Reddit public action from this recurring worker.

No scoped memory update needed for x-operator, linkedin-operator, reddit-operator, hn-operator, or social-editor.
