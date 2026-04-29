# X Premium Distribution Playbook

Source check date: 2026-04-29.
Primary account: `@8bitconcepts`.

## Goal

Use X Premium as a distribution engine first, monetization second.

The payout program is not the main prize yet. The useful prize is verified-user reach, reply priority, Articles, Media Studio, X Pro/Radar, post promotion, and retargeting. Revenue sharing becomes meaningful only after the account clears X's thresholds.

## Revenue Sharing Gate

X Creator Revenue Sharing eligibility currently requires:

- Active Premium, Premium Business, or Premium Organizations.
- 5M organic impressions in the last 3 months.
- 500 verified followers.
- Supported payout country.
- Compliance with X rules.

Source: https://help.x.com/en/using-x/creator-revenue-sharing

Payout mechanics:

- X weights verified Home timeline impressions.
- Premium+ interactions can carry more value than Basic interactions.
- Different content formats can be weighted differently.
- Payouts are biweekly with a $30 minimum through Stripe after identity and payout setup.

Operating implication: optimize for verified/Premium people replying, liking, reposting, and viewing in Home. Do not optimize for raw anonymous impressions.

## Monetization Guardrails

Before enabling payout behavior, keep the account clean:

- Complete profile, verified email, 2FA, Stripe, and identity verification.
- No engagement bait, paid engagement swaps, artificial boosting, or spam behavior.
- Disclose AI-generated armed-conflict video. Better: do not post that format from this account.
- Avoid prohibited monetization categories entirely.

Source: https://help.x.com/en/rules-and-policies/content-monetization-standards

## Premium Surfaces To Use

### Reply Priority

Premium and Premium+ get reply-priority treatment. Use this by replying to large accounts in the AI, agents, MCP, hiring, and operator-software conversations with one useful data point, not a pitch.

Daily target: 10 high-signal replies.

### Long Posts

Premium can post up to 25,000 characters. Use this for concise mini-essays that would otherwise be threads.

Default shape:

1. Falsifiable finding.
2. 3-5 numbered evidence points.
3. Link or screenshot only after the useful part.
4. One direct question to pull replies from verified users.

### Articles

Premium accounts can publish Articles with text, media, embedded posts, formatting, and links.

Use Articles as native distribution copies of 8bit research:

- One Article per major paper.
- Pin for 24-72 hours.
- Break it into 3-5 short posts linking back to the Article and original research.
- Reply to every serious early reader.

Source: https://help.x.com/en/using-x/articles

### Media Studio

Verified subscribers get Media Studio at `studio.x.com`, with media management and analytics.

Use it for:

- Uploading charts and short videos.
- Scheduling media posts.
- Exporting video analytics.
- Measuring watch time, completion rate, country, platform, organic vs promoted views.

Sources:
- https://help.x.com/en/using-x/media-studio
- https://help.x.com/en/using-x/media-studio-analytics

### Video

Premium supports long video uploads. Official docs currently describe up to 4 hours on web/iOS and 10 minutes on Android, with 16GB max for long web/iOS uploads.

Use video sparingly:

- 30-90 second chart walkthroughs.
- One data point per clip.
- Captions or burned-in text.
- First frame should carry the finding without sound.

Source: https://help.x.com/en/using-x/premium-longer-videos

### X Pro / Radar / Top Articles

Premium+ includes X Pro access and Radar Search. X Pro supports multi-column workspaces, scheduled posts, advanced search, decks, and multiple account switching.

Use this as the distribution cockpit:

- Column 1: AI agents/MCP keywords.
- Column 2: target accounts.
- Column 3: mentions/replies.
- Column 4: posts from competitors and adjacent newsletters.
- Column 5: bookmarks needing reply.

Top Articles surfaces the most-shared articles from the network and people they follow. Use it to find daily hooks and accounts already discussing AI tooling.

Sources:
- https://help.x.com/en/using-x/x-premium
- https://help.x.com/en/using-x/x-pro
- https://help.x.com/en/using-x/top-articles

## Paid Reach

Quick Promote can boost an existing post. Official docs show budget choices from $10 to $2,500, with results split by organic and promoted engagements. Promoted posts can appear across X-owned surfaces including Home timelines and profiles.

Use paid reach only on posts that already proved organic pull:

- Organic test window: 2-6 hours.
- Promote only if organic engagement rate is above the account baseline.
- Boost a post, not a landing page ad, when the post has standalone value.
- Prefer engagement or website-traffic objectives depending on the asset.
- Retarget post engagers after a useful top-of-funnel post.

Sources:
- https://help.x.com/en/managing-your-account/increase-x-reach
- https://business.x.com/en/advertising/campaign-types
- https://business.x.com/en/advertising/targeting
- https://business.x.com/en/help/campaign-setup/campaign-targeting/post-engager-targeting
- https://business.x.com/en/help/campaign-measurement-and-analytics/conversion-tracking-for-websites/about-conversion-tracking

## Cadence

Daily minimum:

- 4 original posts.
- 10 high-signal replies.
- 2 quote posts on larger accounts.
- 1 repost with comment.
- 1 profile/Article pin check.

Weekly:

- 1 native X Article adapted from 8bit research.
- 2 chart/image posts.
- 1 short video.
- 1 promoted-post test if spend is approved and an organic winner exists.

Bot cadence:

- Keep the current stat bot under ~6-10 original posts/day.
- Add a separate reply queue; do not make the original-post bot spray replies.
- Keep duplicate protection by `fact_key` and `fingerprint`.
- Keep quiet hours unless a live launch/news event is active.

## Format Mix

Use rotation to prevent one-note posting:

- Data point: one number, one implication.
- Mini teardown: what a company/site gets wrong about agent readiness.
- Chart/screenshot: visual proof from ADB/NHS/8bit data.
- Contrarian operator note: short, dry, practical.
- Article excerpt: one paragraph from a long-form Article.
- Quote reply: add a measured correction with data.
- Launch/support: product route only after value is clear.

## What To Avoid

- Engagement farming.
- Generic AI takes.
- Reposting the same fact with different wording.
- Link-first posts.
- Asking for likes/reposts/follows.
- Posting from the wrong account.
- Armed-conflict AI video content.

## Immediate Actions

1. Check `@8bitconcepts` monetization settings for exact remaining gaps: verified follower count, 3-month impressions, identity, Stripe.
2. Upgrade posting loop from original-only to original + reply/quote workflow.
3. Create the first native X Article from the MCP ecosystem-health paper.
4. Build a target-account list for reply priority: AI infra founders, MCP maintainers outside blocked orgs, AI hiring reporters, operator SaaS founders.
5. Add X Pixel only after a paid promotion test is approved.
