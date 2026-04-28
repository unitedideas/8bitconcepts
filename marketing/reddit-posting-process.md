# 8bitconcepts Reddit Posting Process

Verified against Reddit docs on 2026-04-28.

## Current State

- Reddit account: `u/EngineerAdditional30` is the approved default for 8bitconcepts Reddit posting.
- Browser session: currently logged in as `u/EngineerAdditional30`.
- Brand-account fallback: use `u/8bitconcepts` only if a dedicated account exists later and its credentials are stored.
- API credentials: no `reddit-client-id`, `reddit-client-secret`, `8bitconcepts-reddit-client-id`, or `8bitconcepts-reddit-client-secret` entries found in Keychain.

Before posting, verify the visible Reddit user menu says `u/EngineerAdditional30` unless a stored `u/8bitconcepts` account has replaced it.

## Channel Fit

Reddit is for technical or operator-useful artifacts, not generic consulting CTAs. Post only when the subreddit gets a native version of the idea:

- `r/MachineLearning`: data, methodology, model/eval/infrastructure findings.
- `r/LocalLLaMA`: local inference, on-device constraints, benchmarks, tooling.
- `r/ExperiencedDevs`: production failure modes, org design, engineering workflow.
- `r/EngineeringManagers`: team/process consequences of AI adoption.
- `r/startups`: founder/operator lessons with numbers and tradeoffs.

Check each subreddit rules page before posting. If links are restricted, use a self-post with the core argument and put the 8bit link only where the rules allow it.

## Manual Browser Flow

1. Verify the live paper URL returns 200.
2. Check `marketing/social-post-ledger.json` and the sync-state social lock.
3. Open `https://www.reddit.com/submit` or `https://www.reddit.com/r/<subreddit>/submit`.
4. Verify the active account in the Reddit user menu.
5. Select the target subreddit.
6. Use a subreddit-native title, not the paper title.
7. Choose link post only when links are allowed; otherwise use a text post.
8. Submit.
9. Copy the final post URL.
10. Mark the sync-state social lock as posted and update `marketing/social-post-ledger.json`.

Title shape:

```text
We tested 7,039 sites for MCP support; 5.8% passed a live handshake
```

Avoid:

```text
New 8bitconcepts paper: Q2 2026 MCP Ecosystem Health
```

## API Flow

Reddit requires OAuth for Data API clients and a descriptive User-Agent. The current official rate limit for eligible free Data API usage is 100 queries per minute per OAuth client ID, averaged over a window. Track `X-Ratelimit-Used`, `X-Ratelimit-Remaining`, and `X-Ratelimit-Reset`.

One-time setup:

1. Log into the Reddit account that should own the posts.
2. Create or open a traditional Reddit app at `https://www.reddit.com/prefs/apps`.
3. Create an app named `8bitconcepts-publisher`.
4. Use app type `script` for first-party posting from this machine.
5. Store the client ID, client secret, Reddit username, and Reddit password in the Foundry vault and Keychain.
6. Use this User-Agent format:

```text
script:8bitconcepts-publisher:v1.0.0 (by /u/<reddit username>)
```

Token request:

```bash
curl -sS -X POST https://www.reddit.com/api/v1/access_token \
  -u "$REDDIT_CLIENT_ID:$REDDIT_CLIENT_SECRET" \
  -H "User-Agent: script:8bitconcepts-publisher:v1.0.0 (by /u/$REDDIT_USERNAME)" \
  -d "grant_type=password&username=$REDDIT_USERNAME&password=$REDDIT_PASSWORD"
```

Submit a link post:

```bash
curl -sS -X POST https://oauth.reddit.com/api/submit \
  -H "Authorization: Bearer $REDDIT_ACCESS_TOKEN" \
  -H "User-Agent: script:8bitconcepts-publisher:v1.0.0 (by /u/$REDDIT_USERNAME)" \
  -d "api_type=json" \
  -d "kind=link" \
  -d "sr=<subreddit>" \
  -d "title=<title>" \
  -d "url=<url>" \
  -d "resubmit=true" \
  -d "sendreplies=true" \
  -d "nsfw=false" \
  -d "spoiler=false"
```

Submit a text post:

```bash
curl -sS -X POST https://oauth.reddit.com/api/submit \
  -H "Authorization: Bearer $REDDIT_ACCESS_TOKEN" \
  -H "User-Agent: script:8bitconcepts-publisher:v1.0.0 (by /u/$REDDIT_USERNAME)" \
  -d "api_type=json" \
  -d "kind=self" \
  -d "sr=<subreddit>" \
  -d "title=<title>" \
  -d "text=<markdown body>" \
  -d "sendreplies=true" \
  -d "nsfw=false" \
  -d "spoiler=false"
```

If Reddit returns a captcha or administrative rule block, stop API posting for that subreddit and use the browser flow. Do not try to automate captcha solving.

## Sources

- Reddit live API docs: `https://www.reddit.com/dev/api/`
- Reddit Data API rules/rate limits: `https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki`
- Reddit Devvit FAQ note that external scripts use a different auth flow: `https://developers.reddit.com/docs/guides/faq`
