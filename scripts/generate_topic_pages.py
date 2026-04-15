#!/usr/bin/env python3
"""
Generate programmatic SEO topic cluster pages for 8bitconcepts.

Each topic page aggregates 2-4 related research papers with:
- Unique H1 + meta description targeting a long-tail search query
- Original 150-word intro
- Linked paper cards
- Schema.org CollectionPage JSON-LD
- Subscribe CTA
- Internal links back to homepage

Output: /topic/{slug}.html
Updates: sitemap.xml, llms.txt
"""

import json, os, re
from pathlib import Path

ROOT = Path(__file__).parent.parent
TOPICS = [
    {
        "slug": "agentic-ai",
        "title": "Agentic AI Research — What Actually Works in Production",
        "h1": "Agentic AI in Production",
        "meta_desc": "Research on production agentic AI: governance gaps, handoff patterns, and the maturity ladder most teams skip. Six papers on what separates shipping agentic systems from pilots.",
        "intro": "Agentic AI means systems that take autonomous action on behalf of humans — agents that call APIs, mutate databases, and make irreversible decisions without a human in the loop for every step. The gap between \"we have agents\" and \"our agents compound in production\" is not prompting skill. It is systems engineering: versioned skills, shift-aware handoffs, evaluation infrastructure, and governance that was not designed for generative AI. The research below covers the specific patterns we see in engineering teams that ship agentic AI without incident — and the patterns that predictably produce incidents.",
        "papers": [
            "beyond-the-prompt",
            "shift-handoff-intelligence",
            "the-agentic-accountability-gap",
            "the-guardrails-gap",
        ],
        "tags": ["agentic-ai", "ai-agents", "production-ai"],
    },
    {
        "slug": "enterprise-ai-roi",
        "title": "Enterprise AI ROI Research — Why Most Programs Don't Compound",
        "h1": "Enterprise AI ROI",
        "meta_desc": "McKinsey says 88% use AI, 6% see returns. Research on the actual cost math, the metrics that predict value, and why mandates alone don't move the P&L.",
        "intro": "Enterprise AI ROI is not a prompting problem. It is an organizational and measurement problem. Model API costs are 10 to 20 percent of what AI actually costs to deploy; the remaining 80 percent is infrastructure, integration, evaluation, and maintenance that most budgets silently exclude. Teams that measure AI on usage or cost avoidance wonder why the CFO cannot see the value; teams that measure it on irreversible-decisions-per-quarter build a story the P&L accepts. The papers below are the framework we use with late-stage clients who need to show returns inside a single fiscal year.",
        "papers": [
            "the-integration-tax",
            "the-six-percent",
            "the-measurement-problem",
            "the-mandate-trap",
        ],
        "tags": ["ai-roi", "enterprise-ai", "ai-adoption"],
    },
    {
        "slug": "ai-governance",
        "title": "AI Governance Research — Where Generative Frameworks Fail for Agents",
        "h1": "AI Governance",
        "meta_desc": "Governance frameworks built for generative AI break the moment agents act autonomously. Research on guardrails, accountability gaps, and compliance for production agents.",
        "intro": "Most corporate AI governance policies were written in 2023 and 2024 for generative AI — models that produced text a human then used or discarded. Agentic AI breaks the implicit assumption those policies made. When an agent makes a decision and acts on it without a human in the loop, the question of who is accountable when the decision was wrong is not answered by existing governance. The research below covers the specific gaps in guardrails, audit trails, and accountability that we see at companies running agents in production — and the controls that actually work in place of the controls that do not.",
        "papers": [
            "the-guardrails-gap",
            "the-agentic-accountability-gap",
            "the-mandate-trap",
        ],
        "tags": ["ai-governance", "ai-compliance", "ai-safety"],
    },
    {
        "slug": "ai-organizational-design",
        "title": "AI Organizational Design Research — Where AI Should Report",
        "h1": "AI Organizational Design",
        "meta_desc": "The under-discussed predictor of AI outcomes: where AI reports in the org chart. Research on structure, mandates, and why bottom-up adoption outperforms top-down memos.",
        "intro": "Where AI sits in the org chart predicts outcomes more reliably than which model a team uses. Companies that pull AI out from under IT or Engineering and give it a P&L owner consistently compound faster than companies that treat AI as a tools layer. The reason is organizational authority, not technical capability: AI programs that have to negotiate for resources across three VPs every quarter rarely survive the second one. The research below covers the structural patterns we see separating the AI programs that are compounding from the ones that are plateauing.",
        "papers": [
            "the-org-chart-problem",
            "the-mandate-trap",
            "the-six-percent",
        ],
        "tags": ["ai-strategy", "ai-leadership", "organizational-design"],
    },
    {
        "slug": "ai-reliability-evaluation",
        "title": "AI Reliability & Evaluation Research — Measuring What Actually Matters",
        "h1": "AI Reliability & Evaluation",
        "meta_desc": "Most AI systems have no systematic ground truth. Research on hallucination budgets, measurement frameworks, and the evaluation discipline that separates production from pilot.",
        "intro": "AI reliability is not a model problem. It is an evaluation problem. Most teams cannot measure whether their AI system is still correct after a model update, which means they do not know when degradation started and they cannot tell the business what their error rate actually is. The research below covers the evaluation frameworks and measurement patterns that we see in teams running AI in regulated or irreversible-decision contexts — where being wrong without knowing it is the failure mode that ends careers.",
        "papers": [
            "the-hallucination-budget",
            "the-measurement-problem",
            "the-guardrails-gap",
        ],
        "tags": ["ai-reliability", "ai-evaluation", "ai-metrics"],
    },
]

PAPER_META = {
    "beyond-the-prompt": "Moving past prompt engineering to systematic AI integration.",
    "shift-handoff-intelligence": "Maintaining context across AI system transitions and human-agent handoffs.",
    "the-agentic-accountability-gap": "Why governance frameworks built for generative AI fail for agentic systems.",
    "the-guardrails-gap": "Why enterprise AI safety frameworks fail when agents act autonomously.",
    "the-integration-tax": "Hidden costs of integrating AI into existing workflows and systems.",
    "the-six-percent": "The small fraction of organizations getting real value from AI — and what they do differently.",
    "the-measurement-problem": "How enterprises measure AI ROI and where standard metrics fail.",
    "the-mandate-trap": "Top-down AI mandates vs. bottom-up adoption — which actually drives results.",
    "the-org-chart-problem": "Why organizational structure determines AI adoption outcomes.",
    "the-hallucination-budget": "Quantifying the cost of AI hallucinations and mitigation strategies.",
}

PAPER_TITLES = {
    "beyond-the-prompt": "Beyond the Prompt",
    "shift-handoff-intelligence": "Shift Handoff Intelligence",
    "the-agentic-accountability-gap": "The Agentic Accountability Gap",
    "the-guardrails-gap": "The Guardrails Gap",
    "the-integration-tax": "The Integration Tax",
    "the-six-percent": "The Six Percent",
    "the-measurement-problem": "The Measurement Problem",
    "the-mandate-trap": "The Mandate Trap",
    "the-org-chart-problem": "The Org Chart Problem",
    "the-hallucination-budget": "The Hallucination Budget",
}


def render(topic):
    papers_json = [
        {"@type": "Article", "name": PAPER_TITLES[s], "url": f"https://8bitconcepts.com/research/{s}.html"}
        for s in topic["papers"]
    ]
    ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": topic["h1"],
        "description": topic["meta_desc"],
        "url": f"https://8bitconcepts.com/topic/{topic['slug']}.html",
        "isPartOf": {"@type": "WebSite", "name": "8bitconcepts", "url": "https://8bitconcepts.com"},
        "hasPart": papers_json,
        "about": topic["tags"],
    }, indent=2)
    paper_cards = "\n".join(
        f'''      <a class="card" href="/research/{s}.html">
        <div class="card-title">{PAPER_TITLES[s]}</div>
        <div class="card-desc">{PAPER_META[s]}</div>
      </a>'''
        for s in topic["papers"]
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{topic['title']}</title>
<meta name="description" content="{topic['meta_desc']}" />
<link rel="canonical" href="https://8bitconcepts.com/topic/{topic['slug']}.html" />
<meta property="og:type" content="website" />
<meta property="og:title" content="{topic['title']}" />
<meta property="og:description" content="{topic['meta_desc']}" />
<meta property="og:url" content="https://8bitconcepts.com/topic/{topic['slug']}.html" />
<meta name="twitter:card" content="summary" />
<meta name="twitter:title" content="{topic['title']}" />
<meta name="twitter:description" content="{topic['meta_desc']}" />
<link rel="alternate" type="application/rss+xml" href="/feed.xml" title="8bitconcepts Research" />
<script type="application/ld+json">
{ld}
</script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0d0d0e;color:#e8e8e9;font-family:'Inter',system-ui,sans-serif;line-height:1.7;padding:40px 20px;}}
.wrap{{max-width:760px;margin:0 auto;}}
h1{{font-size:38px;letter-spacing:-0.02em;margin-bottom:16px;color:#fff;}}
.eyebrow{{font-size:12px;text-transform:uppercase;letter-spacing:0.2em;color:#d97757;margin-bottom:12px;}}
.intro{{font-size:18px;color:#c5c5c9;margin-bottom:36px;}}
.section-title{{font-size:22px;margin:40px 0 16px;color:#fff;}}
.grid{{display:grid;grid-template-columns:1fr;gap:14px;}}
.card{{display:block;padding:20px;background:#111214;border:1px solid rgba(255,255,255,0.07);border-radius:8px;text-decoration:none;color:inherit;transition:border-color .15s;}}
.card:hover{{border-color:#d97757;}}
.card-title{{font-size:17px;font-weight:600;color:#fff;margin-bottom:6px;}}
.card-desc{{font-size:15px;color:#8b8d91;}}
.nav-back{{display:inline-block;margin-bottom:24px;color:#d97757;text-decoration:none;font-size:14px;}}
.cta{{margin-top:48px;padding:24px;background:#111214;border-left:3px solid #d97757;border-radius:6px;}}
.cta h2{{font-size:18px;margin-bottom:8px;color:#fff;}}
.cta p{{color:#c5c5c9;margin-bottom:14px;font-size:15px;}}
.cta form{{display:flex;gap:8px;flex-wrap:wrap;}}
.cta input{{flex:1;min-width:220px;padding:10px 14px;border:1px solid #333;background:#0d0d0e;color:#fff;border-radius:6px;font-size:15px;}}
.cta button{{padding:10px 20px;background:#d97757;color:#fff;border:none;border-radius:6px;font-weight:600;cursor:pointer;}}
#sub-status{{margin-top:10px;font-size:14px;min-height:1em;}}
footer{{margin-top:56px;padding-top:24px;border-top:1px solid rgba(255,255,255,0.07);font-size:13px;color:#8b8d91;}}
footer a{{color:#d97757;text-decoration:none;}}
</style>
</head>
<body>
<div class="wrap">
  <a class="nav-back" href="/">← 8bitconcepts</a>
  <div class="eyebrow">Research Topic</div>
  <h1>{topic['h1']}</h1>
  <p class="intro">{topic['intro']}</p>

  <div class="section-title">Research Papers</div>
  <div class="grid">
{paper_cards}
  </div>

  <div class="cta">
    <h2>Get new research by email</h2>
    <p>Two papers a week on what's actually happening inside enterprise AI programs. No promo, no hype.</p>
    <form onsubmit="return sub8bc(event)">
      <input type="email" name="email" placeholder="you@company.com" required />
      <button type="submit">Subscribe</button>
    </form>
    <p id="sub-status"></p>
    <p style="margin-top:8px;font-size:13px;color:#5a5c61;">Prefer a reader? <a href="/feed.xml" style="color:#d97757;">RSS feed</a>.</p>
  </div>
  <script>
  async function sub8bc(e){{e.preventDefault();const f=e.target;const email=f.email.value.trim();const s=document.getElementById('sub-status');s.textContent='Subscribing...';try{{const r=await fetch('https://aidevboard.com/api/v1/subscribe',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email,tags:['8bitconcepts-research'],frequency:'weekly'}})}});if(r.ok){{s.textContent='Subscribed.';s.style.color='#4ade80';f.reset();}}else{{s.textContent='Error. Email hello@8bitconcepts.com instead.';s.style.color='#f87171';}}}}catch(err){{s.textContent='Network error.';s.style.color='#f87171';}}return false;}}
  </script>

  <footer>
    <p>&copy; 2026 8bitconcepts — Enterprise AI strategy research</p>
    <p style="margin-top:6px;">More topics: <a href="/topic/agentic-ai.html">Agentic AI</a> · <a href="/topic/enterprise-ai-roi.html">Enterprise AI ROI</a> · <a href="/topic/ai-governance.html">AI Governance</a> · <a href="/topic/ai-organizational-design.html">Org Design</a> · <a href="/topic/ai-reliability-evaluation.html">Reliability &amp; Evaluation</a></p>
  </footer>
</div>
</body>
</html>
"""


def update_sitemap():
    path = ROOT / "sitemap.xml"
    with open(path) as f:
        content = f.read()
    entries = "\n".join(
        f"  <url><loc>https://8bitconcepts.com/topic/{t['slug']}.html</loc><changefreq>monthly</changefreq><priority>0.8</priority></url>"
        for t in TOPICS
    )
    if "/topic/" not in content:
        content = content.replace("</urlset>", f"{entries}\n</urlset>")
        with open(path, "w") as f:
            f.write(content)
        print(f"sitemap.xml: added {len(TOPICS)} topic URLs")
    else:
        print("sitemap.xml: topic URLs already present (skip)")


def update_llms_txt():
    path = ROOT / "llms.txt"
    with open(path) as f:
        content = f.read()
    if "## Research Topics" in content:
        print("llms.txt: topic section already present (skip)")
        return
    topic_section = "\n## Research Topics\n\n" + "\n".join(
        f"- [{t['h1']}](https://8bitconcepts.com/topic/{t['slug']}.html): {t['meta_desc']}"
        for t in TOPICS
    ) + "\n"
    content = content.replace("\n## Programmatic Access", topic_section + "\n## Programmatic Access")
    with open(path, "w") as f:
        f.write(content)
    print(f"llms.txt: added Research Topics section with {len(TOPICS)} pages")


def main():
    outdir = ROOT / "topic"
    outdir.mkdir(exist_ok=True)
    for t in TOPICS:
        (outdir / f"{t['slug']}.html").write_text(render(t))
        print(f"+ topic/{t['slug']}.html")
    update_sitemap()
    update_llms_txt()
    print(f"\n{len(TOPICS)} topic pages generated.")


if __name__ == "__main__":
    main()
