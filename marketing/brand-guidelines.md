# 8bitConcepts Brand Identity Guidelines

## Brand Overview
8bitConcepts is an AI and automation agency that builds and maintains custom AI systems for small and mid-size businesses. We position ourselves as the technical partner that handles everything — from design to deployment to ongoing maintenance.

---

## Brand Voice & Tone

### Core Attributes
- **Expert but approachable**: We know AI deeply, but we explain it like humans
- **Practical, not theoretical**: Every claim is backed by real data (40+ systems, 97% retention, $54K avg savings)
- **Confident but humble**: We let results speak louder than hype
- **Direct and clear**: No jargon, no fluff, no enterprise-speak

### Voice Principles
1. **Lead with value**: Every piece of content answers "what's in it for them?"
2. **Show, don't tell**: Use specific examples and real client outcomes
3. **Be the guide**: Position client as hero, 8bitConcepts as the trusted guide
4. **Action-oriented**: End with clear next steps

### Words We Use
- Build and maintain (not "develop and support")
- Custom systems (not "solutions")
- Save time and money (not "drive efficiency")
- Cancel anytime, keep everything (risk reversal)

### Words We Avoid
- Synergy, leverage, optimize (buzzwords)
- "AI-powered" as a descriptor (everyone says this)
- "Revolutionary," "game-changing" (hype)
- Enterprise jargon ("stakeholder alignment," "paradigm shift")

### Tone by Channel
| Channel | Tone |
|---------|------|
| Website | Confident, professional, benefit-focused |
| Blog | Educational, practical, data-backed |
| Social | Conversational, punchy, visual |
| Email | Personal, helpful, direct |
| Ads | Problem-agitation-solution, specific numbers |

---

## Color System

### Primary Palette
```css
--primary: #5093AD;        /* Main brand color - ocean teal */
--primary-light: #74D5FA;  /* Accents, highlights */
--primary-dark: #3D7085;   /* Hover states, emphasis */
--primary-bg: #EDF6FA;     /* Backgrounds, cards */
```

### Secondary/Accent
```css
--accent: #63B5D6;         /* Mid-tone teal */
--deep: #2A4E5C;           /* Dark teal for headers, savings banner */
```

### Neutral Colors
```css
--text: #1e293b;           /* Primary text - slate-800 */
--text-light: #64748b;     /* Secondary text - slate-500 */
--text-lighter: #94a3b8;   /* Subtle text - slate-400 */
--bg: #f5f5f5;            /* Page background */
--bg-alt: #f8fafc;        /* Alternate section bg */
--border: #e2e8f0;        /* Borders, dividers */
```

### Usage Guidelines
- **Hero sections**: Primary bg gradient (#EDF6FA to #f5f5f5)
- **CTA buttons**: --primary (#5093AD), hover to --primary-dark
- **Savings/impact banners**: --deep gradient (#2A4E5C to #5093AD) with white text
- **Cards**: White or --bg with --border
- **Links**: --primary, underline on hover

---

## Typography

### Font Family
- **Primary**: Inter (Google Fonts)
- **Weights used**: 300, 400, 500, 600, 700, 800
- **Fallback**: -apple-system, BlinkMacSystemFont, sans-serif

### Type Scale
| Element | Size | Weight | Line Height |
|---------|------|--------|-------------|
| H1 (Hero) | clamp(2.5rem, 5.5vw, 4rem) | 800 | 1.15 |
| H2 (Section) | clamp(2rem, 4vw, 3rem) | 800 | 1.15 |
| H3 (Card titles) | 1.2rem | 700 | 1.3 |
| Body | 1rem (16px) | 400 | 1.6 |
| Body large | 1.15rem | 400 | 1.7 |
| Small/Caption | 0.9rem | 400 | 1.65 |
| Label | 0.8rem | 700 | 1.4 |

### Typography Rules
- Headlines use tight letter-spacing (-0.02em to -0.03em)
- Section labels are uppercase with 0.08em letter-spacing
- Body text never goes below 16px for readability
- Use font-weight 600-800 for emphasis, not just color

---

## Visual Style

### Logo
- SVG-based 8-bit style owl/icon in primary colors
- Appears in nav, favicon, and social sharing
- Maintain clear space around logo (minimum 20px)

### Imagery Style
- **Abstract UI illustrations**: SVG-based, isometric or flat design
- **Color scheme**: Matches brand palette (teals, blues, subtle gradients)
- **Subject matter**: Dashboards, workflows, chat interfaces, flow diagrams
- **No stock photos**: All visuals are custom SVG illustrations

### Iconography
- Simple line icons or filled icons consistent with brand colors
- Icon containers: 56px circles with --primary-bg fill
- Stroke width: 1.5-2px
- Icon colors: --primary, --primary-light, --accent

### Layout Principles
- **Max-width**: 1200px for content
- **Section padding**: 6rem vertical (4rem on mobile)
- **Card grid**: CSS Grid with minmax(320px, 1fr) or similar
- **Border radius**: 12px (standard), 20px (large cards/sections)
- **Shadows**: Subtle, layered (0 4px 24px rgba(0,0,0,0.06))

---

## Messaging Framework

### Positioning Statement
For small and mid-size businesses who waste hours on repetitive work, 8bitConcepts is the AI automation agency that builds and maintains custom systems — so you save time and money without hiring technical staff.

### Key Messages
1. **We build AND maintain**: "You never touch a line of code"
2. **Custom, not cookie-cutter**: "100% built for your workflows"
3. **Risk-free**: "Cancel anytime, keep everything we built"
4. **Proven ROI**: "$54K average annual savings, 30-day payback"

### Proof Points
- 40+ systems delivered
- 97% client retention rate
- $54K average annual savings per client
- 12,000+ hours saved for clients
- 2-6 week typical delivery time

### Taglines
- Primary: "We build the AI systems so you don't have to."
- Secondary: "Build once. Maintain forever."
- Supporting: "Your technical team, without the headcount."

---

## Content Patterns

### Blog Post Structure
1. Problem statement (relatable pain point)
2. Data or examples (show the scope)
3. Solution categories (what options exist)
4. Comparison/analysis (data-backed)
5. Recommendation (specific guidance)
6. CTA (consultation or related content)

### Social Post Structure
1. Hook (contrarian take or specific number)
2. Quick context (1-2 sentences)
3. Key insight or takeaway
4. Engagement prompt or CTA

### Email Structure
1. Personal greeting
2. Relevant insight or tip
3. Social proof or example
4. Soft CTA (reply, read, book)

---

## Application Examples

### Button Text
- ✅ "Book a Free Consultation"
- ✅ "Get Started"
- ✅ "See Our Work"
- ❌ "Submit" (too generic)
- ❌ "Learn More" (weak CTA)

### Headline Formulas
- "[Outcome] without [objection]" → "Save 20 hours a week without hiring"
- "[Number] [thing] that [result]" → "3 automations that paid for themselves in 30 days"
- "Stop [pain], start [gain]" → "Stop drowning in admin, start closing deals"

### Social Proof Format
"[Specific outcome] in [timeframe] for [client type]" 
→ "Cut lead response time from 4 hours to 4 minutes for a financial services firm"

---

## File Organization
```
8bitconcepts/
├── marketing/
│   ├── brand-guidelines.md (this file)
│   ├── social-posts/
│   ├── email-sequences/
│   └── ad-creatives/
├── blog/
├── assets/
│   ├── logos/
│   ├── icons/
│   └── illustrations/
```

---

## Version History
- 1.0 - Initial brand guidelines (2026-02-16)
