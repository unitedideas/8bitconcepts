# 8bitconcepts Social Publishing Rule

Every 8bitconcepts research paper and every daily AI insight should teach first, route second, and never read like a pitch.

## Accounts

- X: `@8bitconcepts`
- LinkedIn login: `hello@8bitconcepts.com`
- LinkedIn profile: `https://www.linkedin.com/in/shane-cheek-9173473b6/`
- Hacker News: `8bitconcepts`
- Reddit: `u/EngineerAdditional30` is the approved default unless a dedicated `u/8bitconcepts` account exists later. API app is not configured yet. See `marketing/reddit-posting-process.md`.
- Dev.to / Hashnode: 8bit/research account when available; otherwise ledger the missing account/API credential.

`@8bitconcepts` is agent-owned for normal 8bit marketing. Do not ask which X account to use or whether this account is appropriate. Draft, lock, post, and ledger the content from `@8bitconcepts`.

Marketing posts are pre-approved on Foundry-owned or logged-in marketing accounts. When executing 8bit paper or insight distribution, publish without asking Shane for per-post approval after verifying account identity, duplicate locks, and channel fit. This applies to X, LinkedIn, Hacker News, Reddit, Dev.to/Hashnode, newsletters, directories, gists, and product/community surfaces.

## New Paper Distribution

For every new paper:

1. Verify the paper URL returns 200 before drafting or posting.
2. Generate channel-native copy with `python3 tools/generate-social-posts.py --paper <slug>`.
3. Check `marketing/social-post-ledger.json` before posting. If the normalized fingerprint already exists as `posted`, `scheduled`, or `queued`, do not post it again.
4. Verify the active X account is `@8bitconcepts` before composing. If the browser is logged into another account, switch accounts or log in first.
5. Publish an X native post with the strongest falsifiable claim first. Put the link in the first reply unless the card itself is the visual asset.
6. Publish a LinkedIn native post with the claim, the evidence, and one real discussion question. Put the link in the post only if the piece is already proven to render a good card; otherwise put it in the first comment.
7. Submit to Hacker News with the most technical neutral title available. If the paper is operational rather than code-heavy, frame the methodology, data, or failure mode rather than skipping HN.
8. Submit to Reddit using channel-specific subreddit fit. Default pools: `r/MachineLearning`, `r/ArtificialInteligence`, `r/artificial`, `r/startups`, `r/ExperiencedDevs`, `r/devops`, and `r/EngineeringManagement`; pick the best 1-3, not every subreddit. Verify the active Reddit account before composing and follow `marketing/reddit-posting-process.md`.
9. Republish/adapt the paper to Dev.to or Hashnode when the angle can stand as a technical article. Canonical link back to the original paper.
10. Add the paper to newsletter/outreach motion: weekly digest, relevant newsletter/editorial contacts, and any public lists/directories that match the topic.
11. Submit/index the URL through IndexNow and any existing search/discovery submitters.
12. Update `marketing/social-post-ledger.json` with channel, account, URL, status, date, and fingerprint immediately after each post.
13. Update `marketing/latest-research-social.md` with exact account, URL, post copy, and any first-comment copy.
14. If a live post starts with "New paper," "New post," or a title instead of the claim, edit it before moving to the next channel.

Bad frame:

```text
New paper: Q2 2026 MCP Ecosystem Health
```

Good frame:

```text
Most MCP adoption claims are not real endpoints.
```

## Paper Cadence

Every other day, promote one research paper across all channels. Do not treat LinkedIn, HN, Reddit, Dev.to/Hashnode, newsletter, or outreach as optional. If a channel cannot be posted because access is missing, log it as `blocked` with the exact credential/account gap and keep shipping the remaining channels.

Automation: launchd job `com.foundry.8bitconcepts.paper-distribution`, backed by sync-state automation `8bit-paper-distribution-every-other-day`.

Fully distributed means the paper has a ledger row for each of:

1. X
2. LinkedIn
3. Hacker News
4. Reddit
5. Dev.to or Hashnode
6. Newsletter or direct editorial outreach
7. Indexing/discovery submission

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
- HN submission: use a technical/data/methodology frame for every paper.

## Funnel Rule

Do not end with “book a call.” The funnel is implicit:

- Research posts point to `8bitconcepts.com/research`.
- Hiring-market posts point to `aidevboard.com` or the relevant 8bit paper.
- Agent-readiness posts point to `nothumansearch.ai` or the relevant 8bit paper.
- Consulting proof posts point to `case-studies.html` or `work-with-us.html` only when the post naturally asks how to apply the pattern.

The default CTA is: data, methodology, or artifact. The consulting CTA is secondary.

## Hacker News Guard

HN is not a generic announcement channel, but research papers still go out there. Use the most technical neutral framing available: method, dataset, failure mode, benchmark, or implementation lesson. Log every HN submission in `marketing/social-post-ledger.json` with the item URL.

## Reddit Guard

Reddit is not a generic announcement channel. Use it for subreddit-native artifacts: methodology, benchmarks, production failure modes, technical tradeoffs, and operator lessons with evidence.

Before posting, check the subreddit rules, verify the active browser account, claim the sync-state social lock, and log the post URL immediately after it exists. Do not cross-post the same URL to multiple subreddits on the same day.

API posting is not configured yet. Reddit requires OAuth, a registered app, and a descriptive User-Agent. Store the app credentials before wiring automation; current free Data API usage is rate-limited at 100 QPM per OAuth client ID.

## LinkedIn Browser Recovery Guard

LinkedIn browser posting is allowed only for explicit supervised recovery runs while API credentials are missing. Use Brave, hold the local Computer Use lease, verify `Shane Cheek` plus `Founder at 8bitconcepts` on the feed, and claim the sync-state social-content lock before composing.

The reliable path is: click `Start a post`, paste the approved copy, verify the full copy appears in the composer, wait for the `Post` button to become enabled, click `Post`, then capture the `Post successful. View post` URL. Do not stop at a filled composer when the identity, copy, lock, and enabled state are all verified.

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
