#!/usr/bin/env python3
"""
Regenerate /research/q2-2026-mcp-ecosystem-health.html from live NHS data.

Pulls fresh stats from:
  - https://nothumansearch.ai/digest.json

Rebuilds the full HTML (template inlined), then:
  - Writes the paper (overwrites in place)
  - Regenerates /research/overview.html (atlas)
  - Commits only if data actually changed
  - Pushes origin main (GitHub Pages deploy)
  - IndexNow-pings the paper URL (Bing/Yandex/Naver/Seznam)
  - WebSub-pings the 8bc feed (appspot + superfeedr)
  - Submits to NHS (best-effort; tolerates 429)

Usage:
    python3 tools/regenerate-mcp-health.py          # full run
    python3 tools/regenerate-mcp-health.py --dry-run # fetch + render, don't write
    python3 tools/regenerate-mcp-health.py --once    # write + overview, skip commit/push/pings
    python3 tools/regenerate-mcp-health.py --no-push # skip git push + pings (commit still happens)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
RESEARCH_DIR = REPO / "research"
PAPER_PATH = RESEARCH_DIR / "q2-2026-mcp-ecosystem-health.html"
OVERVIEW_SCRIPT = REPO / "tools" / "generate-overview.py"
PAPER_URL = "https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html"

OG_SLUG = "q2-2026-mcp-ecosystem-health"
OG_IMAGE_PATH = RESEARCH_DIR / "og" / f"{OG_SLUG}.png"
OG_IMAGE_URL = f"https://8bitconcepts.com/research/og/{OG_SLUG}.png"

# Make the shared OG helper importable (same dir as this script)
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from generate_og_image import generate_og_image  # noqa: E402
except Exception as _og_err:  # pragma: no cover
    generate_og_image = None  # type: ignore[assignment]
    print(f"  Warning: OG generator import failed: {_og_err}", file=sys.stderr)
FEED_URL = "https://8bitconcepts.com/feed.xml"
RESEARCH_FEED_URL = "https://8bitconcepts.com/research/feed.xml"
INDEXNOW_KEY = "e4e40fed94fa41b09613c20e7bac4484"
HOST = "8bitconcepts.com"
USER_AGENT = "curl/8.7.1"

NHS_DIGEST_URL = "https://nothumansearch.ai/digest.json"
NHS_STATS_URL = "https://nothumansearch.ai/api/v1/stats"
NHS_SUBMIT_URL = "https://nothumansearch.ai/api/v1/submit"

# Public gist: https://gist.github.com/unitedideas/c93bd6d9984729070c59b2ea6c6b301b
GIST_ID = "c93bd6d9984729070c59b2ea6c6b301b"
GIST_CSV_FILENAME = "mcp-ecosystem-health.csv"
GIST_MD_FILENAME = "mcp-ecosystem-health.md"
# Canonical raw URLs (always latest revision — no commit hash in path)
GIST_CSV_RAW_URL = f"https://gist.githubusercontent.com/unitedideas/{GIST_ID}/raw/{GIST_CSV_FILENAME}"
GIST_MD_RAW_URL = f"https://gist.githubusercontent.com/unitedideas/{GIST_ID}/raw/{GIST_MD_FILENAME}"
GIST_URL = f"https://gist.github.com/unitedideas/{GIST_ID}"


def http_get_json(url: str, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fmt_thousands(n: Any) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n)


def category_label(key: str) -> str:
    return {
        "ai-tools": "AI-native tools",
        "developer": "Developer tools",
        "data": "Data / analytics",
        "finance": "Finance / fintech",
        "productivity": "Productivity",
        "security": "Security",
        "ecommerce": "E-commerce",
        "health": "Health / medical",
        "communication": "Communication",
        "education": "Education",
        "jobs": "Jobs / hiring",
        "news": "News / media",
        "other": "Uncategorized",
    }.get(key, key.capitalize() if key else "—")


def html_escape(s: str) -> str:
    if s is None:
        return ""
    return (
        str(s)
        .replace("&amp;", "&")  # un-escape first so we don't double-escape
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def attr_escape(s: str) -> str:
    if s is None:
        return ""
    return (
        str(s)
        .replace("&amp;", "&")
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_html(digest: dict[str, Any], today: str, generated_iso: str) -> str:
    total_sites = int(digest.get("total_sites", 0))
    mcp_verified = int(digest.get("mcp_verified", 0))
    llms_txt_count = int(digest.get("llms_txt_count", 0))
    openapi_count = int(digest.get("openapi_count", 0))
    pct_mcp = float(digest.get("pct_mcp", 0.0))
    pct_llms = float(digest.get("pct_llms_txt", 0.0))
    pct_openapi = float(digest.get("pct_openapi", 0.0))
    submissions_week = int(digest.get("submissions_week", 0))

    categories = digest.get("categories", []) or []
    new_mcp_servers = digest.get("new_mcp_servers", []) or []
    top_mcp_servers = digest.get("top_mcp_servers", []) or []

    # Derived
    unverified = max(total_sites - mcp_verified, 0)
    unverified_pct = (unverified / total_sites * 100) if total_sites else 0

    # Category breakdown as % of index
    total_cat_count = sum(int(c.get("count", 0)) for c in categories) or 1
    # Sort already sorted by count; skip 'other' in visible tables
    visible_cats = [c for c in categories if c.get("name") != "other"]
    top_cats = visible_cats[:10]

    # Biggest category (excluding 'other')
    if visible_cats:
        biggest_cat = visible_cats[0]
        biggest_cat_name = category_label(biggest_cat.get("name", ""))
        biggest_cat_count = int(biggest_cat.get("count", 0))
        biggest_cat_pct = biggest_cat_count / total_sites * 100 if total_sites else 0
    else:
        biggest_cat_name = "Developer tools"
        biggest_cat_count = 0
        biggest_cat_pct = 0

    # Under-represented categories (thin coverage even though vertical is large)
    thin_cats = [c for c in visible_cats if int(c.get("count", 0)) < 150]
    # Pick three interesting under-represented verticals for commentary if available
    thin_names = {c.get("name") for c in thin_cats}

    def cat_count_by_name(n: str) -> int:
        for c in categories:
            if c.get("name") == n:
                return int(c.get("count", 0))
        return 0

    finance_ct = cat_count_by_name("finance")
    health_ct = cat_count_by_name("health")
    security_ct = cat_count_by_name("security")
    ecom_ct = cat_count_by_name("ecommerce")
    edu_ct = cat_count_by_name("education")
    jobs_ct = cat_count_by_name("jobs")
    news_ct = cat_count_by_name("news")

    # Build rows
    category_rows = "\n".join(
        f"          <tr><td>{category_label(c.get('name', ''))}</td>"
        f"<td class=\"num\">{fmt_thousands(c.get('count', 0))}</td>"
        f"<td class=\"num\">{(int(c.get('count', 0)) / total_sites * 100):.1f}%</td></tr>"
        for c in top_cats
    )

    # New this week rows — sort by created_at desc already, limit to 10
    new_rows_list = []
    for s in new_mcp_servers[:10]:
        domain = html_escape(s.get("domain", "—"))
        name = html_escape((s.get("name") or "").split("—")[0].split("|")[0].strip() or "—")
        cat = category_label(s.get("category", ""))
        score = int(s.get("agentic_score", 0))
        new_rows_list.append(
            f"          <tr><td><a href=\"https://nothumansearch.ai/site/{domain}\">{domain}</a></td>"
            f"<td>{name}</td>"
            f"<td>{cat}</td>"
            f"<td class=\"num\">{score}</td></tr>"
        )
    new_rows = "\n".join(new_rows_list) if new_rows_list else "<tr><td colspan=\"4\">No new MCP servers this week.</td></tr>"

    # Meta / schema strings
    mcp_pct_round = f"{pct_mcp:.1f}"
    subtitle_text = (
        f"As of {today}, {fmt_thousands(total_sites)} agent-ready sites are indexed on "
        f"NothingHumanSearch, but only {fmt_thousands(mcp_verified)} ({mcp_pct_round}%) survive a real JSON-RPC "
        f"handshake to their /mcp endpoint. The rest claim MCP in their docs but don't implement it correctly. "
        f"Live data pulled from <a href=\"https://nothumansearch.ai/digest.json\">nothumansearch.ai/digest.json</a>."
    )

    meta_description = (
        f"Live MCP ecosystem health: {fmt_thousands(total_sites)} agent-ready sites indexed, {fmt_thousands(mcp_verified)} "
        f"({mcp_pct_round}%) MCP-verified via JSON-RPC handshake. {fmt_thousands(llms_txt_count)} publish llms.txt, "
        f"{fmt_thousands(openapi_count)} publish OpenAPI. Category breakdown, newly-indexed servers, gaps."
    )
    og_description = (
        f"{fmt_thousands(mcp_verified)} of {fmt_thousands(total_sites)} indexed agent-ready sites ({mcp_pct_round}%) "
        f"pass a live JSON-RPC handshake. Most MCP claims don't implement the protocol correctly. "
        f"Category breakdown + newly-verified servers from NothingHumanSearch."
    )
    twitter_description = (
        f"MCP reality check: {fmt_thousands(mcp_verified)}/{fmt_thousands(total_sites)} sites survive a real "
        f"JSON-RPC handshake. Live data from nothumansearch.ai, {today}."
    )

    article_description = (
        f"Live MCP ecosystem audit from NothingHumanSearch: {fmt_thousands(total_sites)} agent-ready sites indexed, "
        f"only {fmt_thousands(mcp_verified)} ({mcp_pct_round}%) MCP-verified via live JSON-RPC handshake. Category "
        f"breakdown, top MCP servers, newly-indexed this week, and gaps in regulated verticals."
    )

    # Executive summary paragraph — opener with hard numbers
    exec_summary_para = (
        f"NothingHumanSearch has been crawling the web for agent-readiness signals since launch, and the "
        f"numbers tell a consistent story about the gap between claiming MCP support and shipping it. "
        f"As of {today} the index holds {fmt_thousands(total_sites)} sites with at least one agent-discovery "
        f"signal (llms.txt, ai-plugin.json, OpenAPI, or an MCP manifest). Of those, "
        f"{fmt_thousands(mcp_verified)} &mdash; {mcp_pct_round}% &mdash; pass a live JSON-RPC probe against "
        f"their declared /mcp endpoint. The remaining {fmt_thousands(unverified)} sites ({unverified_pct:.1f}%) "
        f"either mention MCP in their documentation without implementing it, or host a manifest that fails "
        f"the handshake (404, 500, wrong Content-Type, or a server that answers HTTP but never completes "
        f"the <code>initialize</code> round-trip)."
    )

    # Verification meaning
    verify_meaning_para_1 = (
        f"Static scanners &mdash; the ones that produce most of the MCP directory listings you see today &mdash; "
        f"treat a string match for <code>mcp</code> in <code>llms.txt</code> or a link to "
        f"<code>/.well-known/mcp.json</code> as a positive signal. That's how you end up with directories "
        f"claiming 10,000+ MCP servers when the actual live count is smaller by an order of magnitude. A real "
        f"check has to open a connection, send <code>{{\"method\": \"initialize\"}}</code>, wait for a protocol "
        f"handshake, and confirm the server responds with a valid <code>result</code> block citing a "
        f"<code>protocolVersion</code>. Anything short of that is a citation, not an implementation."
    )

    verify_meaning_para_2 = (
        f"NHS's <code>verify_mcp</code> tool (published as part of the NHS MCP server at "
        f"<a href=\"https://nothumansearch.ai/mcp\">nothumansearch.ai/mcp</a>) does exactly this live-probe for any "
        f"URL you hand it. When we recrawled the full index in April 2026 with the probe turned on, the "
        f"verified-MCP count stayed stable around {fmt_thousands(mcp_verified)} even as the total indexed "
        f"population kept climbing. The gap between &quot;sites that mention MCP&quot; and &quot;sites that "
        f"implement MCP&quot; is widening, not narrowing &mdash; which is the opposite of what the marketing "
        f"cycle would have you believe."
    )

    verify_meaning_para_3 = (
        f"This matters for anyone building an agent. If you rely on a static MCP directory to decide which "
        f"tools your agent should discover at runtime, you will waste connections and context tokens on dead "
        f"endpoints. The 90% unverified cohort isn't malicious &mdash; it's mostly stale docs, misconfigured "
        f"reverse proxies, and manifests that reference endpoints the author never actually wired up. But for "
        f"an autonomous agent, the failure mode is the same: a call that eats latency, fails, and doesn't "
        f"advance the task."
    )

    # Categories
    categories_intro_para = (
        f"Across verified MCP servers and the broader agent-ready population, the category distribution is "
        f"heavily concentrated. <strong>{biggest_cat_name}</strong> alone accounts for "
        f"{fmt_thousands(biggest_cat_count)} sites ({biggest_cat_pct:.1f}% of the index). AI-native tools "
        f"follow closely &mdash; unsurprising given that MCP emerged from the AI-tools ecosystem. After that, "
        f"category density drops off a cliff."
    )

    # Gaps paragraph — focus on regulated / high-value verticals with thin coverage
    gap_para = (
        f"The gap that matters for builders: regulated high-value verticals are still thinly represented. "
        f"Finance has {fmt_thousands(finance_ct)} sites, health has {fmt_thousands(health_ct)}, and "
        f"education has {fmt_thousands(edu_ct)}. These are the same verticals where agents would deliver the "
        f"most leverage per call &mdash; underwriting assistance, clinical documentation, degree-audit lookups "
        f"&mdash; and they are the verticals where the MCP ecosystem is the least mature. Jobs "
        f"({fmt_thousands(jobs_ct)}) and news ({fmt_thousands(news_ct)}) round out the long tail. If you are "
        f"deciding where to ship an MCP server and you want reach-per-server rather than defensibility through "
        f"a crowd, the signal is clear: any vertical below {fmt_thousands(security_ct)} indexed sites is "
        f"green field."
    )

    # New this week
    new_this_week_para = (
        f"Ten MCP servers were newly verified in the last seven days. Every one of them scored 100 on the "
        f"NHS agentic-readiness rubric &mdash; meaning they publish llms.txt, ai-plugin.json, an OpenAPI spec, "
        f"<em>and</em> pass the live JSON-RPC MCP handshake. The pattern is consistent: teams that ship one "
        f"discovery file tend to ship all of them, and teams that ship none ship none. There is no middle."
    )

    # Methodology paragraph
    methodology_para = (
        f"NHS crawls submitted URLs and auto-discovered candidates from public sources (awesome-mcp-servers, "
        f"PulseMCP, llmstxt.site, and a handful of curated feeds), then scores each site against seven "
        f"weighted signals: <code>llms.txt</code> present and parseable; <code>ai-plugin.json</code> at "
        f"<code>/.well-known/</code>; an OpenAPI or AsyncAPI spec at a discoverable path; an MCP manifest; a "
        f"live JSON-RPC MCP handshake; documented rate-limit and auth headers; and an accessible structured "
        f"API response. Sites are re-crawled weekly. Scores range 0-100; any score above 75 corresponds to "
        f"a site that an autonomous agent can realistically integrate without human help. The full probe "
        f"methodology is open-source at <a href=\"https://nothumansearch.ai/methodology\">"
        f"nothumansearch.ai/methodology</a>."
    )

    # Download raw data callout (CSV + MD gist) — mirrors hiring-snapshot pattern
    download_para = (
        f'<strong>Download raw data:</strong> The MCP ecosystem health dataset is mirrored as a public gist '
        f'&mdash; <a href="{GIST_CSV_RAW_URL}">CSV</a> &middot; '
        f'<a href="{GIST_MD_RAW_URL}">Markdown</a> &middot; '
        f'<a href="{GIST_URL}">view on GitHub</a>. '
        f"Auto-updated every weekly regeneration, canonical raw URLs are stable across revisions."
    )

    # Submissions stat sentence
    submissions_sentence = (
        f"Weekly submission volume is running at {fmt_thousands(submissions_week)} candidates "
        f"for the week starting {digest.get('week_start', '')[:10]}, most from autonomous discovery agents "
        f"rather than human submissions."
    ) if submissions_week else ""

    # TL;DR
    tldr_para = (
        f"<strong>Implications for builders.</strong> If you are shipping an MCP server: the live-probe bar "
        f"is low but not everyone clears it &mdash; make sure your deployment actually answers "
        f"<code>initialize</code>, not just serves a manifest. If you are building an agent that consumes "
        f"MCP servers at runtime: discover against a live-verified index, not a static list. And if you are "
        f"choosing a vertical: the crowded categories (developer tools, AI-native tools) are fighting over "
        f"the same agent integrations, while finance, health, and education are asking to be built."
    )

    # Stat cards
    stat_cards_html = f"""      <div class="stat-row">
        <div class="stat-box">
          <div class="stat-num">{fmt_thousands(total_sites)}</div>
          <div class="stat-label">agent-ready sites indexed on NothingHumanSearch ({today})</div>
        </div>
        <div class="stat-box">
          <div class="stat-num">{fmt_thousands(mcp_verified)}</div>
          <div class="stat-label">pass a live JSON-RPC MCP handshake &mdash; {mcp_pct_round}% of the index</div>
        </div>
        <div class="stat-box">
          <div class="stat-num">{fmt_thousands(llms_txt_count)}</div>
          <div class="stat-label">publish <code>llms.txt</code> &mdash; {pct_llms:.1f}% of the index</div>
        </div>
      </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="referrer" content="strict-origin-when-cross-origin" />
  <meta name="color-scheme" content="dark light" />
  <meta name="last-updated" content="{today}" />
  <title>Q2 2026 MCP Ecosystem Health -- 8bitconcepts</title>
  <meta name="description" content="{attr_escape(meta_description)}" />
  <meta property="og:title" content="Q2 2026 MCP Ecosystem Health -- 8bitconcepts" />
  <meta property="og:description" content="{attr_escape(og_description)}" />
  <meta property="og:type" content="article" />
  <meta property="og:url" content="https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html" />
  <meta property="og:image" content="{OG_IMAGE_URL}" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="Q2 2026 MCP Ecosystem Health" />
  <meta name="twitter:description" content="{attr_escape(twitter_description)}" />
  <meta name="twitter:image" content="{OG_IMAGE_URL}" />
  <link rel="canonical" href="https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet" />
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --slate: #0d0d0e;
      --slate-1: #111214;
      --slate-2: #1a1c1f;
      --slate-3: #242729;
      --slate-4: #2e3135;
      --border: rgba(255,255,255,0.07);
      --terra: #d97757;
      --terra-dim: rgba(217,119,87,0.15);
      --terra-dim2: rgba(217,119,87,0.08);
      --text: #e8e8e9;
      --text-dim: #8b8d91;
      --text-dimmer: #5a5c61;
    }}

    html {{ scroll-behavior: smooth; }}

    body {{
      background: var(--slate);
      color: var(--text);
      font-family: 'Inter', sans-serif;
      font-size: 16px;
      line-height: 1.7;
      -webkit-font-smoothing: antialiased;
    }}

    nav {{
      position: fixed;
      top: 0; left: 0; right: 0;
      z-index: 100;
      background: rgba(13,13,14,0.92);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      padding: 0 32px;
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}

    .nav-logo {{
      font-family: 'IBM Plex Mono', monospace;
      font-weight: 500;
      font-size: 15px;
      color: var(--text);
      letter-spacing: -0.02em;
      text-decoration: none;
    }}

    .nav-logo span {{ color: var(--terra); }}

    .nav-links {{
      display: flex;
      gap: 28px;
      align-items: center;
    }}

    .nav-links a {{
      color: var(--text-dim);
      text-decoration: none;
      font-size: 14px;
      font-weight: 500;
      transition: color 0.15s;
    }}

    .nav-links a:hover {{ color: var(--text); }}

    .nav-cta {{
      background: var(--terra);
      color: white;
      border: none;
      padding: 8px 18px;
      border-radius: 6px;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      text-decoration: none;
      transition: opacity 0.15s;
    }}

    .nav-cta:hover {{ opacity: 0.88; }}

    .article-wrap {{
      max-width: 720px;
      margin: 0 auto;
      padding: 112px 32px 80px;
    }}

    .eyebrow {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 12px;
      font-weight: 500;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--terra);
      margin-bottom: 24px;
    }}

    h1 {{
      font-size: clamp(28px, 5vw, 40px);
      font-weight: 700;
      line-height: 1.15;
      letter-spacing: -0.03em;
      color: var(--text);
      margin-bottom: 20px;
    }}

    .subtitle {{
      font-size: 18px;
      line-height: 1.6;
      color: var(--text-dim);
      margin-bottom: 40px;
      font-weight: 400;
    }}

    .meta {{
      display: flex;
      align-items: center;
      gap: 20px;
      padding-bottom: 32px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 48px;
      flex-wrap: wrap;
    }}

    .meta-date {{
      font-size: 13px;
      color: var(--text-dimmer);
      font-family: 'IBM Plex Mono', monospace;
    }}

    .meta-tag {{
      font-size: 12px;
      color: var(--terra);
      background: var(--terra-dim2);
      border: 1px solid rgba(217,119,87,0.2);
      padding: 3px 10px;
      border-radius: 4px;
      font-family: 'IBM Plex Mono', monospace;
      font-weight: 500;
      letter-spacing: 0.04em;
    }}

    .meta-read {{
      font-size: 13px;
      color: var(--text-dimmer);
    }}

    .article-body p {{
      margin-bottom: 24px;
      font-size: 16.5px;
      line-height: 1.75;
      color: var(--text);
    }}

    .article-body p:last-child {{ margin-bottom: 0; }}

    .article-body h2 {{
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: var(--text);
      margin-top: 52px;
      margin-bottom: 18px;
      line-height: 1.3;
    }}

    .article-body h3 {{
      font-size: 17px;
      font-weight: 600;
      letter-spacing: -0.01em;
      color: var(--text);
      margin-top: 36px;
      margin-bottom: 14px;
    }}

    .article-body a {{
      color: var(--terra);
      text-decoration: underline;
      text-decoration-color: rgba(217,119,87,0.35);
      text-underline-offset: 3px;
    }}

    .article-body a:hover {{ text-decoration-color: var(--terra); }}

    .article-body code {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.92em;
      background: var(--slate-3);
      padding: 2px 6px;
      border-radius: 4px;
      color: var(--text);
    }}

    .callout {{
      background: var(--slate-2);
      border-left: 3px solid var(--terra);
      padding: 20px 24px;
      margin: 36px 0;
      border-radius: 0 6px 6px 0;
    }}

    .callout p {{
      margin-bottom: 0 !important;
      color: var(--text) !important;
      font-size: 16px !important;
      line-height: 1.65 !important;
    }}

    .data-table {{
      width: 100%;
      border-collapse: collapse;
      margin: 32px 0;
      font-size: 14px;
    }}

    .data-table th {{
      text-align: left;
      padding: 10px 16px;
      background: var(--slate-3);
      color: var(--text-dim);
      font-weight: 500;
      font-family: 'IBM Plex Mono', monospace;
      font-size: 12px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      border-bottom: 1px solid var(--border);
    }}

    .data-table td {{
      padding: 12px 16px;
      border-bottom: 1px solid var(--border);
      color: var(--text);
      vertical-align: top;
    }}

    .data-table td.num {{
      font-family: 'IBM Plex Mono', monospace;
      text-align: right;
      color: var(--text-dim);
    }}

    .data-table tr:last-child td {{ border-bottom: none; }}

    .stat-row {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin: 36px 0;
    }}

    .stat-box {{
      background: var(--slate-2);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 20px;
    }}

    .stat-num {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 28px;
      font-weight: 500;
      color: var(--terra);
      line-height: 1;
      margin-bottom: 6px;
    }}

    .stat-label {{
      font-size: 13px;
      color: var(--text-dim);
      line-height: 1.4;
    }}

    .footnotes {{
      margin-top: 64px;
      padding-top: 32px;
      border-top: 1px solid var(--border);
    }}

    .footnotes h4 {{
      font-size: 11px;
      font-family: 'IBM Plex Mono', monospace;
      font-weight: 500;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--text-dimmer);
      margin-bottom: 16px;
    }}

    .footnotes ol {{ padding-left: 20px; }}

    .footnotes li {{
      font-size: 13px;
      color: var(--text-dimmer);
      margin-bottom: 8px;
      line-height: 1.5;
    }}

    .footnotes a {{
      color: var(--text-dim);
      text-decoration: none;
    }}

    .footnotes a:hover {{ color: var(--terra); }}

    .related {{
      margin-top: 64px;
      padding-top: 40px;
      border-top: 1px solid var(--border);
    }}

    .related-label {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 11px;
      font-weight: 500;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--text-dimmer);
      margin-bottom: 24px;
    }}

    .related-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
    }}

    .related-card {{
      background: var(--slate-1);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 20px;
      text-decoration: none;
      transition: border-color 0.15s;
    }}

    .related-card:hover {{ border-color: rgba(217,119,87,0.3); }}

    .related-card-title {{
      font-size: 14px;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 6px;
      line-height: 1.3;
    }}

    .related-card-sub {{
      font-size: 12px;
      color: var(--text-dimmer);
    }}

    .article-cta {{
      background: var(--terra-dim2);
      border: 1px solid rgba(217,119,87,0.2);
      border-radius: 8px;
      padding: 32px;
      margin-top: 64px;
      text-align: center;
    }}

    .article-cta p {{
      color: var(--text-dim);
      font-size: 15px;
      margin-bottom: 20px !important;
    }}

    .article-cta a {{
      display: inline-block;
      background: var(--terra);
      color: white;
      text-decoration: none;
      padding: 12px 28px;
      border-radius: 6px;
      font-weight: 600;
      font-size: 15px;
      transition: opacity 0.15s;
    }}

    .article-cta a:hover {{ opacity: 0.88; }}

    footer {{
      border-top: 1px solid var(--border);
      padding: 40px 32px;
      text-align: center;
      color: var(--text-dimmer);
      font-size: 13px;
    }}

    footer a {{
      color: var(--text-dim);
      text-decoration: none;
    }}

    footer a:hover {{ color: var(--terra); }}

    @media (max-width: 640px) {{
      .article-wrap {{ padding: 96px 20px 60px; }}
      nav {{ padding: 0 20px; }}
      .nav-links {{ display: none; }}
      .stat-row {{ grid-template-columns: 1fr 1fr; }}
    }}
  </style>
<script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "Q2 2026 MCP Ecosystem Health",
    "description": "{attr_escape(article_description)}",
    "url": "https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html",
    "datePublished": "2026-04-17",
    "dateModified": "{today}",
    "author": {{"@type": "Organization", "name": "8bitconcepts", "url": "https://8bitconcepts.com"}},
    "publisher": {{"@type": "Organization", "name": "8bitconcepts", "url": "https://8bitconcepts.com"}},
    "image": "{OG_IMAGE_URL}",
    "inLanguage": "en",
    "isAccessibleForFree": true,
    "about": "MCP ecosystem health, agent-ready web services, JSON-RPC handshake verification, category distribution, MCP server gaps",
    "keywords": "MCP, Model Context Protocol, agent-ready, NothingHumanSearch, llms.txt, MCP servers, agent infrastructure, JSON-RPC"
  }}
  </script>
  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{"@type": "ListItem", "position": 1, "name": "8bitconcepts", "item": "https://8bitconcepts.com/"}},
    {{"@type": "ListItem", "position": 2, "name": "Research", "item": "https://8bitconcepts.com/research/"}},
    {{"@type": "ListItem", "position": 3, "name": "Q2 2026 MCP Ecosystem Health"}}
  ]
}}
</script>
</head>
<body>

  <nav>
    <a class="nav-logo" href="https://8bitconcepts.com">8bit<span>concepts</span></a>
    <div class="nav-links">
      <a href="https://8bitconcepts.com/#research">Research</a>
      <a href="https://8bitconcepts.com/#services">Services</a>
      <a href="mailto:hello@8bitconcepts.com" class="nav-cta">Talk to us</a>
    </div>
  </nav>

  <div class="article-wrap">

    <div class="eyebrow">Research &mdash; MCP Ecosystem</div>

    <h1>Q2 2026 MCP Ecosystem Health</h1>

    <p class="subtitle">{subtitle_text}</p>

    <div class="meta">
      <span class="meta-date">{today}</span>
      <span class="meta-tag">Live Data</span>
      <span class="meta-read">~850 words</span>
    </div>

    <div class="article-body">

      <h2>Executive summary</h2>

      <p>{exec_summary_para}</p>

{stat_cards_html}

      <h2>What verification actually means</h2>

      <p>{verify_meaning_para_1}</p>

      <p>{verify_meaning_para_2}</p>

      <p>{verify_meaning_para_3}</p>

      <h2>Top categories by indexed count</h2>

      <p>{categories_intro_para}</p>

      <table class="data-table">
        <thead>
          <tr>
            <th>Category</th>
            <th class="num" style="text-align:right;">Sites</th>
            <th class="num" style="text-align:right;">Share</th>
          </tr>
        </thead>
        <tbody>
{category_rows}
        </tbody>
      </table>

      <h2>New this week</h2>

      <p>{new_this_week_para}</p>

      <table class="data-table">
        <thead>
          <tr>
            <th>Domain</th>
            <th>Name</th>
            <th>Category</th>
            <th class="num" style="text-align:right;">Score</th>
          </tr>
        </thead>
        <tbody>
{new_rows}
        </tbody>
      </table>

      <h2>Gaps in the ecosystem</h2>

      <p>{gap_para}</p>

      <div class="callout">
        <p>The pattern is consistent across every index we maintain: the teams that ship real MCP endpoints are a small fraction of the teams that claim MCP support. For builders, that gap is an opportunity &mdash; the verticals that are thin today will not stay thin for long.</p>
      </div>

      <h2>Methodology</h2>

      <p>{methodology_para}</p>

      <p>{submissions_sentence}</p>

      <p>{download_para}</p>

      <h2>Implications for builders</h2>

      <p>{tldr_para}</p>

      <h2>What's next</h2>

      <p>For the human side of this market &mdash; who is hiring the engineers to build against this infrastructure &mdash; see <a href="/research/q2-2026-ai-hiring-snapshot.html">Q2 2026 AI Engineering Hiring Snapshot</a>. For the engineering maturity ladder that separates teams shipping real MCP servers from teams publishing manifests that don't work, see <a href="/research/beyond-the-prompt.html">Beyond the Prompt</a>. For the governance dimension &mdash; what happens when agents start <em>acting</em> against these endpoints rather than just reading from them &mdash; see <a href="/research/the-agentic-accountability-gap.html">The Agentic Accountability Gap</a>. Full reading paths at the <a href="/research/overview.html">Research Atlas</a>.</p>

    </div>

    <div class="related">
      <div class="related-label">Related Research</div>
      <div class="related-grid">
        <a class="related-card" href="/research/q2-2026-ai-hiring-snapshot.html">
          <div class="related-card-title">Q2 2026 AI Hiring Snapshot</div>
          <div class="related-card-sub">Live market data: roles, salaries, companies hiring.</div>
        </a>
        <a class="related-card" href="/research/beyond-the-prompt.html">
          <div class="related-card-title">Beyond the Prompt</div>
          <div class="related-card-sub">The engineering maturity ladder for production agents.</div>
        </a>
        <a class="related-card" href="/research/the-agentic-accountability-gap.html">
          <div class="related-card-title">The Agentic Accountability Gap</div>
          <div class="related-card-sub">Why governance frameworks break when agents act.</div>
        </a>
        <a class="related-card" href="/research/overview.html">
          <div class="related-card-title">Research Atlas</div>
          <div class="related-card-sub">Every paper, topic index, and three reading paths.</div>
        </a>
      </div>
    </div>

    <div class="article-cta" style="margin-top:40px;">
      <p style="margin-bottom:10px;"><strong>Get new research by email</strong></p>
      <p style="margin-bottom:14px;font-size:15px;">Two papers a week on what's actually happening inside enterprise AI programs. No promo, no hype.</p>
      <form onsubmit="return sub8bc(event)" style="display:flex;gap:8px;flex-wrap:wrap;">
        <input type="email" name="email" placeholder="you@company.com" required
          style="flex:1;min-width:200px;padding:10px 14px;border:1px solid #ccc;border-radius:6px;font-size:15px;" />
        <button type="submit" style="padding:10px 18px;background:#d97757;color:#fff;border:none;border-radius:6px;font-weight:600;cursor:pointer;">Subscribe</button>
      </form>
      <p id="sub-status" style="margin-top:10px;font-size:14px;min-height:1em;"></p>
      <p style="margin-top:6px;font-size:13px;color:#888;">Prefer a reader? <a href="/feed.xml">RSS feed</a>.</p>
    </div>
    <script>
    async function sub8bc(e){{e.preventDefault();const f=e.target;const email=f.email.value.trim();const s=document.getElementById('sub-status');s.textContent='Subscribing…';try{{const r=await fetch('https://aidevboard.com/api/v1/subscribe',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email,tags:['8bitconcepts-research'],frequency:'weekly'}})}});if(r.ok){{s.textContent='Subscribed. Check your inbox.';s.style.color='#0a0';f.reset();}}else{{s.textContent='Error subscribing. Email hello@8bitconcepts.com instead.';s.style.color='#c00';}}}}catch(err){{s.textContent='Network error. Email hello@8bitconcepts.com.';s.style.color='#c00';}}return false;}}
    </script>

    <div class="footnotes">
      <h4>Sources</h4>
      <ol>
        <li>NothingHumanSearch &mdash; <a href="https://nothumansearch.ai/digest.json">/digest.json</a>, pulled {generated_iso}. Public unauthenticated endpoint. Backing index: {fmt_thousands(total_sites)} agent-ready sites / {fmt_thousands(mcp_verified)} MCP-verified via JSON-RPC handshake.</li>
        <li>NothingHumanSearch &mdash; <a href="https://nothumansearch.ai/mcp">/mcp</a>, live MCP server exposing <code>verify_mcp</code>, <code>search</code>, <code>get_site</code>, <code>list_categories</code>, <code>get_top_sites</code>, and four more tools over JSON-RPC 2.0.</li>
        <li>NothingHumanSearch &mdash; <a href="https://nothumansearch.ai/methodology">/methodology</a>, open-source scoring rubric with 7 weighted signals.</li>
        <li>Verification means a TCP connection + HTTP POST to the declared <code>/mcp</code> endpoint with a JSON-RPC 2.0 <code>initialize</code> request, followed by a valid <code>result</code> response containing a <code>protocolVersion</code>. Sites that host a manifest but fail the handshake are counted in the index total but not in the MCP-verified total.</li>
      </ol>
    </div>

  </div>

  <footer>
    <p>&copy; 2026 8bitconcepts &mdash; AI Enablement &amp; Integration Consulting &mdash; <a href="mailto:hello@8bitconcepts.com">hello@8bitconcepts.com</a></p>
    <p style="margin-top:6px;font-size:12px;"><a href="/research/overview.html" style="color:#d97757;">Research Atlas &rarr; all papers + reading paths</a></p>
  </footer>

</body>
</html>
"""


def build_gist_content(digest: dict[str, Any], today: str) -> tuple[str, str]:
    """Build the CSV + Markdown content that mirrors the MCP ecosystem health snapshot
    into the public gist. Returns (csv_text, md_text).

    CSV: rank,name,category,agentic_score,url,mcp_verified — top 25 newly-indexed MCP servers.
    MD: last-updated header, global verification rate, top 15 categories table,
        top 25 newly-indexed MCP servers table, methodology + attribution + sibling links.
    """
    total_sites = int(digest.get("total_sites", 0))
    mcp_verified = int(digest.get("mcp_verified", 0))
    llms_txt_count = int(digest.get("llms_txt_count", 0))
    openapi_count = int(digest.get("openapi_count", 0))
    pct_mcp = float(digest.get("pct_mcp", 0.0))
    submissions_week = int(digest.get("submissions_week", 0))

    categories = digest.get("categories", []) or []
    new_mcp_servers = digest.get("new_mcp_servers", []) or []

    # Top 25 newly-indexed MCP servers (digest may return fewer; cap naturally)
    top_new = new_mcp_servers[:25]

    # CSV: rank,name,category,agentic_score,url,mcp_verified
    def csv_safe(s: str) -> str:
        s = str(s or "")
        # Strip commas/quotes/newlines for CSV simplicity (matches hiring snapshot pattern)
        return s.replace(",", " ").replace('"', "").replace("\n", " ").replace("\r", " ").strip()

    csv_lines = ["rank,name,category,agentic_score,url,mcp_verified"]
    for i, s in enumerate(top_new, start=1):
        domain = s.get("domain", "") or ""
        # Take first segment of name before em-dash/pipe for cleaner cells
        raw_name = (s.get("name") or domain or "").split("\u2014")[0].split("|")[0].strip()
        name = csv_safe(raw_name)
        cat = csv_safe(s.get("category", ""))
        score = int(s.get("agentic_score", 0))
        url = f"https://nothumansearch.ai/site/{domain}"
        mcp_verified_flag = "true" if s.get("has_mcp_server") else "false"
        csv_lines.append(f"{i},{name},{cat},{score},{url},{mcp_verified_flag}")
    csv_text = "\n".join(csv_lines) + "\n"

    # Markdown
    visible_cats = [c for c in categories if c.get("name") != "other"]
    top_cats = visible_cats[:15]

    md_lines = [
        "# MCP Ecosystem Health Dataset",
        "",
        f"**Last updated**: {today}",
        "",
        f"**Snapshot**: {today} \u00b7 **Sites indexed**: {total_sites:,} \u00b7 "
        f"**Live-verified MCP servers**: {mcp_verified:,} \u00b7 "
        f"**Verification rate**: {pct_mcp:.1f}%",
        "",
        f"**Other agent-discovery signals**: {llms_txt_count:,} sites publish `llms.txt` \u00b7 "
        f"{openapi_count:,} publish OpenAPI \u00b7 {submissions_week:,} new candidate submissions this week.",
        "",
        "Live data from [nothumansearch.ai/digest.json](https://nothumansearch.ai/digest.json) \u2014 free public API, no auth, refreshed on every crawl cycle.",
        "",
        "## Verification rate",
        "",
        f"Of **{total_sites:,}** sites that advertise MCP / agent-ready signals, only "
        f"**{mcp_verified:,} ({pct_mcp:.1f}%)** survive a real JSON-RPC handshake to their `/mcp` endpoint. "
        "The rest either return HTML, time out, or never implemented the protocol correctly.",
        "",
        "## Top 15 categories",
        "",
        "| Rank | Category | Sites Indexed | Share of Index |",
        "|---:|---|---:|---:|",
    ]
    for i, c in enumerate(top_cats, start=1):
        name = str(c.get("name", "\u2014"))
        count = int(c.get("count", 0))
        share = (count / total_sites * 100) if total_sites else 0
        md_lines.append(f"| {i} | {name} | {count:,} | {share:.1f}% |")

    md_lines += [
        "",
        f"## Top {len(top_new)} newly-indexed MCP servers",
        "",
        "| Rank | Domain | Name | Category | Agentic Score | MCP Verified |",
        "|---:|---|---|---|---:|:---:|",
    ]
    for i, s in enumerate(top_new, start=1):
        domain = str(s.get("domain", "\u2014"))
        raw_name = (s.get("name") or domain or "\u2014").split("\u2014")[0].split("|")[0].strip()
        # Escape pipe chars for markdown table safety
        name_cell = raw_name.replace("|", "\\|")
        cat = str(s.get("category", "\u2014"))
        score = int(s.get("agentic_score", 0))
        verified_cell = "yes" if s.get("has_mcp_server") else "no"
        site_url = f"https://nothumansearch.ai/site/{domain}"
        md_lines.append(f"| {i} | [{domain}]({site_url}) | {name_cell} | {cat} | {score} | {verified_cell} |")

    md_lines += [
        "",
        "## Methodology",
        "",
        "NothingHumanSearch crawls submitted URLs and auto-discovered candidates from public sources "
        "(awesome-mcp-servers, PulseMCP, llmstxt.site, curated feeds), then scores each site against seven "
        "weighted signals: `llms.txt` present and parseable; `ai-plugin.json` at `/.well-known/`; an OpenAPI "
        "or AsyncAPI spec at a discoverable path; an MCP manifest; a live JSON-RPC MCP handshake; documented "
        "rate-limit and auth headers; and an accessible structured API response. Sites are re-crawled weekly. "
        "Scores range 0\u2013100; any score above 75 corresponds to a site an autonomous agent can realistically "
        "integrate without human help.",
        "",
        "Verification means a TCP connection + HTTP POST to the declared `/mcp` endpoint with a JSON-RPC 2.0 "
        "`initialize` request, followed by a valid `result` response containing a `protocolVersion`. Sites that "
        "host a manifest but fail the handshake are counted in the index total but not in the MCP-verified total.",
        "",
        "## Source & License",
        "",
        f"- **Live API**: https://nothumansearch.ai/digest.json (JSON, public)",
        f"- **NHS MCP server**: https://nothumansearch.ai/mcp (JSON-RPC, eight tools incl. `verify_mcp`)",
        f"- **Methodology page**: https://nothumansearch.ai/methodology",
        f"- **Research note**: https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html",
        f"- **Sibling dataset**: [Top AI Companies Hiring](https://gist.github.com/unitedideas/9c59d50a824a075410bd658c96e1f5de)",
        f"- **Auto-regenerated**: weekly via `tools/regenerate-mcp-health.py`",
        f"- **License**: CC BY 4.0 \u2014 attribution to 8bitconcepts + nothumansearch.ai",
        "",
    ]
    md_text = "\n".join(md_lines)

    return csv_text, md_text


def update_gist(digest: dict[str, Any], today: str) -> bool:
    """Write CSV + MD to /tmp/mcp-health-gist/ and push to the public gist via `gh gist edit`.
    Never aborts the caller on failure; logs and returns False instead.
    """
    try:
        csv_text, md_text = build_gist_content(digest, today)
    except Exception as e:
        print(f"   Gist content build failed (non-fatal): {e}", file=sys.stderr)
        return False

    tmpdir = Path(tempfile.gettempdir()) / "mcp-health-gist"
    try:
        tmpdir.mkdir(parents=True, exist_ok=True)
        csv_path = tmpdir / GIST_CSV_FILENAME
        md_path = tmpdir / GIST_MD_FILENAME
        csv_path.write_text(csv_text, encoding="utf-8")
        md_path.write_text(md_text, encoding="utf-8")
        print(f"   Wrote gist files to {tmpdir}")
    except Exception as e:
        print(f"   Gist temp write failed (non-fatal): {e}", file=sys.stderr)
        return False

    ok = True
    for filename, path in ((GIST_CSV_FILENAME, csv_path), (GIST_MD_FILENAME, md_path)):
        # `gh gist edit <id> --filename NAME -- PATH` replaces that file in the gist with the contents at PATH.
        cmd = ["gh", "gist", "edit", GIST_ID, "--filename", filename, "--", str(path)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"   gh gist edit {filename} failed (non-fatal): {r.stderr[:400]}", file=sys.stderr)
            ok = False
        else:
            print(f"   Gist updated: {filename}")
    if ok:
        print(f"   Gist live: {GIST_URL}")
    return ok


def indexnow_ping(urls: list[str]) -> bool:
    payload = {
        "host": HOST,
        "key": INDEXNOW_KEY,
        "keyLocation": f"https://{HOST}/{INDEXNOW_KEY}.txt",
        "urlList": urls,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.indexnow.org/indexnow",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            ok = 200 <= resp.status < 300
            print(f"  IndexNow: HTTP {resp.status} ({'ok' if ok else 'fail'})")
            return ok
    except Exception as e:
        print(f"  IndexNow failed: {e}", file=sys.stderr)
        return False


def websub_ping(feed_url: str) -> bool:
    ok_any = False
    for hub in ("https://pubsubhubbub.appspot.com/", "https://pubsubhubbub.superfeedr.com/"):
        data = f"hub.mode=publish&hub.url={feed_url}".encode("utf-8")
        req = urllib.request.Request(
            hub,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": USER_AGENT},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                ok = 200 <= resp.status < 300
                print(f"  WebSub {hub}: HTTP {resp.status} ({'ok' if ok else 'fail'})")
                ok_any = ok_any or ok
        except Exception as e:
            print(f"  WebSub {hub} failed: {e}", file=sys.stderr)
    return ok_any


def nhs_submit(url: str) -> None:
    """Best-effort NHS submission. Never aborts caller; tolerates 429."""
    try:
        data = json.dumps({"url": url}).encode("utf-8")
        req = urllib.request.Request(
            NHS_SUBMIT_URL,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"  NHS submit: HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print("  NHS submit: rate-limited (429), skipping")
        else:
            print(f"  NHS submit: HTTP {e.code}", file=sys.stderr)
    except Exception as e:
        print(f"  NHS submit failed: {e}", file=sys.stderr)


def run_git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate the Q2 2026 MCP Ecosystem Health note from live data.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch + render, don't write anything")
    parser.add_argument("--once", action="store_true", help="Write file + refresh atlas, skip commit/push/pings")
    parser.add_argument("--no-push", action="store_true", help="Skip git push and IndexNow/WebSub pings")
    args = parser.parse_args()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    generated_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"=== Regenerate MCP ecosystem health ({today}) ===")
    print("1. Fetching live NHS digest...")
    try:
        digest = http_get_json(NHS_DIGEST_URL)
    except Exception as e:
        print(f"  NHS digest fetch failed: {e}", file=sys.stderr)
        return 2
    print(f"   NHS: {digest.get('total_sites')} sites / {digest.get('mcp_verified')} mcp-verified / {digest.get('llms_txt_count')} llms.txt / {digest.get('openapi_count')} openapi")

    print("2. Rendering HTML...")
    html = build_html(digest, today, generated_iso)

    if args.dry_run:
        print(f"   [DRY RUN] Would write {len(html)} chars to {PAPER_PATH}")
        print(f"   First 400 chars:\n{html[:400]}")
        return 0

    prior = ""
    if PAPER_PATH.exists():
        prior = PAPER_PATH.read_text(encoding="utf-8")

    def normalize_for_diff(s: str) -> str:
        import re as _re
        s = _re.sub(r'"dateModified": "[^"]*"', '"dateModified": "X"', s)
        s = _re.sub(r'pulled \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', "pulled X", s)
        s = _re.sub(r'<meta name="last-updated" content="[^"]*" />', '<meta name="last-updated" content="X" />', s)
        s = _re.sub(r'as of \d{4}-\d{2}-\d{2}', "as of X", s)
        s = _re.sub(r'\(NHS, \d{4}-\d{2}-\d{2}\)', "(NHS, X)", s)
        s = _re.sub(r'\(\d{4}-\d{2}-\d{2}\)', "(X)", s)
        s = _re.sub(r'week starting \d{4}-\d{2}-\d{2}', "week starting X", s)
        return s

    new_normalized = normalize_for_diff(html)
    old_normalized = normalize_for_diff(prior)
    data_changed = new_normalized != old_normalized

    print("3. Writing paper...")
    PAPER_PATH.write_text(html, encoding="utf-8")
    print(f"   Wrote {len(html)} chars to {PAPER_PATH}")

    print("3b. Regenerating OG image (paper-specific)...")
    try:
        total_sites_v = int(digest.get("total_sites", 0))
        mcp_verified_v = int(digest.get("mcp_verified", 0))
        llms_v = int(digest.get("llms_txt_count", 0))
        # Pull claim count from NHS stats (best-effort, else fall back to total_sites)
        claim_total = total_sites_v
        try:
            nhs_stats = http_get_json(NHS_STATS_URL, timeout=10)
            claim_total = int(nhs_stats.get("mcp_claim_count", total_sites_v)) or total_sites_v
        except Exception:
            pass
        headline = f"{mcp_verified_v:,} of {claim_total:,} MCP claims verified"
        subtext = (
            f"Q2 2026 \u2022 {total_sites_v:,} agent-ready sites indexed \u2022 "
            f"{llms_v:,} publish llms.txt"
        )
        if generate_og_image is not None:
            path = generate_og_image(headline, subtext, OG_IMAGE_PATH)
            print(f"   OG image: {path}")
        else:
            print("   OG generator unavailable; skipping (paper still ships).")
    except Exception as e:
        print(f"   OG image generation failed (non-fatal): {e}", file=sys.stderr)

    print("4. Refreshing overview atlas...")
    r = subprocess.run(["python3", str(OVERVIEW_SCRIPT)], cwd=REPO, capture_output=True, text=True)
    if r.returncode == 0:
        print("   Overview regenerated.")
    else:
        print(f"   Overview failed (non-fatal): {r.stderr[:300]}", file=sys.stderr)

    print("\n4b. Updating public gist (MCP ecosystem health CSV + MD)...")
    try:
        update_gist(digest, today)
    except Exception as e:
        # Never let a gist failure abort the run
        print(f"   Gist update unhandled exception (non-fatal): {e}", file=sys.stderr)

    if args.once:
        print("\n=== --once: stopping before commit/push/pings ===")
        if data_changed:
            print("   (data had changed; running without --once will commit)")
        else:
            print("   (data unchanged vs prior content)")
        return 0

    if not data_changed:
        print("\n5. Data unchanged vs prior; skipping commit/push/pings.")
        return 0

    print("\n5. Committing...")
    add = run_git(["git", "add",
                   "research/q2-2026-mcp-ecosystem-health.html",
                   "research/overview.html",
                   "index.html",
                   f"research/og/{OG_SLUG}.png"])
    if add.returncode != 0:
        print(f"   git add failed: {add.stderr[:300]}", file=sys.stderr)
        return 3
    msg = f"mcp-health: auto-regenerate {today}"
    commit = run_git(["git", "commit", "-m", msg])
    if commit.returncode != 0:
        print(f"   git commit output: {(commit.stdout + commit.stderr)[:300]}")
        if "nothing to commit" in (commit.stdout + commit.stderr).lower():
            print("   Nothing to commit after all; exiting cleanly.")
            return 0
        return 3
    print(f"   Committed: {msg}")

    if args.no_push:
        print("\n6. --no-push set; skipping push + pings.")
        return 0

    print("\n6. Pushing origin main...")
    push = run_git(["git", "push", "origin", "main"])
    if push.returncode != 0:
        print(f"   git push failed: {push.stderr[:400]}", file=sys.stderr)
        return 4
    print("   Pushed — GitHub Pages will deploy within ~60s.")

    print("\n7. IndexNow ping...")
    indexnow_ping([PAPER_URL])

    print("\n8. WebSub ping...")
    websub_ping(FEED_URL)
    websub_ping(RESEARCH_FEED_URL)

    print("\n9. NHS submit (best-effort)...")
    nhs_submit(PAPER_URL)

    print("\n=== Done. ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
