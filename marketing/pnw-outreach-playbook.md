# PNW Small-Business Outreach Playbook — 8bitconcepts Consulting

**Audience:** Owners/operators of 5–50 employee businesses in Vancouver WA, Camas WA, Portland OR, Tigard OR + surrounding metro.

**Built:** 2026-04-17. Owner: Shane (Foundry).

---

## What's Live (Owl-shipped)

**Target list:** `pnw-smb-targets.csv` (31 named SMB owners across the 4 cities; ~13 with public email; details in `pnw-smb-targets-README.md`)
**Email templates:** `pnw-cold-email-templates.md` (6 industry-specific + 2 follow-ups + subject line bank, voice-rule compliant)
**Case studies:** `https://8bitconcepts.com/case-studies.html` (3 real shipped Foundry products as proof)

Geo-targeted landing pages with LocalBusiness schema for organic Google "near me" capture:

- **Hub:** [8bitconcepts.com/local/](https://8bitconcepts.com/local/)
- **Vancouver, WA:** [/local/vancouver-wa.html](https://8bitconcepts.com/local/vancouver-wa.html)
- **Camas, WA:** [/local/camas-wa.html](https://8bitconcepts.com/local/camas-wa.html)
- **Portland, OR:** [/local/portland-or.html](https://8bitconcepts.com/local/portland-or.html)
- **Tigard, OR:** [/local/tigard-or.html](https://8bitconcepts.com/local/tigard-or.html)

Each page:
- City-specific hero + intro
- Outcome cards (10–15 hrs/wk, 2–3× capacity, out-execute)
- Local industry list
- Cross-links to neighbor cities + remote engagements
- Lead form posting to `/api/v1/lead` with `source=8bitconcepts-local-{city-slug}` so leads are attributable
- LocalBusiness + ProfessionalService schema with `areaServed` for each city
- `Pacific Northwest` footer line on homepage and `/work-with-us`

Sitemap + llms.txt updated. Submit sitemap to Google Search Console once GSC is verified (currently blocked on Shane).

---

## Channel Plan (Ranked by Cost-to-Lead)

### 1. Local SEO (compounding, free, no Shane action required)
**Status:** Pages live. Now needs:
- Submit sitemap.xml to Google Search Console (Shane: blocked on GSC verification — see CLAUDE.md WIP)
- Submit each /local/* URL to IndexNow (Owl can automate)
- Add **Google Business Profile** for 8bitconcepts (Shane action — needs phone verification + physical-address policy review)
- Backlinks from local directories (Vancouver WA Chamber, Portland Business Alliance, GBA, etc.) → Shane action

### 2. Local Chamber of Commerce membership (paid, high-trust)
Three chambers worth joining:
- **Greater Vancouver Chamber of Commerce** — ~$400-600/yr small-business tier. Member directory listing, monthly networking. Direct access to 1,000+ Clark County SMB owners.
- **Portland Business Alliance** — ~$575+/yr starter. Monthly mixers, member-to-member directory.
- **Tigard Chamber of Commerce** — ~$300/yr. Smaller, intimate; high % of named-decision-maker conversations.
**Combined cost:** ~$1,500/yr for ~3 channels of warm SMB-owner exposure.
**Shane action:** Join, attend one monthly event per chamber, distribute 8bc one-pager.

### 3. Targeted Cold Outreach (low-cost, requires email reputation reset)
Currently blocked by ADB email reputation (per memory `project_aidevboard_email_spam.md`). Options:
- **Use a different sending domain** (e.g. `outreach@shane8bc.com` or personal Gmail) for SMB-targeted cold sends. Brand-new domains with proper SPF/DKIM/DMARC + warming would avoid the ADB-domain reputation taint.
- **Personal email from Shane** — fewer per day, much higher open rate. ~10/day x 60 days = 600 named decision-makers reached.
**Shane action:** Pick approach. If new domain, register + warm. If personal email, no setup needed but Shane time-bound.

### 4. Local Meetups + Workshops (high-trust, high-time)
- **PDX Web & Design** (monthly) — adjacent audience of agency owners who refer SMB clients
- **Portland Tech Crawl** (quarterly) — broader tech, surfaces consulting referrals
- **Vancouver USA Innovation Council** (monthly) — exact target audience
- **Run a free "AI for small business" workshop** — host at a local co-working space (Cowork at Hive Vancouver, Centrl Office Tigard, WeWork Pioneer Square). One workshop/quarter = pipeline.
**Shane action:** Attend, present.

### 5. Local Partner Referral Network
SMB owners trust their existing trusted advisors. Build referral relationships with:
- **Local CPAs/bookkeepers** (we automate AP/AR workflows their clients hate)
- **Business insurance brokers** (we automate underwriting prep, claims triage)
- **Commercial real-estate brokers** (we automate property-research and pre-call prep)
- **Local IT MSPs** (we plug into the ops they're already managing)
**Shane action:** 5 introductory coffees per month, offer revenue share or reciprocal referral.

### 6. Direct Mail / Print (slow but high-trust for SMB)
- Mailchimp postcards → curated SMB list ($500–1,000 per drop)
- Local business journal print ad (Vancouver Business Journal, Portland Business Journal, Tigard-Tualatin Times)
**Shane action:** Lower priority. Run after channels 1–5 have validated.

---

## Industry-First Outreach Targets (Top SMB Categories per City)

### Vancouver, WA + Clark County
- **3PL & logistics** (port-adjacent, dense)
- **Precision manufacturing** (Camas/Vancouver corridor)
- **Healthcare practices** (PeaceHealth ecosystem partners)
- **Specialty trades** (HVAC, electrical, plumbing — high admin overhead)
- **Insurance & financial advisory firms** (10-50 person typical)

### Portland, OR
- **Food/beverage producers** (small batch ~5-50 employees)
- **Creative agencies** (ad, design, video — workflow-heavy)
- **Specialty retail + e-commerce** (Made-in-Portland brands)
- **Healthcare/wellness practices** (chiro, naturopathic, mental health)
- **Independent law firms** (5-20 attorney shops)

### Tigard, OR + SW Metro
- **Wholesale distribution** (food, industrial, specialty)
- **Insurance + financial services** (high density)
- **Specialty contractors** (commercial trades)
- **Professional services** (engineering, architecture)

### Camas, WA
- **Specialty manufacturing**
- **Family-owned trades** (multi-generation, modernizing)
- **Niche professional services**

---

## First-90-Days Outreach Sequence (Shane Action)

**Week 1:** Join Vancouver + Tigard chambers. Set up Google Business Profile.

**Week 2-3:** Identify 50 named SMB owners across the 4 cities (LinkedIn Sales Navigator OR Apollo OR ZoomInfo OR manual research). Prioritize: 5-30 employees, in target industries, owner reachable.

**Week 4-6:** Send 50 personal emails over 3 weeks (well-spaced, not in batch). Lead with research paper hook ("I just published research on the AI compounding gap — thought it might be relevant to [their specific industry]"), close with "20-min intro?" CTA → /local/[city]/lead form.

**Week 7-8:** Attend one Vancouver Chamber event, one Portland Business Alliance event, one Tigard Chamber event. Bring 8bc one-pagers.

**Week 9-12:** Run free "AI for small business" workshop at a local co-working space. Promote via the chambers + LinkedIn.

**Goal:** 5 booked discovery calls per month by month 3. Conversion target: 20% to paid engagement (1 client/mo to start).

---

## Asset Checklist (What Shane Needs to Pull Together)

**Already shipped (Owl):**
- Geo landing pages
- Lead form + Discord notification pipeline (loud ping on every submit)
- Schema markup for local SEO
- Sitemap + llms.txt entries
- Footer cross-links to all PNW pages

**Shane needs to build:**
- [ ] Google Business Profile (claim + verify)
- [ ] 8bc one-pager PDF (printable, for chamber events)
- [ ] Cal.com or Calendly account → wire into "Book a 30-min intro call" CTAs (currently form-based; calendar would convert higher)
- [ ] Decide: personal email vs. new outreach domain for cold SMB sends
- [ ] Curated 50-name SMB target list (CSV with name, company, role, email, industry, city)
- [ ] Chamber memberships (Vancouver, Portland, Tigard)

**Owl can scaffold next:**
- IndexNow auto-submission for the new local pages
- Per-city case-study placeholder pages (1 fictional/composite each, swap real ones in as engagements close)
- LinkedIn post drafts (when Shane creates business LinkedIn page)
- Email outreach templates for each industry vertical

---

## Tracking

Every lead form on /local/* posts to `aidevboard.com/api/v1/lead` with `source=8bitconcepts-local-{city-slug}`. Filter Discord pings by tag, query the leads DB by source to measure each city's conversion:

```bash
curl -s 'https://aidevboard.com/api/v1/admin/leads?limit=200' \
  -H "Authorization: Bearer $(security find-generic-password -a foundry -s aidevboard-admin-key -w)" \
  | jq '.leads | group_by(.source) | map({source: .[0].source, count: length})'
```

Discord channel will get `🔥🔥 NEW CONSULTING LEAD (8bitconcepts-local-vancouver-wa)` style pings — instant visibility per city.

---

## Next Owl Iteration

After Shane validates the geo pages with traffic:
1. Auto-IndexNow submission for /local/* on every change (already supported by infra — needs script)
2. Per-city case study templates ready to populate as engagements close
3. Email outreach templates per industry vertical (insurance, manufacturing, healthcare, etc.)
4. PNW-specific research paper variant ("AI in PNW small business: what 5,000 hiring posts tell us about local readiness") — uses existing aidevboard data filtered to PNW companies

