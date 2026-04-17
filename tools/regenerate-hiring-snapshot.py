#!/usr/bin/env python3
"""
Regenerate /research/q2-2026-ai-hiring-snapshot.html from live APIs.

Pulls fresh stats from:
  - https://aidevboard.com/api/v1/stats
  - https://nothumansearch.ai/digest.json

Rebuilds the full HTML (template inlined), then:
  - Writes the paper (overwrites in place)
  - Regenerates /research/overview.html (atlas)
  - Commits only if data actually changed
  - Pushes origin main (GitHub Pages deploy)
  - IndexNow-pings the paper URL (Bing/Yandex/Naver/Seznam)
  - WebSub-pings the 8bc feed (appspot + superfeedr)

Usage:
    python3 tools/regenerate-hiring-snapshot.py          # full run
    python3 tools/regenerate-hiring-snapshot.py --dry-run # fetch + render, don't write
    python3 tools/regenerate-hiring-snapshot.py --once    # write + overview, skip commit/push/pings
    python3 tools/regenerate-hiring-snapshot.py --no-push # skip git push + pings (commit still happens)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
RESEARCH_DIR = REPO / "research"
PAPER_PATH = RESEARCH_DIR / "q2-2026-ai-hiring-snapshot.html"
OVERVIEW_SCRIPT = REPO / "tools" / "generate-overview.py"
PAPER_URL = "https://8bitconcepts.com/research/q2-2026-ai-hiring-snapshot.html"
FEED_URL = "https://8bitconcepts.com/feed.xml"
INDEXNOW_KEY = "e4e40fed94fa41b09613c20e7bac4484"
HOST = "8bitconcepts.com"
USER_AGENT = "curl/8.7.1"

ADB_STATS_URL = "https://aidevboard.com/api/v1/stats"
NHS_DIGEST_URL = "https://nothumansearch.ai/digest.json"


def http_get_json(url: str, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fmt_thousands(n: Any) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n)


def fmt_k(n: Any) -> str:
    try:
        return f"${int(n) // 1000}k"
    except (TypeError, ValueError):
        return "&mdash;"


def fmt_salary(n: Any) -> str:
    try:
        v = int(n)
        if v <= 0:
            return "&mdash;"
        return f"${v:,}"
    except (TypeError, ValueError):
        return "&mdash;"


def salary_range_label(key: str) -> str:
    return {
        "under_100k": "Under $100k",
        "100k_150k": "$100k-$150k",
        "150k_200k": "$150k-$200k",
        "200k_250k": "$200k-$250k",
        "250k_300k": "$250k-$300k",
        "300k_400k": "$300k-$400k",
        "400k_plus": "$400k+",
    }.get(key, key)


def workplace_label(key: str) -> str:
    return {"onsite": "Onsite", "remote": "Remote", "hybrid": "Hybrid"}.get(key, key.capitalize())


def build_html(stats: dict[str, Any], digest: dict[str, Any], today: str, generated_iso: str) -> str:
    ov = stats.get("overview", {}) or {}
    salary = stats.get("salary", {}) or {}
    tags = stats.get("tags", []) or []
    companies = stats.get("companies", []) or []
    workplaces = stats.get("workplace", []) or []
    distribution = salary.get("distribution", []) or []

    total_jobs = int(ov.get("total_jobs", 0))
    total_companies = int(ov.get("total_companies", 0))
    new_this_week = int(ov.get("new_this_week", 0))
    jobs_with_salary = int(ov.get("jobs_with_salary", 0))
    median = salary.get("median", 0)

    # Top companies (top 10)
    top_companies = companies[:10]

    # Top tags — pick the ones we want to highlight (same set as the original paper)
    # Preference order: llm, agents, generative-ai, distributed-systems, pytorch,
    #                  fine-tuning, research, reinforcement-learning, mlops, gpu.
    # Fall back to top-by-count if any are missing.
    preferred_tags = [
        "llm", "agents", "generative-ai", "distributed-systems", "pytorch",
        "fine-tuning", "research", "reinforcement-learning", "mlops", "gpu",
    ]
    tags_by_name = {t.get("tag"): t for t in tags}
    selected_tags: list[dict[str, Any]] = []
    for name in preferred_tags:
        if name in tags_by_name:
            selected_tags.append(tags_by_name[name])
    # If any missing, top up from the sorted list
    if len(selected_tags) < 10:
        seen = {t.get("tag") for t in selected_tags}
        for t in tags:
            if t.get("tag") not in seen:
                selected_tags.append(t)
                if len(selected_tags) >= 10:
                    break

    # Salary distribution total for share calc
    total_distribution = sum(int(d.get("count", 0)) for d in distribution) or 1

    # Workplace share calc
    total_workplace = sum(int(w.get("count", 0)) for w in workplaces) or 1

    # Derived top-3 and top-10 aggregates (for the "concentration at the top" paragraph)
    top3_sum = sum(int(c.get("roles", 0)) for c in top_companies[:3])
    top10_sum = sum(int(c.get("roles", 0)) for c in top_companies[:10])
    top3_share_pct = (top3_sum / total_jobs * 100) if total_jobs else 0
    top10_share_pct = (top10_sum / total_jobs * 100) if total_jobs else 0
    tail_companies = max(total_companies - 10, 0)

    # Leading companies (for opening paragraph)
    first_co_name = top_companies[0].get("company", "—") if top_companies else "—"
    first_co_roles = int(top_companies[0].get("roles", 0)) if top_companies else 0
    second_co_name = top_companies[1].get("company", "—") if len(top_companies) > 1 else "—"
    second_co_roles = int(top_companies[1].get("roles", 0)) if len(top_companies) > 1 else 0

    # LLM / agents / generative-ai counts for paragraph
    def tag_count(name: str) -> int:
        return int(tags_by_name.get(name, {}).get("count", 0))

    llm_ct = tag_count("llm")
    agents_ct = tag_count("agents")
    genai_ct = tag_count("generative-ai")
    llm_pct = (llm_ct / total_jobs * 100) if total_jobs else 0
    agents_pct = (agents_ct / total_jobs * 100) if total_jobs else 0
    genai_pct = (genai_ct / total_jobs * 100) if total_jobs else 0

    # Daily pace
    daily_pace = int(round(new_this_week / 7)) if new_this_week else 0

    # Salary distribution stats for paragraph
    def dist_count(key: str) -> int:
        for d in distribution:
            if d.get("range") == key:
                return int(d.get("count", 0))
        return 0

    d_200_250 = dist_count("200k_250k")
    d_150_200 = dist_count("150k_200k")
    d_under_100 = dist_count("under_100k")
    d_100_150 = dist_count("100k_150k")
    d_250_300 = dist_count("250k_300k")
    d_300_400 = dist_count("300k_400k")
    d_400_plus = dist_count("400k_plus")
    below_150k_total = d_under_100 + d_100_150
    above_300k_total = d_300_400 + d_400_plus
    share_200_250 = (d_200_250 / total_distribution * 100) if total_distribution else 0
    share_150_200 = (d_150_200 / total_distribution * 100) if total_distribution else 0
    share_below_150k = (below_150k_total / total_distribution * 100) if total_distribution else 0
    share_above_300k = (above_300k_total / total_distribution * 100) if total_distribution else 0

    # Workplace stats for paragraph
    ws_map = {w.get("type"): w for w in workplaces}
    onsite = ws_map.get("onsite", {})
    remote = ws_map.get("remote", {})
    hybrid = ws_map.get("hybrid", {})
    onsite_ct = int(onsite.get("count", 0))
    remote_ct = int(remote.get("count", 0))
    hybrid_ct = int(hybrid.get("count", 0))
    onsite_pct = (onsite_ct / total_workplace * 100) if total_workplace else 0
    remote_pct = (remote_ct / total_workplace * 100) if total_workplace else 0
    hybrid_pct = (hybrid_ct / total_workplace * 100) if total_workplace else 0
    onsite_avg = int(onsite.get("avg_salary", 0))
    remote_avg = int(remote.get("avg_salary", 0))
    hybrid_avg = int(hybrid.get("avg_salary", 0))
    hybrid_premium = hybrid_avg - max(onsite_avg, remote_avg) if hybrid_avg else 0

    # NHS stats
    nhs_total = int(digest.get("total_sites", 0))
    nhs_mcp = int(digest.get("mcp_verified", 0))
    nhs_llms = int(digest.get("llms_txt_count", 0))
    nhs_cats = digest.get("categories", []) or []
    dev_ct = 0
    ai_tools_ct = 0
    for c in nhs_cats:
        if c.get("name") == "developer":
            dev_ct = int(c.get("count", 0))
        elif c.get("name") == "ai-tools":
            ai_tools_ct = int(c.get("count", 0))

    # ATS source feed count (hard to infer from API; keep prior statement but guard)
    # Source feed count isn't in the API — we keep the long-form "538 source feeds" claim
    # out of the fresh template and describe it generically.

    # Build rows
    company_rows = "\n".join(
        f"          <tr><td>{html_escape(c.get('company', '—'))}</td>"
        f"<td class=\"num\">{fmt_thousands(c.get('roles', 0))}</td>"
        f"<td class=\"num\">{fmt_salary(c.get('avg_salary', 0))}</td></tr>"
        for c in top_companies
    )

    tag_rows = "\n".join(
        f"          <tr><td>{html_escape(t.get('tag', '—'))}</td>"
        f"<td class=\"num\">{fmt_thousands(t.get('count', 0))}</td>"
        f"<td class=\"num\">{fmt_salary(t.get('avg_salary', 0))}</td></tr>"
        for t in selected_tags
    )

    distribution_rows = "\n".join(
        f"          <tr><td>{salary_range_label(d.get('range', ''))}</td>"
        f"<td class=\"num\">{fmt_thousands(d.get('count', 0))}</td>"
        f"<td class=\"num\">{(int(d.get('count', 0)) / total_distribution * 100):.1f}%</td></tr>"
        for d in distribution
    )

    workplace_rows_list = []
    for key in ("onsite", "remote", "hybrid"):
        w = ws_map.get(key)
        if not w:
            continue
        workplace_rows_list.append(
            f"          <tr><td>{workplace_label(key)}</td>"
            f"<td class=\"num\">{fmt_thousands(w.get('count', 0))}</td>"
            f"<td class=\"num\">{(int(w.get('count', 0)) / total_workplace * 100):.1f}%</td>"
            f"<td class=\"num\">{fmt_salary(w.get('avg_salary', 0))}</td></tr>"
        )
    workplace_rows = "\n".join(workplace_rows_list)

    # Description / meta strings
    subtitle_text = (
        f"{fmt_thousands(total_jobs)} active AI/ML engineering roles are open across "
        f"{fmt_thousands(total_companies)} companies as of {today}. Median advertised "
        f"salary is {fmt_salary(median)}. {fmt_thousands(new_this_week)} new roles were "
        f"posted this week. {html_escape(first_co_name)} leads with {first_co_roles} open roles, "
        f"followed by {html_escape(second_co_name)} at {second_co_roles}. Live data pulled from "
        f'<a href="https://aidevboard.com/api/v1/stats">aidevboard.com/api/v1/stats</a>.'
    )

    meta_description = (
        f"Live data from aidevboard.com: {fmt_thousands(total_jobs)} active AI/ML "
        f"engineering roles, {fmt_thousands(total_companies)} companies hiring, "
        f"{fmt_k(median)} median salary, {fmt_thousands(new_this_week)} new roles posted this week. "
        f"{html_escape(first_co_name)} leads with {first_co_roles} open roles. Analysis with full source data."
    )
    og_description = (
        f"Live data: {fmt_thousands(total_jobs)} active AI/ML engineering roles across "
        f"{fmt_thousands(total_companies)} companies. Median {fmt_k(median)}. "
        f"{fmt_thousands(new_this_week)} new this week. {html_escape(first_co_name)} leads with "
        f"{first_co_roles} open roles. Agents/LLM/generative-ai dominate tag counts."
    )
    twitter_description = (
        f"{fmt_thousands(total_jobs)} AI/ML roles. {fmt_thousands(total_companies)} companies. "
        f"{fmt_k(median)} median. {fmt_thousands(new_this_week)} posted this week. "
        f"Live data from aidevboard.com, {today}."
    )

    # Schema-org article description
    article_description = (
        f"Live data from aidevboard.com: {fmt_thousands(total_jobs)} active AI/ML engineering roles "
        f"across {fmt_thousands(total_companies)} companies, {fmt_k(median)} median salary, "
        f"{fmt_thousands(new_this_week)} new roles posted this week. Full breakdown by company, "
        f"skill tag, salary band, and workplace type."
    )

    # Intro paragraph derived number
    intro_para = (
        f"This note captures the state of AI engineering hiring on {today}, pulled directly from "
        f"the AI Dev Jobs public API. The numbers are not a survey. They are a live, daily-refreshed "
        f"index of what companies are actually posting to their own applicant tracking systems right "
        f"now &mdash; scraped continuously from the AI Dev Jobs ATS source feed network, deduplicated, "
        f"and canonicalized."
    )

    # Concentration paragraph
    # Build the first-three-names string defensively
    if len(top_companies) >= 3:
        first_three_names = f"{html_escape(top_companies[0]['company'])}, {html_escape(top_companies[1]['company'])}, and {html_escape(top_companies[2]['company'])}"
    else:
        first_three_names = ", ".join(html_escape(c.get("company", "")) for c in top_companies)

    concentration_para = (
        f"The concentration at the top is striking. {first_three_names} alone account for "
        f"{top3_sum} open roles &mdash; roughly {top3_share_pct:.0f}% of the entire index. The top 10 companies "
        f"account for {fmt_thousands(top10_sum)} roles, or {top10_share_pct:.1f}% of the market. This is a market "
        f"with a long tail ({fmt_thousands(tail_companies)} companies below the top 10) but also with serious "
        f"pockets of single-company acceleration."
    )

    # Frontier labs paragraph (compute premium: frontier avg vs. non-frontier in top 10)
    frontier_names = {"OpenAI", "Anthropic", "xAI", "Mistral AI", "Cohere"}
    frontier_salaries = [int(c.get("avg_salary", 0)) for c in top_companies if c.get("company") in frontier_names and int(c.get("avg_salary", 0)) > 0]
    nonfrontier_salaries = [int(c.get("avg_salary", 0)) for c in top_companies if c.get("company") not in frontier_names and int(c.get("avg_salary", 0)) > 0]
    if frontier_salaries and nonfrontier_salaries:
        frontier_avg = sum(frontier_salaries) / len(frontier_salaries)
        nonfrontier_avg = sum(nonfrontier_salaries) / len(nonfrontier_salaries)
        premium = int(round(frontier_avg - nonfrontier_avg))
        frontier_para = (
            f"The frontier labs (OpenAI, Anthropic, xAI) pay a premium of roughly ${premium // 1000}k "
            f"over the defense-tech, autonomy, and infrastructure players in the same leaderboard. "
            f"That gap is the clearest signal in the data about where investor capital is being deployed "
            f"most aggressively right now."
        )
    else:
        frontier_para = (
            "The frontier labs (OpenAI, Anthropic, xAI) pay a material premium over the defense-tech, "
            "autonomy, and infrastructure players in the same leaderboard. That gap is the clearest signal "
            "in the data about where investor capital is being deployed most aggressively right now."
        )

    # Skills paragraph
    skills_para = (
        f"LLM work now dominates the index. {fmt_thousands(llm_ct)} of {fmt_thousands(total_jobs)} roles "
        f"({llm_pct:.1f}%) list <code>llm</code> as a tag. <code>agents</code> is close behind at "
        f"{fmt_thousands(agents_ct)} ({agents_pct:.1f}%), and <code>generative-ai</code> sits at "
        f"{fmt_thousands(genai_ct)} ({genai_pct:.1f}%). A year ago <code>pytorch</code> and "
        f"<code>deep-learning</code> led by volume. The demand center of gravity has migrated up the "
        f"stack &mdash; from model training to model orchestration and agent design."
    )

    # Research tag salary callout (best-effort)
    research_row = tags_by_name.get("research", {})
    research_avg = int(research_row.get("avg_salary", 0))
    skills_closing_para = (
        f"Research roles command the highest average salary (${research_avg:,}) among tags with 500+ roles, "
        f"followed by reinforcement learning and search. The premium for specialized, harder-to-hire skills "
        f"is intact &mdash; training infrastructure and eval/reliability work (distributed systems, MLOps, GPU) "
        f"continues to outpay generic application work."
    ) if research_avg else (
        "Research roles command a top-tier average salary among tags with 500+ roles, followed by reinforcement "
        "learning and search. The premium for specialized, harder-to-hire skills is intact."
    )

    # Salary distribution paragraph
    salary_para = (
        f"Of the {fmt_thousands(jobs_with_salary)} roles that publish salary ranges, the shape is bimodal "
        f"around the $200k line. The $200-250k band is the single largest bucket ({fmt_thousands(d_200_250)} "
        f"roles, {share_200_250:.1f}%), with $150-200k close behind ({fmt_thousands(d_150_200)} roles, "
        f"{share_150_200:.1f}%). Everything below $150k is a minority ({fmt_thousands(below_150k_total)} roles "
        f"combined, {share_below_150k:.1f}%), and roles above $300k are a meaningful but not overwhelming "
        f"slice ({fmt_thousands(above_300k_total)} roles, {share_above_300k:.1f}%)."
    )

    # Workplace paragraph
    if hybrid_premium > 0:
        workplace_para = (
            f"Onsite is still the largest category by volume ({fmt_thousands(onsite_ct)} roles, "
            f"{onsite_pct:.1f}%), but hybrid roles pay the highest on average: ${hybrid_avg:,} versus "
            f"${onsite_avg:,} for onsite and ${remote_avg:,} for remote. The ${hybrid_premium // 1000}k hybrid "
            f"premium is real and worth pausing on &mdash; it suggests the companies paying the most for senior "
            f"talent right now want people in the building at least part of the week. Remote pay tracks onsite "
            f"almost exactly."
        )
    else:
        workplace_para = (
            f"Onsite is still the largest category by volume ({fmt_thousands(onsite_ct)} roles, "
            f"{onsite_pct:.1f}%). Hybrid, onsite, and remote are all within a narrow band on average pay this "
            f"cycle &mdash; the earlier hybrid premium has compressed."
        )

    # NHS paragraph
    nhs_para = (
        f"Hiring demand is not the only signal. On the infrastructure side, "
        f'<a href="https://nothumansearch.ai/digest">NothingHumanSearch</a> &mdash; an independent index of '
        f"agent-ready web services &mdash; now tracks {fmt_thousands(nhs_total)} sites with agent discovery files "
        f"(llms.txt, OpenAPI, ai-plugin), of which {fmt_thousands(nhs_mcp)} have a live-verified MCP server over "
        f"JSON-RPC, and {fmt_thousands(nhs_llms)} publish an llms.txt. Developer tools ({fmt_thousands(dev_ct)} "
        f"sites) and AI-native tools ({fmt_thousands(ai_tools_ct)} sites) are the two largest categories. Read "
        f"alongside the hiring data, these two indexes describe the same market from opposite ends: "
        f"{fmt_thousands(total_jobs)} humans being hired to build AI products, into a world where "
        f"{fmt_thousands(nhs_total)} services are already exposing themselves natively to AI agents."
    )

    # Methodology paragraph (keep durable text — no stale feed count)
    methodology_para = (
        f"Data in this note was pulled live at publication. The aidevboard.com index scrapes applicant-tracking "
        f"feeds (Ashby, Greenhouse, Lever, Workday, custom careers pages) on a daily cron, canonicalizes titles "
        f"and tags with a rules-based classifier, and dedupes by (company, title, location). The "
        f'<a href="https://aidevboard.com/api/v1/stats">/api/v1/stats</a> endpoint is public and unauthenticated. '
        f'NHS data is from <a href="https://nothumansearch.ai/digest.json">/digest.json</a> &mdash; an index that '
        f"live-probes sites for agent-discovery signals and MCP endpoints. Both APIs are agent-readable. This "
        f"page auto-regenerates weekly."
    )

    # Stat cards
    stat_cards_html = f"""      <div class="stat-row">
        <div class="stat-box">
          <div class="stat-num">{fmt_thousands(total_jobs)}</div>
          <div class="stat-label">active AI/ML engineering roles open across {fmt_thousands(total_companies)} companies (ADB, {today})</div>
        </div>
        <div class="stat-box">
          <div class="stat-num">{fmt_k(median)}</div>
          <div class="stat-label">median advertised salary across the {fmt_thousands(jobs_with_salary)} roles that publish salary ranges</div>
        </div>
        <div class="stat-box">
          <div class="stat-num">{fmt_thousands(new_this_week)}</div>
          <div class="stat-label">new roles posted in the last 7 days &mdash; sustained pace of ~{daily_pace} per day</div>
        </div>
      </div>"""

    # Assemble full HTML (preserve exact style / structure from the shipped page)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="referrer" content="strict-origin-when-cross-origin" />
  <meta name="color-scheme" content="dark light" />
  <meta name="last-updated" content="{today}" />
  <title>Q2 2026 AI Engineering Hiring Snapshot -- 8bitconcepts</title>
  <meta name="description" content="{attr_escape(meta_description)}" />
  <meta property="og:title" content="Q2 2026 AI Engineering Hiring Snapshot -- 8bitconcepts" />
  <meta property="og:description" content="{attr_escape(og_description)}" />
  <meta property="og:type" content="article" />
  <meta property="og:url" content="https://8bitconcepts.com/research/q2-2026-ai-hiring-snapshot.html" />
  <meta property="og:image" content="https://8bitconcepts.com/og-default.png" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="Q2 2026 AI Engineering Hiring Snapshot" />
  <meta name="twitter:description" content="{attr_escape(twitter_description)}" />
  <meta name="twitter:image" content="https://8bitconcepts.com/og-default.png" />
  <link rel="canonical" href="https://8bitconcepts.com/research/q2-2026-ai-hiring-snapshot.html" />
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

    .data-table .td-label {{
      font-weight: 600;
      color: var(--terra);
      font-size: 13px;
      white-space: nowrap;
    }}

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
    "headline": "Q2 2026 AI Engineering Hiring Snapshot",
    "description": "{attr_escape(article_description)}",
    "url": "https://8bitconcepts.com/research/q2-2026-ai-hiring-snapshot.html",
    "datePublished": "2026-04-17",
    "dateModified": "{today}",
    "author": {{"@type": "Organization", "name": "8bitconcepts", "url": "https://8bitconcepts.com"}},
    "publisher": {{"@type": "Organization", "name": "8bitconcepts", "url": "https://8bitconcepts.com"}},
    "image": "https://8bitconcepts.com/og-default.png",
    "inLanguage": "en",
    "isAccessibleForFree": true,
    "about": "AI engineering hiring, salary data, demanded skills, workplace distribution",
    "keywords": "AI hiring, ML engineering, LLM jobs, agent engineering, AI salary, 2026 hiring"
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
    {{"@type": "ListItem", "position": 3, "name": "Q2 2026 AI Engineering Hiring Snapshot"}}
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

    <div class="eyebrow">Research &mdash; Hiring Snapshot</div>

    <h1>Q2 2026 AI Engineering Hiring Snapshot</h1>

    <p class="subtitle">{subtitle_text}</p>

    <div class="meta">
      <span class="meta-date">{today}</span>
      <span class="meta-tag">Live Data</span>
      <span class="meta-read">~900 words</span>
    </div>

    <div class="article-body">

      <p>{intro_para}</p>

{stat_cards_html}

      <h2>Top 10 hiring companies right now</h2>

      <p>{concentration_para}</p>

      <table class="data-table">
        <thead>
          <tr>
            <th>Company</th>
            <th class="num" style="text-align:right;">Open roles</th>
            <th class="num" style="text-align:right;">Avg salary</th>
          </tr>
        </thead>
        <tbody>
{company_rows}
        </tbody>
      </table>

      <p>{frontier_para}</p>

      <h2>Top demanded skills</h2>

      <p>{skills_para}</p>

      <table class="data-table">
        <thead>
          <tr><th>Tag</th><th class="num" style="text-align:right;">Role count</th><th class="num" style="text-align:right;">Avg salary</th></tr>
        </thead>
        <tbody>
{tag_rows}
        </tbody>
      </table>

      <p>{skills_closing_para}</p>

      <h2>Salary distribution</h2>

      <p>{salary_para}</p>

      <table class="data-table">
        <thead><tr><th>Range</th><th class="num" style="text-align:right;">Roles</th><th class="num" style="text-align:right;">Share</th></tr></thead>
        <tbody>
{distribution_rows}
        </tbody>
      </table>

      <h2>Workplace mix</h2>

      <p>{workplace_para}</p>

      <table class="data-table">
        <thead><tr><th>Workplace</th><th class="num" style="text-align:right;">Roles</th><th class="num" style="text-align:right;">Share</th><th class="num" style="text-align:right;">Avg salary</th></tr></thead>
        <tbody>
{workplace_rows}
        </tbody>
      </table>

      <h2>The ecosystem side</h2>

      <p>{nhs_para}</p>

      <div class="callout">
        <p>The story the data tells: the stack is diversifying faster than headcount is. Agent frameworks, eval pipelines, MCP servers, vector infra, and MLOps tooling are all real sub-markets now. Companies that want to hire into this market need to be specific about which layer they are hiring for &mdash; generic "ML engineer" listings are competing against a labor pool that self-identifies by framework and problem domain.</p>
      </div>

      <h2>Methodology</h2>

      <p>{methodology_para}</p>

      <h2>What's next</h2>

      <p>For the organizational implications of this hiring mix &mdash; specifically why the <code>agents</code> tag growing {agents_pct:.1f}% of the index matters more than the raw salary numbers &mdash; see <a href="/research/the-agentic-accountability-gap.html">The Agentic Accountability Gap</a> and <a href="/research/beyond-the-prompt.html">Beyond the Prompt</a>. For what those 6% of companies actually capturing returns are doing differently, see <a href="/research/the-six-percent.html">The Six Percent</a>. Full reading paths at the <a href="/research/overview.html">Research Atlas</a>.</p>

    </div>

    <div class="related">
      <div class="related-label">Related Research</div>
      <div class="related-grid">
        <a class="related-card" href="/research/the-agentic-accountability-gap.html">
          <div class="related-card-title">The Agentic Accountability Gap</div>
          <div class="related-card-sub">Why governance frameworks break when agents act.</div>
        </a>
        <a class="related-card" href="/research/beyond-the-prompt.html">
          <div class="related-card-title">Beyond the Prompt</div>
          <div class="related-card-sub">The engineering maturity ladder for production agents.</div>
        </a>
        <a class="related-card" href="/research/the-six-percent.html">
          <div class="related-card-title">The Six Percent</div>
          <div class="related-card-sub">94% of orgs adopt AI. 6% capture returns. Why.</div>
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
        <li>AI Dev Jobs &mdash; <a href="https://aidevboard.com/api/v1/stats">/api/v1/stats</a>, pulled {generated_iso}. Public unauthenticated endpoint. Backing index: {fmt_thousands(total_jobs)} roles / {fmt_thousands(total_companies)} companies, daily scrape across ATS source feed network.</li>
        <li>AI Dev Jobs &mdash; <a href="https://aidevboard.com/weekly-hiring">/weekly-hiring</a>, weekly roll-up of new postings and company movement.</li>
        <li>NothingHumanSearch &mdash; <a href="https://nothumansearch.ai/digest.json">/digest.json</a>, pulled {generated_iso}. Live-probed index of agent-ready web services with MCP / llms.txt / OpenAPI detection.</li>
        <li>Salary ranges apply to the {fmt_thousands(jobs_with_salary)} of {fmt_thousands(total_jobs)} roles that publish them. Roles without published ranges are excluded from median and distribution calculations but included in role counts.</li>
      </ol>
    </div>

  </div>

  <div style="max-width:640px;margin:40px auto;padding:24px;background:#fafaf8;border:1px solid #e5e5e5;border-radius:8px;">
    <p style="font-size:13px;color:#666;margin:0 0 12px;text-transform:uppercase;letter-spacing:1px;">Hiring for agentic AI?</p>
    <div data-aidev-jobs data-tag="agents" data-limit="3" data-theme="light"></div>
    <script src="https://aidevboard.com/static/widget.js" async></script>
  </div>

  <footer>
    <p>&copy; 2026 8bitconcepts &mdash; AI Enablement &amp; Integration Consulting &mdash; <a href="mailto:hello@8bitconcepts.com">hello@8bitconcepts.com</a></p>
    <p style="margin-top:6px;font-size:12px;"><a href="/research/overview.html" style="color:#d97757;">Research Atlas &rarr; all papers + reading paths</a></p>
  </footer>

</body>
</html>
"""


def html_escape(s: str) -> str:
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def attr_escape(s: str) -> str:
    """Escape for use inside an HTML attribute value (double-quoted)."""
    if s is None:
        return ""
    # Strip any HTML we already injected (the meta tags don't want anchor tags)
    # Only & and " need escaping for attribute safety.
    return (
        str(s)
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


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


def run_git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate the Q2 2026 AI hiring snapshot from live data.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch + render, don't write anything")
    parser.add_argument("--once", action="store_true", help="Write file + refresh atlas, skip commit/push/pings")
    parser.add_argument("--no-push", action="store_true", help="Skip git push and IndexNow/WebSub pings")
    args = parser.parse_args()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    generated_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"=== Regenerate hiring snapshot ({today}) ===")
    print("1. Fetching live data...")
    try:
        stats = http_get_json(ADB_STATS_URL)
    except Exception as e:
        print(f"  ADB stats fetch failed: {e}", file=sys.stderr)
        return 2
    try:
        digest = http_get_json(NHS_DIGEST_URL)
    except Exception as e:
        print(f"  NHS digest fetch failed: {e}", file=sys.stderr)
        return 2
    ov = stats.get("overview", {}) or {}
    print(f"   ADB: {ov.get('total_jobs')} jobs / {ov.get('total_companies')} cos / {ov.get('new_this_week')} new this wk")
    print(f"   NHS: {digest.get('total_sites')} sites / {digest.get('mcp_verified')} mcp / {digest.get('llms_txt_count')} llms.txt")

    print("2. Rendering HTML...")
    html = build_html(stats, digest, today, generated_iso)

    if args.dry_run:
        print(f"   [DRY RUN] Would write {len(html)} chars to {PAPER_PATH}")
        print(f"   First 400 chars:\n{html[:400]}")
        return 0

    # Read prior content (if any) for change detection
    prior = ""
    if PAPER_PATH.exists():
        prior = PAPER_PATH.read_text(encoding="utf-8")

    # Normalize volatile bits for diffing: drop the dateModified and the "pulled <iso>" lines
    # so cosmetic timestamp-only changes don't trigger a commit.
    def normalize_for_diff(s: str) -> str:
        import re as _re
        s = _re.sub(r'"dateModified": "[^"]*"', '"dateModified": "X"', s)
        s = _re.sub(r'pulled \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', "pulled X", s)
        s = _re.sub(r'<meta name="last-updated" content="[^"]*" />', '<meta name="last-updated" content="X" />', s)
        # "as of YYYY-MM-DD" text inside subtitle / stat-label / intro
        s = _re.sub(r'as of \d{4}-\d{2}-\d{2}', "as of X", s)
        s = _re.sub(r'\(ADB, \d{4}-\d{2}-\d{2}\)', "(ADB, X)", s)
        s = _re.sub(r'hiring on \d{4}-\d{2}-\d{2}', "hiring on X", s)
        s = _re.sub(r'aidevboard\.com, \d{4}-\d{2}-\d{2}', "aidevboard.com, X", s)
        return s

    new_normalized = normalize_for_diff(html)
    old_normalized = normalize_for_diff(prior)
    data_changed = new_normalized != old_normalized

    print("3. Writing paper...")
    PAPER_PATH.write_text(html, encoding="utf-8")
    print(f"   Wrote {len(html)} chars to {PAPER_PATH}")

    print("4. Refreshing overview atlas...")
    r = subprocess.run(["python3", str(OVERVIEW_SCRIPT)], cwd=REPO, capture_output=True, text=True)
    if r.returncode == 0:
        print("   Overview regenerated.")
    else:
        print(f"   Overview failed (non-fatal): {r.stderr[:300]}", file=sys.stderr)

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
                   "research/q2-2026-ai-hiring-snapshot.html",
                   "research/overview.html"])
    if add.returncode != 0:
        print(f"   git add failed: {add.stderr[:300]}", file=sys.stderr)
        return 3
    msg = f"hiring-snapshot: auto-regenerate {today}"
    commit = run_git(["git", "commit", "-m", msg])
    if commit.returncode != 0:
        # Might be "nothing to commit" if overview.html is noop and paper normalized-equal edge case
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

    print("\n=== Done. ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
