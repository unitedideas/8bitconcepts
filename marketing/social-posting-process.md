# 8bitconcepts Social Posting Process

This is the reusable process from the Q2 2026 MCP Ecosystem Health launch. It exists so future posting is systematic, not article-specific.

## Accounts

- X: `@8bitconcepts`
- LinkedIn: Shane profile, login `hello@8bitconcepts.com`
- Hacker News: `8bitconcepts`

## Working Rule

Every post must teach first, route second, and never read like a pitch. The route can be 8bit research, AI Dev Board, Not Human Search, or a case study, but the post should stand on its own without the link.

## New Paper Flow

1. Verify the live URL returns 200.
2. Generate drafts with `python3 tools/generate-social-posts.py --paper <slug>`.
3. Rewrite the hook so the first line is the strongest falsifiable claim, not the paper title.
4. Check `marketing/social-post-ledger.json` for duplicate fingerprints.
5. Before posting to X, verify the active account is `@8bitconcepts`. If the browser is logged into another account, switch accounts or log in before composing.
6. Post X, LinkedIn, and HN only if each channel has a native angle.
7. Log the live URL and fingerprint in `marketing/social-post-ledger.json` immediately after posting.
8. Leave any unused good drafts as `pending` or `backlog_refresh_before_posting`; do not discard them.

## Twice-Daily AI Insight Flow

1. Run `python3 tools/generate-daily-ai-insights.py`.
2. Use `marketing/daily-ai-insights-queue.json` as the machine queue.
3. Post the morning item around 08:30 PT and the afternoon item around 14:30 PT.
4. Rotate formats: data point, mini teardown, field note, infographic, meme, poll, thread, or short think piece.
5. Reuse pending backlog before creating new content.
6. Refresh stale claims before posting old drafts from `marketing/social-drafts.md`.

Codex automation `8bit-daily-ai-social-queue` refreshes this queue every day at 08:20 and 14:20 PT. It preserves pending backlog, checks duplicate fingerprints, and keeps the queue ready for channel posting.

## Anti-Duplicate Gate

Before any public post, normalize the candidate copy by lowercasing and collapsing whitespace, hash it with SHA-256, and keep the first 16 hex chars. If that fingerprint exists in `marketing/social-post-ledger.json` with status `posted`, `scheduled`, or `queued`, skip it.

Similar ideas are allowed only when the angle is materially different: new data, new format, new proof point, or a different audience. Same idea plus different wording is still a duplicate.

## Q2 2026 MCP Launch Pattern

The weak framing was:

```text
New 8bitconcepts paper: Q2 2026 MCP Ecosystem Health
```

The stronger framing was:

```text
Most MCP claims are not real endpoints.
```

The HN title that worked was:

```text
We tested 7,039 sites for MCP support; 5.8% passed a live handshake
```

This worked because it led with a falsifiable finding, not an announcement, and because the route was a live methodology page.

## Automation Boundary

The automated system owns research selection, draft generation, queue creation, duplicate checks, and ledger updates. Public posting uses the configured channel accounts and must always pass the anti-duplicate gate before anything goes live.
