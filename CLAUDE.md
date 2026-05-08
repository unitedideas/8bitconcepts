# 8bitconcepts — Project Rules

## Automation State Handling

Marketing automation and outreach loops write tracking state to `marketing/`, `logs/`, and `runs/` directories. These files (queue.json, ledgers, followup logs) represent completed automation work and should be committed.

**Golden Rule — no stale uncommitted automation state:**
- Hook `stale_automation_state.py` runs on every Bash operation
- Any uncommitted files in automation dirs >4 days old are auto-committed
- This prevents indefinite accumulation and auto-commit-then-revert cycles

**For developers**: If you revert an auto-commit that includes automation state, know that the files will re-accumulate and be auto-committed again. Instead, move state-tracking files out of git (use a side database, cache, or logs directory).

---

## API / Core Invariants

*(Inherit from parent Foundry configuration)*
