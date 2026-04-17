#!/usr/bin/env python3
"""
Generates /research/overview.html - the master atlas of all 8bitconcepts research papers.

Scans /research/*.html, extracts title / meta description / word-count / datePublished / tags,
and produces a static overview page with:
  - header + intro
  - all-papers grid with reading-time estimates
  - topic index (papers grouped by tag)
  - three curated reading paths
  - subscribe CTA (wired to aidevboard /api/v1/subscribe)
  - CollectionPage JSON-LD
  - OG / Twitter meta

Run from the repo root or anywhere:  python3 tools/generate-overview.py
Auto-updates whenever new research papers ship.
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
RESEARCH_DIR = REPO / "research"
OUT_PATH = RESEARCH_DIR / "overview.html"
FEED_SCRIPT = REPO / "tools" / "generate-research-feed.py"
OG_IMAGE = "https://8bitconcepts.com/og-default.png"

SKIP = {"index.html", "overview.html"}

# Curated card descriptions (fallbacks if a paper doesn't yet ship its own summary).
# Keep in sync with /research/index.html; indexed by slug.
CURATED_DESC: dict[str, str] = {
    "the-integration-tax": "Model API costs are 10-20% of what AI actually costs to ship. Where the other 80% goes.",
    "beyond-the-prompt": "The teams shipping reliable production agentic systems are not prompting harder - they moved through a specific engineering maturity ladder.",
    "the-six-percent": "88% of organizations use AI. Only 6% see meaningful returns. What McKinsey found in 2,000 companies across 105 countries.",
    "the-mandate-trap": "Shopify's AI mandate worked. Duolingo's didn't. Companies copying the Shopify memo template are learning the wrong lesson.",
    "the-measurement-problem": "A company ran an AI system for eight months before discovering four months of silent degradation. Most have no better detection mechanism.",
    "the-org-chart-problem": "AI transformation fails because of where it sits in the org chart. Every placement encodes a ceiling.",
    "shift-handoff-intelligence": "100% information retention with AI-generated shift briefings vs. 40-60% with verbal handoffs. The pattern-detection gap is where preventable failures originate.",
    "the-guardrails-gap": "Engineering teams spent 2023 and 2024 obsessing over what AI would say. In 2026, the threat has shifted - agentic systems are now taking action.",
    "the-hallucination-budget": "Most engineering teams ship LLM features with less testing rigor than they apply to a login form. Production hallucinations land on customer trust and legal risk.",
    "the-agentic-accountability-gap": "Enterprise teams spent three years learning how to stop AI from saying the wrong thing. Then they handed those same systems write-access to production.",
    "q2-2026-ai-hiring-snapshot": "Live snapshot: 8,618 AI/ML engineering roles across 513 companies, $213k median, 599 new this week. OpenAI leads with 336 open roles. Full breakdown by skill, salary, workplace.",
    "q2-2026-mcp-ecosystem-health": "5,578 agent-ready sites indexed, only 575 (10.3%) pass a live JSON-RPC handshake. Category breakdown, newly-verified servers, and the regulated verticals still waiting to be built.",
    "q2-2026-ai-compensation-by-skill": "Research roles pay a $42k premium over generative-AI roles ($274k vs $231k avg), even though generative-AI has 2.5x more openings. Top-paying skill tags, most in-demand tags, sweet-spot skills, and salary distribution across 3,402 salary-disclosed roles.",
    "q2-2026-remote-vs-onsite-ai-hiring": "Hybrid AI/ML roles pay a ~$35k premium over remote+onsite ($253k vs $218k). 55% of AI engineering roles still require full onsite attendance. Workplace mix, hybrid-premium analysis, onsite-heavy and remote-friendly companies.",
    "q2-2026-entry-level-ai-gap": "Only ~7% of AI/ML engineering roles are open to juniors. For every entry-level opening there are ~10 senior-plus roles -- the tightest junior-to-senior ratio in tech. Experience-level mix, why the squeeze exists, companies still hiring juniors, and the career-switcher playbook.",
}

# Tag enrichment per slug (mirrors /research/index.html + research.json).
SLUG_TAGS: dict[str, list[str]] = {
    "the-integration-tax": ["integration", "tco", "enterprise"],
    "beyond-the-prompt": ["llm", "engineering", "systems-design"],
    "the-six-percent": ["adoption", "case-studies", "best-practices"],
    "the-mandate-trap": ["adoption", "leadership", "strategy"],
    "the-measurement-problem": ["roi", "metrics", "evaluation"],
    "the-org-chart-problem": ["adoption", "organizational-design", "change-management"],
    "shift-handoff-intelligence": ["agents", "context", "operations"],
    "the-guardrails-gap": ["agents", "safety", "governance"],
    "the-hallucination-budget": ["llm", "reliability", "evaluation"],
    "the-agentic-accountability-gap": ["agents", "governance", "accountability"],
    "q2-2026-ai-hiring-snapshot": ["hiring", "market-data", "live-data"],
    "q2-2026-mcp-ecosystem-health": ["mcp", "agents", "live-data", "ecosystem"],
    "q2-2026-ai-compensation-by-skill": ["compensation", "salary", "market-data", "live-data"],
    "q2-2026-remote-vs-onsite-ai-hiring": ["workplace", "remote", "hybrid", "market-data", "live-data"],
    "q2-2026-entry-level-ai-gap": ["hiring", "entry-level", "career", "market-data", "live-data"],
}

# Topic index groupings. Each topic collects slugs that fit.
TOPIC_INDEX: list[tuple[str, str, list[str]]] = [
    (
        "Enterprise AI ROI",
        "Cost, metrics, and the gap between adoption and returns.",
        ["the-six-percent", "the-integration-tax", "the-measurement-problem", "the-mandate-trap"],
    ),
    (
        "AI Governance & Accountability",
        "Guardrails, compliance, and who owns agent actions.",
        ["the-guardrails-gap", "the-agentic-accountability-gap", "the-hallucination-budget"],
    ),
    (
        "Multi-Agent & Production Systems",
        "What separates shipping agentic systems from pilots.",
        ["beyond-the-prompt", "shift-handoff-intelligence", "the-guardrails-gap"],
    ),
    (
        "Organizational Design",
        "Where AI reports in the org chart and why that predicts outcomes.",
        ["the-org-chart-problem", "the-mandate-trap", "the-six-percent"],
    ),
    (
        "Reliability & Evaluation",
        "Measurement, eval, and detecting silent degradation.",
        ["the-measurement-problem", "the-hallucination-budget", "beyond-the-prompt"],
    ),
    (
        "Market & Hiring Data",
        "Live snapshots of where AI hiring, compensation, and agent infrastructure are moving.",
        ["q2-2026-ai-hiring-snapshot", "q2-2026-ai-compensation-by-skill", "q2-2026-remote-vs-onsite-ai-hiring", "q2-2026-entry-level-ai-gap", "q2-2026-mcp-ecosystem-health"],
    ),
]

# Three curated reading paths.
READING_PATHS: list[tuple[str, str, list[str]]] = [
    (
        "Starting out with enterprise AI",
        "If your team is early in the curve - start with the economics, then the organizational failure modes, then the measurement discipline that separates pilots from production.",
        ["the-six-percent", "the-mandate-trap", "the-org-chart-problem", "the-measurement-problem"],
    ),
    (
        "Deploying multi-agent systems in production",
        "The teams actually shipping agentic systems have moved past prompting. Read the engineering ladder, then the operational handoff patterns, then the reliability discipline underneath.",
        ["beyond-the-prompt", "shift-handoff-intelligence", "the-hallucination-budget", "the-integration-tax"],
    ),
    (
        "AI governance and compliance",
        "Frameworks built for generative AI break the moment agents act. Start with the shift, then the accountability gap, then the reliability floor you need under it.",
        ["the-guardrails-gap", "the-agentic-accountability-gap", "the-hallucination-budget"],
    ),
]

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
META_DESC_RE = re.compile(
    r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']\s*/?>',
    re.IGNORECASE | re.DOTALL,
)
DATE_PUB_RE = re.compile(r'"datePublished"\s*:\s*"([0-9]{4}-[0-9]{2}-[0-9]{2})"')
TAG_STRIP_RE = re.compile(r"<[^>]+>")


def clean_title(raw: str) -> str:
    t = html.unescape(raw.strip())
    # Papers use "Title -- 8bitconcepts" - strip the suffix.
    for sep in (" -- 8bitconcepts", " — 8bitconcepts", " | 8bitconcepts"):
        if t.endswith(sep):
            t = t[: -len(sep)]
            break
    return t.strip()


def estimate_reading_time(html_text: str) -> int:
    # Strip tags then words.
    text = TAG_STRIP_RE.sub(" ", html_text)
    words = len(text.split())
    minutes = max(1, round(words / 250))
    return minutes


def parse_paper(path: Path) -> dict[str, Any] | None:
    slug = path.stem
    if path.name in SKIP:
        return None
    raw = path.read_text(encoding="utf-8", errors="ignore")

    title_m = TITLE_RE.search(raw)
    desc_m = META_DESC_RE.search(raw)
    date_m = DATE_PUB_RE.search(raw)

    title = clean_title(title_m.group(1)) if title_m else slug.replace("-", " ").title()
    meta_desc = html.unescape(desc_m.group(1)).strip() if desc_m else ""
    # Prefer curated short summary if available (matches /research/index).
    summary = CURATED_DESC.get(slug) or meta_desc
    # Two-line cap: trim aggressively.
    if len(summary) > 220:
        summary = summary[:217].rsplit(" ", 1)[0] + "..."

    date_iso = date_m.group(1) if date_m else "2026-04-01"
    reading_min = estimate_reading_time(raw)
    tags = SLUG_TAGS.get(slug, [])

    return {
        "slug": slug,
        "url": f"/research/{path.name}",
        "abs_url": f"https://8bitconcepts.com/research/{path.name}",
        "title": title,
        "summary": summary,
        "reading_min": reading_min,
        "date_iso": date_iso,
        "tags": tags,
    }


def load_papers() -> list[dict[str, Any]]:
    papers: list[dict[str, Any]] = []
    for p in sorted(RESEARCH_DIR.glob("*.html")):
        parsed = parse_paper(p)
        if parsed:
            papers.append(parsed)
    return papers


def he(s: str) -> str:
    return html.escape(s, quote=True)


def render_card(p: dict[str, Any]) -> str:
    tags_html = "".join(
        f'<span class="tag">{he(t)}</span>' for t in p["tags"]
    )
    date_display = datetime.strptime(p["date_iso"], "%Y-%m-%d").strftime("%b %Y")
    return f"""      <a class="card" href="{he(p['url'])}">
        <div class="card-title">{he(p['title'])}</div>
        <div class="card-desc">{he(p['summary'])}</div>
        <div class="card-meta">
          <span class="meta-item">{p['reading_min']} min read</span>
          <span class="meta-sep">&middot;</span>
          <span class="meta-item">{date_display}</span>
        </div>
        <div class="card-tags">{tags_html}</div>
      </a>"""


def render_topic_block(title: str, blurb: str, slugs: list[str], by_slug: dict[str, dict[str, Any]]) -> str:
    items = []
    for s in slugs:
        p = by_slug.get(s)
        if not p:
            continue
        items.append(
            f'<li><a href="{he(p["url"])}">{he(p["title"])}</a>'
            f' <span class="mini-meta">{p["reading_min"]} min</span></li>'
        )
    if not items:
        return ""
    return f"""    <div class="topic">
      <h3 class="topic-title">{he(title)}</h3>
      <p class="topic-blurb">{he(blurb)}</p>
      <ul class="topic-list">
{chr(10).join(items)}
      </ul>
    </div>"""


def render_path_block(idx: int, title: str, blurb: str, slugs: list[str], by_slug: dict[str, dict[str, Any]]) -> str:
    steps = []
    for i, s in enumerate(slugs, start=1):
        p = by_slug.get(s)
        if not p:
            continue
        steps.append(
            f"""        <li>
          <div class="step-num">{i}</div>
          <div class="step-body">
            <a class="step-title" href="{he(p['url'])}">{he(p['title'])}</a>
            <div class="step-desc">{he(p['summary'])}</div>
            <div class="step-meta">{p['reading_min']} min read</div>
          </div>
        </li>"""
        )
    return f"""    <div class="path">
      <div class="path-eyebrow">Path {idx}</div>
      <h3 class="path-title">{he(title)}</h3>
      <p class="path-blurb">{he(blurb)}</p>
      <ol class="path-steps">
{chr(10).join(steps)}
      </ol>
    </div>"""


def build_jsonld(papers: list[dict[str, Any]]) -> str:
    has_part = [
        {
            "@type": "ScholarlyArticle",
            "name": p["title"],
            "headline": p["title"],
            "url": p["abs_url"],
            "datePublished": p["date_iso"],
            "keywords": ", ".join(p["tags"]),
            "author": {"@type": "Organization", "name": "8bitconcepts"},
        }
        for p in papers
    ]
    doc = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "8bitconcepts Research Atlas - All Papers, Topics, and Reading Paths",
        "description": "Master map of every 8bitconcepts research paper on enterprise AI - organized by topic, with curated reading paths for practitioners.",
        "url": "https://8bitconcepts.com/research/overview.html",
        "isPartOf": {"@type": "WebSite", "name": "8bitconcepts", "url": "https://8bitconcepts.com"},
        "hasPart": has_part,
    }
    return json.dumps(doc, indent=2)


def build_html(papers: list[dict[str, Any]]) -> str:
    by_slug = {p["slug"]: p for p in papers}
    cards_html = "\n".join(render_card(p) for p in papers)
    topics_html = "\n".join(
        render_topic_block(t, b, slugs, by_slug) for t, b, slugs in TOPIC_INDEX
    )
    paths_html = "\n".join(
        render_path_block(i + 1, t, b, slugs, by_slug)
        for i, (t, b, slugs) in enumerate(READING_PATHS)
    )
    jsonld = build_jsonld(papers)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = len(papers)

    title = "8bitconcepts Research Atlas - the practitioner's map of enterprise AI"
    desc = (
        "Master index of every 8bitconcepts research paper on enterprise AI, "
        "organized by topic with curated reading paths. Free. No vendor sponsorship. No paywall."
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<meta name="referrer" content="strict-origin-when-cross-origin" />
<meta name="color-scheme" content="dark light" />
<title>{he(title)}</title>
<meta name="description" content="{he(desc)}" />
<link rel="canonical" href="https://8bitconcepts.com/research/overview.html" />

<!-- Open Graph / Twitter -->
<meta property="og:type" content="website" />
<meta property="og:site_name" content="8bitconcepts" />
<meta property="og:title" content="{he(title)}" />
<meta property="og:description" content="{he(desc)}" />
<meta property="og:url" content="https://8bitconcepts.com/research/overview.html" />
<meta property="og:image" content="{OG_IMAGE}" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{he(title)}" />
<meta name="twitter:description" content="{he(desc)}" />
<meta name="twitter:image" content="{OG_IMAGE}" />

<!-- Agent / API discovery -->
<link rel="alternate" type="application/rss+xml" href="/research/feed.xml" title="8bitconcepts Research (papers only)" />
<link rel="alternate" type="application/rss+xml" href="/feed.xml" title="8bitconcepts (site-wide)" />
<link rel="alternate" type="application/json" href="/research.json" title="8bitconcepts Research Index (JSON)" />

<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet" />

<script type="application/ld+json">
{jsonld}
</script>

<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--slate:#0d0d0e;--slate-1:#111214;--slate-2:#1a1c1f;--border:rgba(255,255,255,0.07);--terra:#d97757;--terra-dim:rgba(217,119,87,0.08);--terra-edge:rgba(217,119,87,0.25);--text:#e8e8e9;--text-dim:#8b8d91;--text-dimmer:#5a5c61}}
html{{scroll-behavior:smooth}}
body{{background:var(--slate);color:var(--text);font-family:'Inter',system-ui,sans-serif;line-height:1.7;-webkit-font-smoothing:antialiased}}
nav{{position:sticky;top:0;z-index:100;background:rgba(13,13,14,0.92);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:0 28px;height:56px;display:flex;align-items:center;justify-content:space-between}}
.nav-logo{{font-family:'IBM Plex Mono',monospace;font-weight:500;font-size:15px;color:var(--text);letter-spacing:-0.02em;text-decoration:none}}
.nav-logo span{{color:var(--terra)}}
.nav-links{{display:flex;gap:22px;align-items:center}}
.nav-links a{{color:var(--text-dim);font-size:14px;text-decoration:none;transition:color .15s}}
.nav-links a:hover{{color:var(--terra)}}
.wrap{{max-width:980px;margin:0 auto;padding:56px 24px 96px}}
.eyebrow{{font-family:'IBM Plex Mono',monospace;font-size:12px;text-transform:uppercase;letter-spacing:0.2em;color:var(--terra);margin-bottom:14px}}
h1{{font-size:48px;letter-spacing:-0.025em;color:#fff;line-height:1.1;margin-bottom:18px;max-width:800px}}
.intro{{font-size:18px;color:#c5c5c9;max-width:720px;margin-bottom:12px}}
.intro strong{{color:#fff;font-weight:600}}
.intro-sub{{font-size:14px;color:var(--text-dim);max-width:720px}}
.stats-row{{display:flex;flex-wrap:wrap;gap:32px;margin:32px 0 16px;padding:18px 22px;background:var(--slate-1);border:1px solid var(--border);border-radius:10px}}
.stat{{display:flex;flex-direction:column}}
.stat-num{{font-family:'IBM Plex Mono',monospace;font-size:22px;color:var(--terra);font-weight:500}}
.stat-label{{font-size:12px;color:var(--text-dim);text-transform:uppercase;letter-spacing:0.1em;margin-top:4px}}
.section{{margin-top:72px}}
.section-title{{font-size:28px;color:#fff;letter-spacing:-0.015em;margin-bottom:8px}}
.section-sub{{font-size:15px;color:var(--text-dim);max-width:720px;margin-bottom:28px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}}
.card{{display:flex;flex-direction:column;padding:20px 22px;background:var(--slate-1);border:1px solid var(--border);border-radius:10px;text-decoration:none;color:inherit;transition:border-color .15s,transform .15s}}
.card:hover{{border-color:var(--terra);transform:translateY(-1px)}}
.card-title{{font-size:17px;font-weight:600;color:#fff;margin-bottom:8px;letter-spacing:-0.01em}}
.card-desc{{font-size:14px;color:#c5c5c9;margin-bottom:12px;flex:1}}
.card-meta{{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--text-dimmer);font-family:'IBM Plex Mono',monospace;margin-bottom:10px}}
.meta-item{{color:var(--text-dim)}}
.meta-sep{{color:var(--text-dimmer)}}
.card-tags{{display:flex;flex-wrap:wrap;gap:6px}}
.tag{{font-size:11px;font-family:'IBM Plex Mono',monospace;color:var(--terra);padding:2px 8px;background:var(--terra-dim);border-radius:3px}}
.topic{{padding:20px 22px;margin-bottom:14px;background:var(--slate-1);border:1px solid var(--border);border-radius:10px}}
.topic-title{{font-size:18px;color:#fff;margin-bottom:6px;letter-spacing:-0.01em}}
.topic-blurb{{font-size:14px;color:var(--text-dim);margin-bottom:12px}}
.topic-list{{list-style:none;display:flex;flex-wrap:wrap;gap:8px}}
.topic-list li{{background:var(--slate-2);padding:6px 12px;border-radius:6px;border:1px solid var(--border)}}
.topic-list a{{color:var(--text);text-decoration:none;font-size:14px}}
.topic-list a:hover{{color:var(--terra)}}
.mini-meta{{font-family:'IBM Plex Mono',monospace;color:var(--text-dimmer);font-size:11px;margin-left:4px}}
.path{{padding:26px 28px;margin-bottom:16px;background:var(--slate-1);border:1px solid var(--border);border-radius:10px}}
.path-eyebrow{{font-family:'IBM Plex Mono',monospace;font-size:11px;text-transform:uppercase;letter-spacing:0.18em;color:var(--terra);margin-bottom:8px}}
.path-title{{font-size:20px;color:#fff;letter-spacing:-0.01em;margin-bottom:8px}}
.path-blurb{{font-size:14px;color:var(--text-dim);max-width:640px;margin-bottom:20px}}
.path-steps{{list-style:none;counter-reset:step}}
.path-steps li{{display:flex;gap:16px;padding:14px 0;border-top:1px solid var(--border)}}
.path-steps li:first-child{{border-top:none;padding-top:4px}}
.step-num{{flex-shrink:0;width:28px;height:28px;border-radius:50%;background:var(--terra-dim);border:1px solid var(--terra-edge);color:var(--terra);font-family:'IBM Plex Mono',monospace;font-size:13px;display:flex;align-items:center;justify-content:center;font-weight:500}}
.step-body{{flex:1}}
.step-title{{display:block;font-size:15px;font-weight:600;color:#fff;text-decoration:none;margin-bottom:4px}}
.step-title:hover{{color:var(--terra)}}
.step-desc{{font-size:13px;color:var(--text-dim);margin-bottom:4px;line-height:1.55}}
.step-meta{{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--text-dimmer)}}
.subscribe-box{{padding:28px 30px;background:linear-gradient(180deg,var(--slate-1) 0%,var(--slate-2) 100%);border:1px solid var(--terra-edge);border-radius:12px;margin-top:24px}}
.subscribe-box h3{{font-size:20px;color:#fff;margin-bottom:6px;letter-spacing:-0.01em}}
.subscribe-box p{{color:var(--text-dim);font-size:14px;margin-bottom:16px;max-width:560px}}
.subscribe-form{{display:flex;gap:10px;flex-wrap:wrap}}
.subscribe-form input{{flex:1;min-width:240px;padding:11px 15px;border:1px solid #333;background:var(--slate);color:#fff;border-radius:6px;font-size:15px;font-family:inherit}}
.subscribe-form input:focus{{outline:none;border-color:var(--terra)}}
.subscribe-form button{{padding:11px 22px;background:var(--terra);color:#fff;border:none;border-radius:6px;font-weight:600;font-size:15px;cursor:pointer;font-family:inherit;transition:opacity .15s}}
.subscribe-form button:hover{{opacity:0.88}}
.sub-status{{margin-top:12px;font-size:13px;min-height:1em;font-family:'IBM Plex Mono',monospace}}
.small{{font-size:12px;color:var(--text-dimmer);margin-top:10px}}
.small a{{color:var(--terra);text-decoration:none}}
footer{{margin-top:96px;padding-top:28px;border-top:1px solid var(--border);font-size:13px;color:var(--text-dimmer);text-align:center}}
footer a{{color:var(--terra);text-decoration:none}}
@media(max-width:640px){{
  h1{{font-size:34px}}
  .wrap{{padding:40px 18px 72px}}
  .stats-row{{gap:20px;padding:14px 16px}}
  .path{{padding:20px 18px}}
  nav{{padding:0 16px}}
  .nav-links{{gap:14px}}
}}
</style>
<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
</head>
<body>

<nav>
  <a class="nav-logo" href="/">8bit<span>concepts</span></a>
  <div class="nav-links">
    <a href="/research/">Research</a>
    <a href="/research/overview.html">Atlas</a>
    <a href="/research/feed.xml">RSS</a>
  </div>
</nav>

<div class="wrap">
  <div class="eyebrow">Research Atlas</div>
  <h1>The practitioner's atlas of enterprise AI</h1>
  <p class="intro"><strong>8bitconcepts</strong> is independent field-level research on enterprise AI adoption, governance, multi-agent systems, and ROI - written for engineering and AI leaders at Series B-D companies doing the actual work.</p>
  <p class="intro-sub">No vendor sponsorship. No paywall. No "transformation" slide decks. Every paper is grounded in what teams are shipping (or failing to ship) inside real production systems. This page is the map.</p>

  <div class="stats-row">
    <div class="stat">
      <div class="stat-num">{total}</div>
      <div class="stat-label">papers</div>
    </div>
    <div class="stat">
      <div class="stat-num">{len(TOPIC_INDEX)}</div>
      <div class="stat-label">topics</div>
    </div>
    <div class="stat">
      <div class="stat-num">{len(READING_PATHS)}</div>
      <div class="stat-label">reading paths</div>
    </div>
    <div class="stat">
      <div class="stat-num">$0</div>
      <div class="stat-label">paywall</div>
    </div>
  </div>

  <div class="section">
    <h2 class="section-title">All papers</h2>
    <p class="section-sub">Every 8bitconcepts research paper, most-recent first. Reading-time estimates based on ~250 words per minute.</p>
    <div class="grid">
{cards_html}
    </div>
  </div>

  <div class="section">
    <h2 class="section-title">Topic index</h2>
    <p class="section-sub">Papers grouped by theme. Each paper appears under every topic it touches.</p>
{topics_html}
  </div>

  <div class="section">
    <h2 class="section-title">Reading paths</h2>
    <p class="section-sub">Three curated sequences for the most common jobs-to-be-done. Work through in order.</p>
{paths_html}
  </div>

  <div class="section">
    <h2 class="section-title">Subscribe</h2>
    <div class="subscribe-box">
      <h3>Two papers a week. Unsubscribe in one click.</h3>
      <p>Practitioner research on enterprise AI delivered to your inbox. No fluff, no vendor pitches, no "how AI will change everything" framing. Prefer a reader? <a href="/research/feed.xml" style="color:var(--terra);text-decoration:none;border-bottom:1px solid var(--terra-edge);">Subscribe via RSS</a>.</p>
      <form class="subscribe-form" onsubmit="return sub8bc(event)">
        <input type="email" name="email" placeholder="you@company.com" required />
        <button type="submit">Subscribe</button>
      </form>
      <p class="sub-status" id="sub-status"></p>
      <p class="small">Prefer a reader? <a href="/research/feed.xml">Research RSS feed</a> (papers only) or <a href="/feed.xml">site-wide feed</a>. Programmatic access? <a href="/research.json">research.json</a>, <a href="/openapi.yaml">OpenAPI spec</a>, <a href="/llms.txt">llms.txt</a>.</p>
    </div>
  </div>

  <footer>
    <p>&copy; 2026 8bitconcepts &mdash; AI Enablement &amp; Integration Consulting &mdash; <a href="mailto:hello@8bitconcepts.com">hello@8bitconcepts.com</a></p>
    <p style="margin-top:6px;">Atlas generated {generated_at} &middot; <a href="/research/">Plain research index</a> &middot; <a href="/">Home</a></p>
    <p style="margin-top:12px;">
        <strong>Weekly across the Foundry:</strong>
        <a href="https://nothumansearch.ai/digest" target="_blank" rel="noopener">MCP ecosystem digest</a> &middot;
        <a href="https://aidevboard.com/weekly-hiring" target="_blank" rel="noopener">AI hiring snapshot</a>
    </p>
  </footer>
</div>

<script>
async function sub8bc(e){{
  e.preventDefault();
  const f = e.target;
  const email = f.email.value.trim();
  const s = document.getElementById('sub-status');
  s.textContent = 'Subscribing...';
  s.style.color = '#8b8d91';
  try {{
    const r = await fetch('https://aidevboard.com/api/v1/subscribe', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{email, tags: ['8bitconcepts-research'], frequency: 'weekly'}})
    }});
    if (r.ok) {{
      s.textContent = 'Subscribed. Check your inbox.';
      s.style.color = '#4ade80';
      f.reset();
    }} else {{
      s.textContent = 'Error. Email hello@8bitconcepts.com instead.';
      s.style.color = '#f87171';
    }}
  }} catch (err) {{
    s.textContent = 'Network error. Email hello@8bitconcepts.com instead.';
    s.style.color = '#f87171';
  }}
  return false;
}}
</script>
</body>
</html>
"""


def main() -> int:
    if not RESEARCH_DIR.is_dir():
        print(f"ERROR: {RESEARCH_DIR} not found", file=sys.stderr)
        return 2
    papers = load_papers()
    if not papers:
        print("ERROR: no research papers found", file=sys.stderr)
        return 2
    # Newest first for the grid (all share 2026-04-01 today; secondary sort by title).
    papers.sort(key=lambda p: (p["date_iso"], p["title"]), reverse=True)

    html_out = build_html(papers)
    OUT_PATH.write_text(html_out, encoding="utf-8")
    print(f"wrote {OUT_PATH} ({len(papers)} papers, {len(html_out):,} bytes)")

    # Also regenerate the dedicated research RSS feed (research/feed.xml).
    if FEED_SCRIPT.is_file():
        try:
            r = subprocess.run(
                ["python3", str(FEED_SCRIPT)],
                cwd=REPO, capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                print(r.stdout.strip() or f"regenerated {FEED_SCRIPT.name}")
            else:
                print(f"research-feed regen failed (non-fatal): {r.stderr[:300]}", file=sys.stderr)
        except Exception as e:
            print(f"research-feed regen error (non-fatal): {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
