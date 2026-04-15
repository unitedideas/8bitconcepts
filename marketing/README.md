# 8bitconcepts Marketing

Tools for outbound marketing. Everything uses Resend from the verified
`hello@8bitconcepts.com` sender, plus the shared aidevboard subscriber list
(tag-filtered).

## Components

- `outreach.py` — cold 1-to-1 email sender targeting execs (sales) or
  journalists/authors (media). Reads `outreach-targets.json`, writes
  `outreach-sent.json`. One email per target, logged by Resend message ID.
- `newsletter.py` — weekly digest sender. Queries the aidevboard admin
  subscriber endpoint, filters to tag `8bitconcepts-research`, composes
  HTML+text digest from the 3 newest papers in `../research.json`, sends
  via Resend with per-recipient unsubscribe URL.
- `outreach-targets.json` — list of verified-email contacts.
  `source_confidence` must be `verified` or `high`; never `guessed`.
  Bounce rate on guesses runs ~30%, on primary-source-verified ~0%.
- `outreach-sent.json` — delivery log; each entry has Resend message ID
  for downstream correlation in the engagement monitor.
- `newsletter-sent.json` — broadcast log (per-broadcast with recipient
  list + success/fail counts).
- `outreach-emails.txt`, `distribution-posts.md`, `execution-plan.md` —
  historical drafts from 2026-03 session. Manual posting plan for
  HN/LinkedIn/Reddit which is blocked on Shane-identity accounts.
- `cto-outreach-targets.md` — 2026-03 target list with no email
  addresses. Superseded by `outreach-targets.json` for anyone who got
  enriched via market-researcher agents.

## Usage

```bash
cd ~/foundry-businesses/8bitconcepts

# add new verified target
# edit marketing/outreach-targets.json directly, or via dispatch to
# market-researcher agents with primary-source-only constraint

# send all pending outreach (skips already-sent by email)
python3 marketing/outreach.py send

# dry-run first to inspect copy
python3 marketing/outreach.py dry-run

# outreach status
python3 marketing/outreach.py status

# weekly digest (pulls subscribers with tag '8bitconcepts-research')
python3 marketing/newsletter.py dry-run
python3 marketing/newsletter.py send
```

## Hooks

Each outreach target has a `hook` field selecting the email template.
Hooks in `outreach.py`:

- `integration-tax`, `org-chart-problem`, `measurement-problem`,
  `six-percent` — exec sales pitches
- `media-integration-tax`, `media-six-percent` — journalist story pitches
- `founder-integration-tax`, `founder-six-percent` — early-stage founder
  tactical framing (YC-targeted)

## Deliverability discipline

The `source_confidence` field is load-bearing. Only `verified` (primary
source: personal-site mailto, company about page, byline author page,
self-disclosed in published post) and `high` (company bio + confirmed
email-domain pattern) should be sent. Guessed / aggregator-surfaced
emails run ~30% bounce rate and damage sender reputation. Memory
`feedback_outreach_personal_emails.md` has the full discipline rule.

## Infrastructure dependencies

- `security find-generic-password -a foundry -s resend-api-key` —
  Resend API key for sending
- `security find-generic-password -a foundry -s aidevboard-admin-key` —
  admin auth for `/api/v1/admin/subscribers` (used by `newsletter.py`)
- `https://aidevboard.com/api/v1/subscribe` — subscribers are stored
  in the shared aidevboard Postgres, tag-filtered per business
- `https://aidevboard.com/unsubscribe/{id}` — CAN-SPAM/GDPR compliant
  one-click unsubscribe
- Aidevboard engagement-monitor (launchd `com.foundry.aidevboard.engagement`,
  30min) pulls Resend events for ALL sends under the shared API key, so
  8bc sends are auto-tracked without separate infra.

## Future automation

- Wire `newsletter.py send` to launchd weekly (Wed 8am ET is the memory
  rule from aidevboard newsletter schedule) once subscriber list > 5.
- Add `follow-up` command to `outreach.py` mirroring aidevboard pattern:
  4-day delay, check delivery_status, halt if bounce > 5%.
- Research retargeting: schedule weekly market-researcher batches to
  enrich `outreach-targets.json` with new YC cohorts or conference
  speakers.
