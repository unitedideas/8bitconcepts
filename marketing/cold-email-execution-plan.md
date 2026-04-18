# 8bitconcepts Cold-Email Campaign — Execution Plan

**Status**: Ready to execute (blocked on Shane for domain registration)
**Targets**: 31 PNW SMB owners (13 with verified direct email, 18 LinkedIn-only)
**Timeline**: 2-week warmup + 3-day send window
**Expected**: 15–20% open rate, 2–3 qualified leads

---

## Phase 1: Sender Domain Setup (Shane — 30 min)

**Decision**: Fresh outreach-only domain (not aidevboard, not personal email)

**Why**: 
- ADB domain reputation is damaged (legacy campaign spam feedback)
- Fresh domain builds 8bc-specific reputation for future campaigns
- Enables scalable outreach infrastructure across multiple properties
- 2-week warmup is acceptable vs messaging quality tradeoff

**Action items** (Shane does in Namecheap/GoDaddy):
1. Register `8bitconcepts-outreach.com` (or similar; $12–18/yr)
   - Registrant: Shane Cheek (or business)
   - Email: hello@8bitconcepts.com (or personal)
2. Point to Resend domain verification:
   - Go to Resend Dashboard → Domains → Add Domain
   - Enter `8bitconcepts-outreach.com`
   - Add the 3 DNS records: CNAME (for domain verification), SPF, DKIM
3. Resend will verify domain (instant once DNS propagates)
4. Share the verified domain name back: `[DOMAIN_VERIFIED]`

**Cost**: $15/yr (trivial — execute from Privacy.com card)

---

## Phase 2: Email Warmup (Owl — 2 weeks)

Once domain is verified in Resend, execute warmup sequence using the Resend API:

```bash
# Warmup.py pattern (existing)
# Day 1–7: 5 emails/day to safe inboxes (bounce monitors)
# Day 8–14: 10 emails/day, mix of safe + warm prospects
# Day 15+: production volume (31 targets in 3-day window)
```

Warmup target list (pre-seeded):
- Bounce monitors (Gmail, Outlook, Yahoo accounts that verify deliverability)
- Existing ADB newsletter subscribers as safety set
- 3–4 friendly prospects who've engaged before

**Automation**: `warmup.sh` spawns from launchd every morning at 8am.

---

## Phase 3: Campaign Send (Owl — 3 days, post-warmup)

**Send window**: Day 15–17 post-warmup (once domain is warm)

**Target segmentation**:

### Tier 1 (Direct email — 13 targets)
Send immediately with matching template:
- Atlantic & Pacific Freightways → Template 1 (Logistics)
- Greear Kramer Monaghan CPAs → Template 4 (Professional Services)
- Brewer Caley CPAs → Template 4
- Harlow Wealth Management → Template 4
- Pacific Northwest Tax & Accounting → Template 4
- High Tech Manufacturing → Template 2 (Manufacturing)
- JJH Law → Template 4
- Grady Britton → Template 3 (creative agency variant)
- Freeland Spirits → Template 3 (food/beverage)
- Portland Pet Food Company → Template 3
- Jacobsen Salt Co. → Template 3
- Bridge City Medical → Template 3

### Tier 2 (LinkedIn-only — 18 targets)
LinkedIn message 2–3 days BEFORE email (if email exists), else LinkedIn-only path:
- Message: "Hi {first_name}, saw {company} on LinkedIn. Read this: [PNW AI Desert link]. Relevant?" → CTA to `8bitconcepts.com/work-with-us` + email address
- Wait 2 days
- Email from 8bitconcepts-outreach domain (if email from CSV)
- If no email: close loop via LinkedIn after 5 days

**Send cadence**: 3–4 per day (stagger to avoid sender volume spikes)

**Tracking**: Resend webhook logs → Discord ping on opens + clicks

---

## Phase 4: Follow-Up Sequence (Owl — days 4–30 post-send)

Auto-fire follow-ups per `outreach.py` pattern:

| Day | Action | Template |
|---|---|---|
| +0 | Send initial | Industry-specific |
| +4 | Follow-up (no reply) | "Checking in" + Compounding Gap research |
| +7 | (for warm prospects) | Alternative CTA: $500 diagnostic instead of call |
| +14 | Final (no reply) | One-liner + soft close |

All delivered from `hello@8bitconcepts-outreach.com` (visible sender).

---

## Success Metrics

- **Sends**: 31 direct emails + 18 LinkedIn messages
- **Open rate target**: 15–20% (domain warmth + localized + personalized)
- **Click rate target**: 3–5% (drive to `/work-with-us`)
- **Qualified leads**: 2–3 (target call/diagnostic booking)
- **Sales target (Q2)**: 1 engagement at $2.5k–5k first-month

---

## Current Status

- [x] 31 targets identified + prioritized
- [x] 4 industry-specific templates written (110–160 words each)
- [x] PNW AI Desert research hook live
- [x] Resend integration ready (API + webhooks)
- [x] Warmup automation coded
- [x] Follow-up sequence configured
- [ ] Domain registered (Shane blocks on this)
- [ ] Domain verified in Resend
- [ ] Warmup sequence executed (Owl, 2 weeks)
- [ ] Campaign launched (Owl, day 15+)

---

## Rollback / Pause

- If domain reputation tanks mid-warmup: switch to fresh domain (minimal penalty)
- If open rate < 5%: pause, investigate sender issues, retry with list subset
- If > 2 unsubscribes: audit template for non-compliance (unlikely but flagged)

---

## Notes

- BCC Shane on all sends for transparency: `hello@8bitconcepts.com` (already in Resend config as cc recipient)
- All copy is Shane's voice — no edits without his review
- Industry templates are locked once approved; variances go to a new template version
- This plan is async — no waiting for replies to move forward. LinkedIn + email run in parallel.
