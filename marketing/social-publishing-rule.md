# 8bitconcepts Social Publishing Rule

Every 8bitconcepts research paper and every daily AI insight should teach first, route second, and never read like a pitch.

## Accounts

- X: `@8bitconcepts`
- LinkedIn login: `hello@8bitconcepts.com`
- LinkedIn profile: `https://www.linkedin.com/in/shane-cheek-9173473b6/`
- Hacker News: submit only technical systems pieces.
- Reddit: `u/EngineerAdditional30` is the approved default unless a dedicated `u/8bitconcepts` account exists later. API app is not configured yet. See `marketing/reddit-posting-process.md`.

`@8bitconcepts` is agent-owned for normal 8bit marketing. Do not ask which X account to use or whether this account is appropriate. Draft, lock, post, and ledger the content from `@8bitconcepts`.

## New Paper Distribution

For every new paper:

1. Verify the paper URL returns 200 before drafting or posting.
2. Generate channel-native copy with `python3 tools/generate-social-posts.py --paper <slug>`.
3. Check `marketing/social-post-ledger.json` before posting. If the normalized fingerprint already exists as `posted`, `scheduled`, or `queued`, do not post it again.
4. Verify the active X account is `@8bitconcepts` before composing. If the browser is logged into another account, switch accounts or log in first.
5. Publish an X native post with the strongest falsifiable claim first. Put the link in the first reply unless the card itself is the visual asset.
6. Publish a LinkedIn native post with the claim, the evidence, and one real discussion question. Put the link in the post only if the piece is already proven to render a good card; otherwise put it in the first comment.
7. Submit to Hacker News only when the piece has a technical systems angle. Use a neutral title and a factual first comment.
8. Submit to Reddit only when the subreddit gets a native technical/operator angle. Verify the active Reddit account before composing and follow `marketing/reddit-posting-process.md`.
9. Update `marketing/social-post-ledger.json` with channel, account, URL, status, date, and fingerprint immediately after each post.
10. Update `marketing/latest-research-social.md` with exact account, URL, post copy, and any first-comment copy.
11. If a live post starts with "New paper," "New post," or a title instead of the claim, edit it before moving to the next channel.

Bad frame:

```text
New paper: Q2 2026 MCP Ecosystem Health
```

Good frame:

```text
Most MCP adoption claims are not real endpoints.
```

## Twice-Daily AI Insight Cadence

Post two AI insights per day:

- Morning: one short data-backed insight, teardown, chart, or claim.
- Afternoon: one practical pattern, failure mode, field note, meme, or visual.
- Generate the queue with `python3 tools/generate-daily-ai-insights.py`; it writes `marketing/daily-ai-insights.md` and `marketing/daily-ai-insights-queue.json`.
- Post from pending queue items before inventing new content. Do not waste existing drafts.
- Treat `marketing/social-drafts.md`, `marketing/latest-research-social.md`, and `marketing/daily-ai-insights.md` as backlog sources. Refresh stale stats before posting old drafts.
- Every queued item needs a fingerprint in `marketing/social-post-ledger.json` before posting. Duplicate content makes the feed look automated in the bad way.

The topic area can be broad: AI hiring, agent infrastructure, MCP, evals, production failures, workflow automation, org design, prompt decay, governance, AI ROI, agentic search, or operating-system patterns for agents.

`tools/x-ai-stat-bot.py` also runs under launchd as `com.foundry.8bitconcepts.x-ai-stat-bot` in draft mode every random 29-114 minutes. It uses the same voice rules and duplicate gates, writes linkless X-native copy capped below the composer limit, and keeps the route URL in metadata instead of publishing live.

Every post must satisfy all four:

1. It teaches something specific.
2. It connects naturally to an 8bitconcepts surface, ADB, NHS, or a Foundry-built proof point.
3. It avoids hard selling, fake urgency, and generic thought-leadership filler.
4. It has a comment/click trigger: tension, a surprising number, a disagreement, a before/after, or a useful artifact.

## Format Mix

Rotate formats so the feed does not become one-note:

- Data point: one surprising stat from ADB, NHS, or 8bit research.
- Mini teardown: what a tool/company claims vs. what the live surface verifies.
- Field note: what failed in production and what changed.
- Diagram/infographic: a simple table or flow that explains a system.
- Meme: only if it teaches a real pattern.
- Poll: use when the answers reveal market signal.
- Thread: use for multi-step methodology or before/after stories.
- HN submission: use sparingly for technical artifacts and research pages.

## Funnel Rule

Do not end with “book a call.” The funnel is implicit:

- Research posts point to `8bitconcepts.com/research`.
- Hiring-market posts point to `aidevboard.com` or the relevant 8bit paper.
- Agent-readiness posts point to `nothumansearch.ai` or the relevant 8bit paper.
- Consulting proof posts point to `case-studies.html` or `work-with-us.html` only when the post naturally asks how to apply the pattern.

The default CTA is: data, methodology, or artifact. The consulting CTA is secondary.

## Hacker News Guard

HN is not a generic announcement channel. Submit only technical systems pieces
with a neutral title from the `8bitconcepts` account. Log every HN submission
in `marketing/social-post-ledger.json` with the item URL.

## Reddit Guard

Reddit is not a generic announcement channel. Use it for subreddit-native artifacts: methodology, benchmarks, production failure modes, technical tradeoffs, and operator lessons with evidence.

Before posting, check the subreddit rules, verify the active browser account, claim the sync-state social lock, and log the post URL immediately after it exists. Do not cross-post the same URL to multiple subreddits on the same day.

API posting is not configured yet. Reddit requires OAuth, a registered app, and a descriptive User-Agent. Store the app credentials before wiring automation; current free Data API usage is rate-limited at 100 QPM per OAuth client ID.

## Anti-Duplicate Guard

Before any public post:

1. Normalize the candidate copy by lowercasing and collapsing whitespace.
2. Hash it with SHA-256 and keep the first 16 hex chars.
3. Search `marketing/social-post-ledger.json`.
4. If the fingerprint exists as `posted`, `scheduled`, or `queued`, skip the post and pick the next pending item.
5. If the idea is useful but too similar, rewrite the angle, format, or proof point before posting.

Backlog is an asset. Duplicate posting is a brand tax.

## Hook Formula

Use this order:

1. Claim: what is true that the market is missing?
2. Evidence: one number, artifact, or observed failure.
3. Implication: why this changes what builders/operators should do.
4. Route: where the full data, tool, or method lives.

If the first line could be replaced with “new post,” rewrite it.
