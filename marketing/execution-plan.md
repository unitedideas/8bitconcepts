# 8bitconcepts — Distribution Execution Plan

Generated: 2026-03-08

---

## Programmatic Posting: Definitive Assessment

**HN**: Read-only official API. No unofficial posting API exists. Manual only.

**LinkedIn**: Full posting API exists (`POST https://api.linkedin.com/rest/posts`). Requires one-time OAuth app setup (free). After setup, fully automatable. **This is the highest-leverage unlock.**

**Reddit**: Full posting API via PRAW or direct `/api/submit` endpoint. Free for personal/bot use. Requires Reddit account + app credentials. **Fully automatable after one-time setup.**

**Twitter/X**: API posting requires paid tier ($100/mo minimum). Skip.

---

## Decision Rationale

"The Integration Tax" leads. It has a concrete dollar story ($80K client, $74K spent, still not in prod) that stops a scroll and is immediately relevant to any VP or CTO evaluating AI projects — the exact buyer. HN goes first because that audience will amplify the piece if it lands, and HN traffic to a well-argued technical post compounds into inbound; LinkedIn follows 24-48 hours later to capture the business buyer layer. Reddit (r/MachineLearning + r/startups) runs on day 3 to extend reach without cannibalizing the HN moment. "Beyond the Prompt" distributes in the same sequence one week later — it's the deeper framework piece and benefits from having the cost story already in the market.

---

## Priority Order

| # | Action | Channel | Essay | Time |
|---|--------|---------|-------|------|
| 1 | Post to Hacker News | HN | Integration Tax | 3 min |
| 2 | Post to LinkedIn | LinkedIn | Integration Tax | 4 min |
| 3 | Post to r/MachineLearning | Reddit | Integration Tax | 3 min |
| 4 | Post to r/startups | Reddit | Integration Tax | 2 min |
| 5 | Post to Hacker News | HN | Beyond the Prompt | 3 min |
| 6 | Post to LinkedIn | LinkedIn | Beyond the Prompt | 4 min |
| 7 | Post to r/MachineLearning | Reddit | Beyond the Prompt | 3 min |
| 8 | Post to r/startups | Reddit | Beyond the Prompt | 2 min |
| 9 | Post to Hacker News | HN | Measurement Problem | 3 min |
| 10 | Post to LinkedIn | LinkedIn | Measurement Problem | 4 min |
| 11 | Post to r/MachineLearning | Reddit | Measurement Problem | 3 min |
| 12 | Post to r/ExperiencedDevs | Reddit | Measurement Problem | 3 min |
| 13 | Post to r/devops | Reddit | Measurement Problem | 3 min |
| 14 | LinkedIn API setup (one-time) | LinkedIn | — | 20 min |
| 15 | Reddit API setup (one-time) | Reddit | — | 15 min |

Actions 1-13 are manual. Actions 14-15 are one-time setup that enables future posts to be fully automated.

---

## ACTIONS — Execute in Order

---

### ACTION 1 — HN: "The Integration Tax"
**When**: Now (best HN windows: weekdays 8-10am EST or 12-2pm EST)
**Time**: 3 min
**URL**: https://news.ycombinator.com/submit

**Steps**:
1. Go to https://news.ycombinator.com/submit
2. Log into your HN account if not already logged in
3. Fill in title field — paste exactly:

```
The model is 10-20% of what AI actually costs — here's where the rest goes
```

4. Fill in URL field — paste exactly:

```
https://8bitconcepts.com/research/the-integration-tax.html
```

5. Click Submit
6. The post will appear. Click on the post title to go to the comments thread.
7. Click "add a comment" on your own post and paste the opening comment exactly:

```
This is something we see repeatedly in the field: teams budget carefully for model API costs (sometimes obsessively), then get blindsided by everything else. We wrote this up after a client ran $74k into a system that still wasn't in production at month four — against an initial $80k total budget. Model costs were $12k of that.

The actual cost distribution across real enterprise projects: data pipelines eat 20–30% (the "our data is fine" assumption almost never survives contact with production), system integration runs 15–25% (2–3 weeks per external system touchpoint is the honest estimate, not 2–3 days), evaluation 10–20% (most teams have no ground truth and won't notice model degradation until a stakeholder catches it in a demo), observability 5–10%, and then 15–25% of build cost annually just to keep the system from rotting.

The heuristic we landed on: take your model cost estimate and multiply by 5 for a standard integration, 8 for a complex enterprise one. Curious whether others have landed on similar numbers, or whether the distribution looks different in different domains — I'd expect data pipeline costs to be higher in regulated industries where you can't just normalize freely.
```

8. Submit the comment.

**Note**: Do not post again today. One post per account per domain per day is the HN norm.

---

### ACTION 2 — LinkedIn: "The Integration Tax"
**When**: 24-48 hours after HN post (so HN has time to run)
**Time**: 4 min
**URL**: https://www.linkedin.com/feed/ (click "Start a post")

**Steps**:
1. Go to https://www.linkedin.com/feed/
2. Click "Start a post"
3. Paste the following exactly (do not add or remove anything):

```
We had a client budget $80,000 for an AI demand forecasting system last year.

Model API costs: roughly $12,000 annually. Reasonable. They'd done the math.

By month four they'd spent $74,000 and the system still wasn't in production.

Here's what they missed: model cost is 10–20% of what AI actually costs to ship. The rest is a tax most organizations don't see coming.

- Data pipelines: 20–30%. Your data is not clean. It's not slightly messy — it's far worse than your data team believes, and it takes 2–6 months of engineering to find out.
- System integration: 15–25%. Budget 2–3 weeks per external system touchpoint, not 2–3 days.
- Evaluation and testing: 10–20%. Most teams have no systematic way to measure whether the model is still correct after an update. That's not a gap — that's a liability.
- Annual maintenance: 15–25% of build cost, every year. Models deprecate. APIs change. Dependencies drift.

A practical rule: take your estimated model cost. Multiply by 5. For complex enterprise integrations, multiply by 8. That's your year-one budget.

The organizations succeeding with AI aren't the ones with the most sophisticated models. They're the ones who treated integration as the product, not the afterthought.

We wrote up the full breakdown here: https://8bitconcepts.com/research/the-integration-tax.html

#AIStrategy #EnterpriseAI #TechLeadership
```

4. Set visibility to "Anyone" (public)
5. Click Post

---

### ACTION 3 — Reddit r/MachineLearning: "The Integration Tax"
**When**: Day 3 (after HN + LinkedIn have run)
**Time**: 3 min
**URL**: https://www.reddit.com/r/MachineLearning/submit

**Steps**:
1. Go to https://www.reddit.com/r/MachineLearning/submit
2. Select "Link" post type
3. Title field — paste exactly:

```
[D] The model is 10-20% of what AI actually costs in production — breakdown of where the rest goes
```

4. URL field — paste exactly:

```
https://8bitconcepts.com/research/the-integration-tax.html
```

5. Submit
6. In your own post's comment thread, add a top-level comment:

```
We work with a lot of engineering orgs deploying production ML systems. The pattern that prompted this: client budgeted $80K for an AI demand forecasting system, model API costs were ~$12K, but they'd burned through $74K by month four with nothing in production.

The cost breakdown across real projects: data pipelines 20–30% (the gap between "our data is fine" and production reality is usually 2–6 months of engineering), system integration 15–25% (2–3 weeks per external system touchpoint, not days), evaluation 10–20% (most teams have no systematic ground truth — they find out about model degradation when a stakeholder catches it in a demo), and maintenance 15–25% of initial build cost annually.

Heuristic that holds up reasonably well: multiply your model cost estimate by 5 for standard integrations, 8 for complex enterprise ones. Curious whether this matches what others see, especially in regulated domains where data pipeline complexity tends to be higher.
```

**Note**: r/MachineLearning uses the [D] prefix for discussions. Read the subreddit rules before posting — they have strict quality standards. If your account is new, karma thresholds may block submission; in that case, skip to r/startups.

---

### ACTION 4 — Reddit r/startups: "The Integration Tax"
**When**: Same day as Action 3, or Day 3
**Time**: 2 min
**URL**: https://www.reddit.com/r/startups/submit

**Steps**:
1. Go to https://www.reddit.com/r/startups/submit
2. Select "Link" post type
3. Title field — paste exactly:

```
Most companies are only budgeting for 10-20% of what AI actually costs — the breakdown
```

4. URL field — paste exactly:

```
https://8bitconcepts.com/research/the-integration-tax.html
```

5. Submit

**Note**: r/startups sometimes restricts link posts to accounts with sufficient karma. If blocked, use "Text" post type and include the key points from the LinkedIn post above as the body, with the URL at the end.

---

### ACTION 5 — HN: "Beyond the Prompt"
**When**: 7 days after Action 1
**Time**: 3 min
**URL**: https://news.ycombinator.com/submit

**Steps**:
1. Go to https://news.ycombinator.com/submit
2. Title field — paste exactly:

```
Why most teams plateau with AI agents (and what the teams that don't do differently)
```

3. URL field — paste exactly:

```
https://8bitconcepts.com/research/beyond-the-prompt.html
```

4. Submit
5. Go to your post's comment thread and add:

```
We work with a lot of engineering orgs on production agentic systems, and there's a consistent pattern: teams hit a ceiling and assume they've found the technology's limits. Usually they've found their own process limits instead.

What we've observed is effectively a maturity ladder. L1 is ad-hoc prompting — context windows fill up, results depend heavily on phrasing, and the whole thing is a "prompt-craft lottery." L2 is planning-first development: structured specs before agent invocation. This alone is a significant unlock. The key mental shift is "the conversation is the input to the work, not the work itself." L3 is skills — encoding expertise into reusable, versioned, composable units rather than one-off prompt chains that live in a single engineer's head. This is where most teams plateau, and the reason is organizational, not technical. L4-L6 cover workflows, orchestration, and validation.

The L5 → L6 gap is interesting — L6 (systematic validation of all agent outputs) is the rarest maturity level, and it's not because the technical implementation is especially hard. It's because it requires treating agentic engineering as a discipline with standards rather than a practice with enthusiasts. Most orgs aren't there yet.

Curious whether people building internal agentic tooling have found ways to accelerate the L2-L3 transition in particular — that seems like the highest-leverage intervention point.
```

---

### ACTION 6 — LinkedIn: "Beyond the Prompt"
**When**: 24-48 hours after Action 5
**Time**: 4 min
**URL**: https://www.linkedin.com/feed/

**Steps**:
1. Go to https://www.linkedin.com/feed/
2. Click "Start a post"
3. Paste exactly:

```
Most companies are using AI agents the same way people used spreadsheets in 1985: they've learned to type in cells. They haven't built a model.

After working with engineering teams across Series B to D companies, I keep seeing the same pattern. Teams reach a ceiling and mistake it for the technology's ceiling. It's not. It's a maturity ceiling.

The teams shipping reliable production agentic systems aren't prompting harder. They've moved through a different kind of engineering ladder:

- Planning: Structured specifications before agent invocation — not conversational fragments. The conversation is the input, not the work.
- Skills: Reusable, versioned, documented capabilities. Not one-off prompt chains that live in someone's head.
- Workflows: Agent capabilities wired into repeatable, triggerable processes. Infrastructure, not experiments.
- Orchestration: Parallel execution across specialized agent fleets. A single context window is finite. A fleet is effectively infinite.
- Validation: Systematic verification of every output. This is rare — not because it's technically hard, but because most organizations haven't built the discipline for it.

The bottleneck between levels 2 and 3 is almost never technical. It's organizational. Teams plateau because they haven't shifted from individual expertise to systematized expertise. That requires standards, not just talent.

Teams operating at the higher levels are seeing 3–5x improvements in development velocity. The gap is compounding.

Full framework: https://8bitconcepts.com/research/beyond-the-prompt.html

#AIEngineering #AgenticAI #EngineeringLeadership
```

4. Set visibility to "Anyone"
5. Click Post

---

### ACTION 7 — Reddit r/MachineLearning: "Beyond the Prompt"
**When**: Day 10 (3 days after Action 5)
**Time**: 3 min
**URL**: https://www.reddit.com/r/MachineLearning/submit

**Steps**:
1. Go to https://www.reddit.com/r/MachineLearning/submit
2. Select "Link" post type
3. Title — paste exactly:

```
[D] A maturity ladder for production agentic systems — why most teams plateau at L2 and what's required to move past it
```

4. URL — paste exactly:

```
https://8bitconcepts.com/research/beyond-the-prompt.html
```

5. Submit, then add comment in your thread:

```
The observation that prompted this: teams consistently mistake an organizational ceiling for a technology ceiling. L3 (skills — reusable, versioned agent capabilities) is where most teams plateau, and it's not a technical blocker. It's a standards problem. You have to treat agentic development as an engineering discipline, not a prompting practice.

L6 (systematic validation of all outputs) is the rarest in the wild. The barrier isn't implementation complexity — it's that validation requires having defined ground truth, and most orgs haven't done that work.

Curious whether anyone has built internal tooling that accelerated the L2→L3 transition specifically — that seems like the highest-leverage intervention point for orgs trying to move faster.
```

---

### ACTION 8 — Reddit r/startups: "Beyond the Prompt"
**When**: Same day as Action 7
**Time**: 2 min
**URL**: https://www.reddit.com/r/startups/submit

**Steps**:
1. Go to https://www.reddit.com/r/startups/submit
2. Select "Link" post type
3. Title — paste exactly:

```
Why engineering teams plateau with AI agents — it's not the technology, it's the process maturity
```

4. URL — paste exactly:

```
https://8bitconcepts.com/research/beyond-the-prompt.html
```

5. Submit

---

## ONE-TIME SETUP: LinkedIn Programmatic Posting

**Why**: Once done, all future LinkedIn posts can be sent via API — no manual steps.
**Time**: ~20 min
**Effort level**: Light (one OAuth flow, then it's done)

**Steps**:
1. Go to https://www.linkedin.com/developers/apps/new
2. Create an app:
   - App name: `8bitconcepts-publisher`
   - LinkedIn Page: select your 8bitconcepts company page (create one if needed at linkedin.com/company/setup/new/)
   - App logo: upload any image
3. Click "Create app"
4. On the app page, go to the "Products" tab
5. Request access to: **"Share on LinkedIn"** and **"Sign In with LinkedIn using OpenID Connect"** — click "Request access" for each (usually auto-approved)
6. Go to the "Auth" tab — copy your **Client ID** and **Client Secret** into 1Password
7. Generate a token: go to https://www.linkedin.com/developers/tools/oauth/token-generator
   - Select your app
   - Check all scopes (especially `w_member_social`)
   - Click "Request access token"
   - Copy the token into 1Password as `LINKEDIN_ACCESS_TOKEN`
   - Note: token expires in 60 days — set a calendar reminder to refresh
8. Test it works:

```bash
curl -X POST https://api.linkedin.com/rest/posts \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -H "LinkedIn-Version: 202504" \
  -d '{
    "author": "urn:li:person:YOUR_PERSON_URN",
    "commentary": "Test post — ignore",
    "visibility": "PUBLIC",
    "distribution": {"feedDistribution": "MAIN_FEED"},
    "lifecycleState": "PUBLISHED"
  }'
```

   (Get your person URN by calling: `curl -H "Authorization: Bearer YOUR_TOKEN" https://api.linkedin.com/v2/userinfo`)

9. Add `LINKEDIN_ACCESS_TOKEN` and `LINKEDIN_PERSON_URN` to `/foundry/.env`

After this, posting is a single API call. Wire into Foundry when ready.

---

## ONE-TIME SETUP: Reddit Programmatic Posting

**Why**: Once done, r/startups, r/MachineLearning, and any subreddit can be posted to via API.
**Time**: ~15 min
**Effort level**: Light

**Steps**:
1. Go to https://www.reddit.com/prefs/apps (logged into the 8bitconcepts or personal Reddit account)
2. Click "Create another app" at the bottom
3. Fill in:
   - Name: `8bitconcepts-publisher`
   - Type: select **"script"** (for personal use, no OAuth dance required)
   - Redirect URI: `http://localhost:8080` (placeholder, not used for script apps)
4. Click "Create app"
5. Copy the **client ID** (shown under the app name) and **client secret** into 1Password
6. Add to `/foundry/.env`:
   - `REDDIT_CLIENT_ID`
   - `REDDIT_CLIENT_SECRET`
   - `REDDIT_USERNAME`
   - `REDDIT_PASSWORD`
7. Test with Python (PRAW) or direct HTTP:

```bash
# Get access token
curl -X POST https://www.reddit.com/api/v1/access_token \
  -u "CLIENT_ID:CLIENT_SECRET" \
  -d "grant_type=password&username=USERNAME&password=PASSWORD" \
  -H "User-Agent: 8bitconcepts-publisher/1.0"

# Submit a link post
curl -X POST https://oauth.reddit.com/api/submit \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "User-Agent: 8bitconcepts-publisher/1.0" \
  -d "kind=link&sr=startups&title=Test+post&url=https://8bitconcepts.com&resubmit=true&nsfw=false&spoiler=false"
```

8. Wire into Foundry when ready.

**Note**: Reddit script apps are free with no rate limit beyond 60 req/min. Subreddit karma requirements still apply — if the account is new, posts may be auto-removed. Use an aged account with some history in those subreddits.

---

---

### ACTION 9 — HN: "The Six Percent"
**When**: Day 14 (two weeks after Action 1, let Integration Tax cycle complete)
**Time**: 3 min
**URL**: https://news.ycombinator.com/submit

Title:
```
88% of companies use AI. Only 6% see real returns — McKinsey's data on what separates them
```

URL: `https://8bitconcepts.com/research/the-six-percent.html`

Opening comment: see distribution-posts.md → HN post for "The Six Percent"

---

### ACTION 10 — Reddit r/engineering: "The Six Percent"
**When**: Day 14 (same day as Action 9)
**Title**: `McKinsey data: 88% of companies use AI, 6% see real returns — specific breakdown of what separates them`
**URL**: `https://8bitconcepts.com/research/the-six-percent.html`

---

### ACTION 11 — Reddit r/ExperiencedDevs: "The Six Percent"
**When**: Day 15
**Title**: `Why most AI tool ROI is near zero (Atlassian surveyed 3,500 devs — the data is interesting)`
**URL**: `https://8bitconcepts.com/research/the-six-percent.html`

---

### ACTION 12 — HN: "The Mandate Trap"
**When**: Day 21
**Title**: `Shopify's AI mandate worked. Duolingo's didn't. Here's the actual difference.`
**URL**: `https://8bitconcepts.com/research/the-mandate-trap.html`

Opening comment: see distribution-posts.md → HN post for "The Mandate Trap"

---

### ACTION 13 — Reddit r/EngineeringManagement: "The Mandate Trap"
**When**: Day 21 (same day as Action 12)
**Title**: `Shopify's AI mandate worked. Duolingo's didn't. The actual difference (not what the press covered).`
**URL**: `https://8bitconcepts.com/research/the-mandate-trap.html`

---

### ACTION 14 — Reddit r/startups: "The Mandate Trap"
**When**: Day 22
**Title**: `The AI mandate playbook everyone's copying — and why it works for Shopify but not for companies copying the memo`
**URL**: `https://8bitconcepts.com/research/the-mandate-trap.html`

---

### ACTION 15 — LinkedIn: "The Six Percent"
**When**: After LinkedIn API is set up (one-time) — then Day 15
**Content**: see distribution-posts.md → LinkedIn post for "The Six Percent"

---

### ACTION 16 — LinkedIn: "The Mandate Trap"
**When**: Day 22
**Content**: see distribution-posts.md → LinkedIn post for "The Mandate Trap"

---

## Summary

**Already published (no action needed):**
- ✅ Essay: The Integration Tax — live
- ✅ Essay: Beyond the Prompt — live
- ✅ Essay: The Six Percent — live (2026-03-09)
- ✅ Essay: The Mandate Trap — live (2026-03-09)

**Manual actions — 4-week cadence (total human time: ~48 min):**

| Day | Action | Channel | Essay |
|-----|--------|---------|-------|
| 1 | Action 1: HN post | HN | Integration Tax |
| 1 | Action 2: LinkedIn | LinkedIn | Integration Tax |
| 3 | Actions 3-4: Reddit | r/ML + r/startups | Integration Tax |
| 7 | Action 5: HN post | HN | Beyond the Prompt |
| 8 | Action 6: LinkedIn | LinkedIn | Beyond the Prompt |
| 10 | Actions 7-8: Reddit | r/ML + r/startups | Beyond the Prompt |
| 14 | Action 9: HN post | HN | Six Percent |
| 14 | Action 10: Reddit | r/engineering | Six Percent |
| 15 | Action 11: Reddit | r/ExperiencedDevs | Six Percent |
| 15 | Action 15: LinkedIn | LinkedIn | Six Percent |
| 21 | Action 12: HN post | HN | Mandate Trap |
| 21 | Action 13: Reddit | r/EngineeringManagement | Mandate Trap |
| 22 | Action 14: Reddit | r/startups | Mandate Trap |
| 22 | Action 16: LinkedIn | LinkedIn | Mandate Trap |

**One-time setup (total: ~35 min):**
- LinkedIn API setup — do once, all future posts automated
- Reddit API setup — do once, all future posts automated
