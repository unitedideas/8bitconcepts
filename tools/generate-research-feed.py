#!/usr/bin/env python3
"""
Generates /research/feed.xml - a dedicated RSS 2.0 feed for 8bitconcepts research papers.

Scans /research/*.html, extracts title / meta description / pubDate / tags, and emits
a valid RSS 2.0 feed scoped only to research papers (separate from the site-wide /feed.xml).

pubDate precedence per paper:
  1) <meta name="last-updated" content="YYYY-MM-DDTHH:MM:SSZ"> (5 auto-regen papers)
  2) "datePublished" inside embedded JSON-LD ScholarlyArticle
  3) File mtime (last resort)

Run from anywhere:  python3 tools/generate-research-feed.py
Auto-invoked by tools/generate-overview.py so every weekly paper regen refreshes the feed.
"""
from __future__ import annotations

import html
import re
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
RESEARCH_DIR = REPO / "research"
OUT_PATH = RESEARCH_DIR / "feed.xml"
SITE = "https://8bitconcepts.com"
FEED_SELF = f"{SITE}/research/feed.xml"

SKIP = {"index.html", "overview.html"}

# Mirrors the curated descriptions used in generate-overview.py; keep sources aligned.
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
    "q2-2026-ai-hiring-snapshot": "Live snapshot: 8,618 AI/ML engineering roles across 513 companies, $213k median, 599 new this week. OpenAI leads with 336 open roles.",
    "q2-2026-mcp-ecosystem-health": "5,578 agent-ready sites indexed, only 575 (10.3%) pass a live JSON-RPC handshake. Category breakdown and the regulated verticals still waiting to be built.",
    "q2-2026-ai-compensation-by-skill": "Research roles pay a $42k premium over generative-AI roles ($274k vs $231k avg), even though generative-AI has 2.5x more openings.",
    "q2-2026-remote-vs-onsite-ai-hiring": "Hybrid AI/ML roles pay a ~$35k premium over remote+onsite ($253k vs $218k). 55% of AI engineering roles still require full onsite attendance.",
    "q2-2026-entry-level-ai-gap": "Only ~7% of AI/ML engineering roles are open to juniors. For every entry-level opening there are ~10 senior-plus roles - the tightest junior-to-senior ratio in tech.",
}

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

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
META_DESC_RE = re.compile(
    r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']\s*/?>',
    re.IGNORECASE | re.DOTALL,
)
LAST_UPDATED_RE = re.compile(
    r'<meta\s+name=["\']last-updated["\']\s+content=["\'](.*?)["\']\s*/?>',
    re.IGNORECASE,
)
DATE_PUB_RE = re.compile(r'"datePublished"\s*:\s*"([0-9]{4}-[0-9]{2}-[0-9]{2}(?:T[0-9:.-]+Z?)?)"')


def clean_title(raw: str) -> str:
    t = html.unescape(raw.strip())
    for sep in (" -- 8bitconcepts", " — 8bitconcepts", " | 8bitconcepts"):
        if t.endswith(sep):
            t = t[: -len(sep)]
            break
    return t.strip()


def parse_iso(s: str) -> datetime | None:
    s = s.strip()
    if not s:
        return None
    # Handle common variants: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SSZ, with tz, etc.
    fmts = (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d",
    )
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def parse_paper(path: Path) -> dict[str, Any] | None:
    if path.name in SKIP:
        return None
    slug = path.stem
    raw = path.read_text(encoding="utf-8", errors="ignore")

    title_m = TITLE_RE.search(raw)
    desc_m = META_DESC_RE.search(raw)
    lu_m = LAST_UPDATED_RE.search(raw)
    dp_m = DATE_PUB_RE.search(raw)

    title = clean_title(title_m.group(1)) if title_m else slug.replace("-", " ").title()
    meta_desc = html.unescape(desc_m.group(1)).strip() if desc_m else ""
    summary = CURATED_DESC.get(slug) or meta_desc or title

    pub_dt: datetime | None = None
    if lu_m:
        pub_dt = parse_iso(lu_m.group(1))
    if pub_dt is None and dp_m:
        pub_dt = parse_iso(dp_m.group(1))
    if pub_dt is None:
        try:
            mtime = path.stat().st_mtime
            pub_dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
        except Exception:
            pub_dt = datetime.now(timezone.utc)

    tags = SLUG_TAGS.get(slug, [])

    return {
        "slug": slug,
        "url": f"{SITE}/research/{path.name}",
        "title": title,
        "summary": summary,
        "pub_dt": pub_dt,
        "tags": tags,
    }


def xml_escape(s: str) -> str:
    return html.escape(s, quote=True)


def render_item(p: dict[str, Any]) -> str:
    pub_date_822 = format_datetime(p["pub_dt"])
    categories = "".join(f"<category>{xml_escape(t)}</category>" for t in p["tags"])
    return (
        "<item>"
        f"<title>{xml_escape(p['title'])}</title>"
        f"<link>{xml_escape(p['url'])}</link>"
        f"<guid isPermaLink=\"true\">{xml_escape(p['url'])}</guid>"
        f"<pubDate>{pub_date_822}</pubDate>"
        f"<description><![CDATA[{p['summary']}]]></description>"
        f"{categories}"
        "</item>"
    )


def build_feed(papers: list[dict[str, Any]]) -> str:
    now = datetime.now(timezone.utc)
    last_build = format_datetime(now)
    items_xml = "\n".join(render_item(p) for p in papers)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
<title>8bitconcepts Research</title>
<link>{SITE}/research</link>
<atom:link href="{FEED_SELF}" rel="self" type="application/rss+xml" />
<description>Practitioner-grade research on AI engineering, hiring, compensation, and infrastructure. Auto-refreshed weekly.</description>
<language>en-US</language>
<lastBuildDate>{last_build}</lastBuildDate>
<managingEditor>hello@8bitconcepts.com (8bitconcepts)</managingEditor>
<webMaster>hello@8bitconcepts.com (8bitconcepts)</webMaster>
<generator>tools/generate-research-feed.py</generator>
<docs>https://www.rssboard.org/rss-specification</docs>
{items_xml}
</channel></rss>"""


def main() -> int:
    if not RESEARCH_DIR.is_dir():
        print(f"ERROR: {RESEARCH_DIR} not found", file=sys.stderr)
        return 2
    papers: list[dict[str, Any]] = []
    for p in sorted(RESEARCH_DIR.glob("*.html")):
        parsed = parse_paper(p)
        if parsed:
            papers.append(parsed)
    if not papers:
        print("ERROR: no research papers found", file=sys.stderr)
        return 2
    # Newest first.
    papers.sort(key=lambda x: x["pub_dt"], reverse=True)
    xml = build_feed(papers)
    OUT_PATH.write_text(xml, encoding="utf-8")
    print(f"wrote {OUT_PATH} ({len(papers)} items, {len(xml):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
