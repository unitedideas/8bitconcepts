# 8bitconcepts portfolio segment: queue repair and route coverage

Automation: `foundry-portfolio-marketing-daily`
Run window: 2026-05-17 19:00 PDT

Actions:

- Fixed malformed CSV quoting in `marketing/pnw-smb-targets.csv` for Miller's Heating & Air.
- Added Miller's Heating & Air to `marketing/pnw-enrichment-queue.json` as `role_based_email`.
- Re-ran `python3 tools/verify-pnw-outreach-queue.py`: `targets=31`, `pending_sendable=0`, `unsent_role_based_blocked=7`, `linkedin_or_unenriched=14`.
- Re-ran `python3 marketing/pnw-outreach.py status`: 10 sent, 0 pending sendable, 27 blocked or LinkedIn-only.
- Re-ran `python3 marketing/pnw-outreach.py followup --hours 96`: no follow-ups due.
- Refreshed portfolio social queue with `python3 tools/generate-portfolio-social-queue.py`; live posting remains owned by the split X/LinkedIn publishers.
- Verified live routes:
  - `https://8bitconcepts.com/work-with-us.html` HTTP 200
  - `https://8bitconcepts.com/diagnostic.html` HTTP 200
  - `https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html` HTTP 200
  - `https://8bitconcepts.com/.well-known/agent.json` HTTP 200

Weighted touch: 1 for outreach data repair, 1 for verified follow-up status, 1 for social queue refresh, 1 conversion-route proof.

Blockers:

- PNW SMB outreach has no safe sendable email targets. Remaining records are role-based, LinkedIn-only, or need enrichment.
- Public calls were not attempted in this segment because no call outcome could be completed safely inside the remaining window.

No scoped memory update needed for x-operator, linkedin-operator, reddit-operator, hn-operator, or social-editor.
