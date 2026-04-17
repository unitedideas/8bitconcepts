#!/usr/bin/env python3
"""
Regenerate /research/q2-2026-ai-compensation-by-skill.html from live ADB stats.

Pulls fresh stats from:
  - https://aidevboard.com/api/v1/stats

Rebuilds the full HTML (template inlined), then:
  - Writes the paper (overwrites in place)
  - Regenerates /research/overview.html (atlas)
  - Updates the public gist (CSV + Markdown of top 20 tags by avg_salary)
  - Commits only if data actually changed
  - Pushes origin main (GitHub Pages deploy)
  - IndexNow-pings the paper URL (Bing/Yandex/Naver/Seznam)
  - WebSub-pings the 8bc feed (appspot + superfeedr)

Usage:
    python3 tools/regenerate-compensation-by-skill.py          # full run
    python3 tools/regenerate-compensation-by-skill.py --dry-run # fetch + render, don't write
    python3 tools/regenerate-compensation-by-skill.py --once    # write + overview, skip commit/push/pings
    python3 tools/regenerate-compensation-by-skill.py --no-push # skip git push + pings (commit still happens)
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
PAPER_PATH = RESEARCH_DIR / "q2-2026-ai-compensation-by-skill.html"
OVERVIEW_SCRIPT = REPO / "tools" / "generate-overview.py"
PAPER_URL = "https://8bitconcepts.com/research/q2-2026-ai-compensation-by-skill.html"

OG_SLUG = "q2-2026-ai-compensation-by-skill"
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
INDEXNOW_KEY = "e4e40fed94fa41b09613c20e7bac4484"
HOST = "8bitconcepts.com"
USER_AGENT = "curl/8.7.1"

ADB_STATS_URL = "https://aidevboard.com/api/v1/stats"

# Public gist: https://gist.github.com/unitedideas/b1b80d11f0f187f93fd6b1a599df418e
GIST_ID = "b1b80d11f0f187f93fd6b1a599df418e"
GIST_CSV_FILENAME = "ai-compensation-by-skill.csv"
GIST_MD_FILENAME = "ai-compensation-by-skill.md"
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


def fmt_k(n: Any) -> str:
    try:
        v = int(n)
        if v <= 0:
            return "&mdash;"
        return f"${v // 1000}k"
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


def level_label(key: str) -> str:
    return {
        "junior": "Junior",
        "mid": "Mid",
        "senior": "Senior",
        "lead": "Lead",
        "principal": "Principal",
    }.get(key, key.capitalize() if key else "—")


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


def build_html(stats: dict[str, Any], today: str, generated_iso: str) -> str:
    ov = stats.get("overview", {}) or {}
    salary = stats.get("salary", {}) or {}
    tags = stats.get("tags", []) or []
    experience_levels = stats.get("experience_levels", []) or []
    distribution = salary.get("distribution", []) or []

    total_jobs = int(ov.get("total_jobs", 0))
    total_companies = int(ov.get("total_companies", 0))
    jobs_with_salary = int(ov.get("jobs_with_salary", 0))
    median = int(salary.get("median", 0) or 0)
    avg_overall = int(salary.get("average", 0) or 0)
    p25 = int(salary.get("p25", 0) or 0)
    p75 = int(salary.get("p75", 0) or 0)

    # Filter tags that have a meaningful avg_salary (>0); they all do for this dataset
    tags_with_salary = [t for t in tags if int(t.get("avg_salary", 0) or 0) > 0]

    # Top 10 by avg_salary (require minimum role count of 100 so we exclude noisy small-n tags)
    MIN_COUNT_FOR_TOP_PAY = 100
    top_pay_tags = sorted(
        [t for t in tags_with_salary if int(t.get("count", 0)) >= MIN_COUNT_FOR_TOP_PAY],
        key=lambda x: int(x.get("avg_salary", 0)),
        reverse=True,
    )[:10]

    # Top 10 by count (most in-demand)
    top_demand_tags = sorted(tags, key=lambda x: int(x.get("count", 0)), reverse=True)[:10]

    # Build a tag map for quick lookups
    tag_map = {t.get("tag"): t for t in tags}

    def t_count(name: str) -> int:
        return int(tag_map.get(name, {}).get("count", 0))

    def t_salary(name: str) -> int:
        return int(tag_map.get(name, {}).get("avg_salary", 0) or 0)

    # Sharpest stat candidates ---
    rl_count = t_count("reinforcement-learning")
    rl_salary = t_salary("reinforcement-learning")
    genai_count = t_count("generative-ai")
    genai_salary = t_salary("generative-ai")
    research_count = t_count("research")
    research_salary = t_salary("research")
    llm_count = t_count("llm")
    llm_salary = t_salary("llm")
    agents_count = t_count("agents")
    agents_salary = t_salary("agents")

    # Lead stat: research vs generative-ai (or whichever pair has biggest delta with substantial volume)
    if research_salary and genai_salary:
        premium = research_salary - genai_salary
        lead_stat_para = (
            f"Research roles pay a ${premium // 1000:,}k premium over generative-AI roles "
            f"(${research_salary:,} vs ${genai_salary:,} avg), even though generative-AI has roughly "
            f"{(genai_count / max(research_count,1)):.1f}x more openings ({fmt_thousands(genai_count)} vs "
            f"{fmt_thousands(research_count)}). Here's what the {fmt_thousands(jobs_with_salary)}-posting "
            f"compensation dataset tells us about where AI engineering compensation is actually flowing &mdash; "
            f"and where agents and LLMs sit in the middle."
        )
    elif rl_salary and genai_salary:
        premium = rl_salary - genai_salary
        lead_stat_para = (
            f"Reinforcement-learning roles pay a ${premium // 1000:,}k premium over generative-AI roles "
            f"(${rl_salary:,} vs ${genai_salary:,} avg), even though generative-AI has roughly "
            f"{(genai_count / max(rl_count,1)):.1f}x more openings ({fmt_thousands(genai_count)} vs "
            f"{fmt_thousands(rl_count)}). Here's what the {fmt_thousands(jobs_with_salary)}-posting "
            f"compensation dataset tells us about where AI engineering compensation is actually flowing."
        )
    else:
        lead_stat_para = (
            f"Across {fmt_thousands(jobs_with_salary)} salary-disclosed roles in the AI Dev Jobs index, "
            f"the highest-paying skill tags out-earn the most in-demand tags by tens of thousands of dollars per year. "
            f"Here's the full breakdown of where AI engineering compensation is actually flowing as of {today}."
        )

    # Stat cards
    # Best paying (highest avg salary among tags with >=100 roles)
    if top_pay_tags:
        best_tag = top_pay_tags[0]
        best_tag_name = str(best_tag.get("tag", "—"))
        best_tag_salary = int(best_tag.get("avg_salary", 0))
    else:
        best_tag_name = "—"
        best_tag_salary = 0

    # Most in-demand
    if top_demand_tags:
        biggest_tag = top_demand_tags[0]
        biggest_tag_name = str(biggest_tag.get("tag", "—"))
        biggest_tag_count = int(biggest_tag.get("count", 0))
    else:
        biggest_tag_name = "—"
        biggest_tag_count = 0

    stat_cards_html = f"""      <div class="stat-row">
        <div class="stat-box">
          <div class="stat-num">${best_tag_salary:,}</div>
          <div class="stat-label">avg salary for <code>{html_escape(best_tag_name)}</code> &mdash; the top-paying skill tag with 100+ roles</div>
        </div>
        <div class="stat-box">
          <div class="stat-num">{fmt_thousands(biggest_tag_count)}</div>
          <div class="stat-label">roles tagged <code>{html_escape(biggest_tag_name)}</code> &mdash; the most in-demand skill in the index</div>
        </div>
        <div class="stat-box">
          <div class="stat-num">${median:,}</div>
          <div class="stat-label">median advertised salary across {fmt_thousands(jobs_with_salary)} salary-disclosed roles</div>
        </div>
      </div>"""

    # Top-paying table
    top_pay_rows = "\n".join(
        f"          <tr><td><code>{html_escape(t.get('tag','—'))}</code></td>"
        f"<td class=\"num\">{fmt_thousands(t.get('count', 0))}</td>"
        f"<td class=\"num\">{fmt_salary(t.get('avg_salary', 0))}</td></tr>"
        for t in top_pay_tags
    ) or '          <tr><td colspan="3">No tag data available.</td></tr>'

    # Most-in-demand table
    top_demand_rows = "\n".join(
        f"          <tr><td><code>{html_escape(t.get('tag','—'))}</code></td>"
        f"<td class=\"num\">{fmt_thousands(t.get('count', 0))}</td>"
        f"<td class=\"num\">{fmt_salary(t.get('avg_salary', 0))}</td></tr>"
        for t in top_demand_tags
    ) or '          <tr><td colspan="3">No tag data available.</td></tr>'

    # Gap analysis: high demand × pay quadrants
    # Compute median salary across tags-with-salary as the threshold
    salaries_only = sorted(int(t.get("avg_salary", 0)) for t in tags_with_salary if int(t.get("avg_salary", 0)) > 0)
    counts_only = sorted(int(t.get("count", 0)) for t in tags if int(t.get("count", 0)) > 0)
    salary_threshold = salaries_only[len(salaries_only) // 2] if salaries_only else 220000
    count_threshold = counts_only[len(counts_only) // 2] if counts_only else 700

    high_demand_high_pay = [
        t for t in tags_with_salary
        if int(t.get("count", 0)) >= count_threshold and int(t.get("avg_salary", 0)) >= salary_threshold
    ]
    high_demand_low_pay = [
        t for t in tags_with_salary
        if int(t.get("count", 0)) >= count_threshold and int(t.get("avg_salary", 0)) < salary_threshold
    ]
    high_demand_high_pay.sort(key=lambda x: int(x.get("count", 0)), reverse=True)
    high_demand_low_pay.sort(key=lambda x: int(x.get("count", 0)), reverse=True)

    def fmt_tag_inline(t: dict[str, Any]) -> str:
        nm = html_escape(t.get("tag", "—"))
        cnt = int(t.get("count", 0))
        sal = int(t.get("avg_salary", 0))
        return f"<code>{nm}</code> ({fmt_thousands(cnt)} roles, ${sal:,} avg)"

    if high_demand_high_pay and high_demand_low_pay:
        sweet_spot = ", ".join(fmt_tag_inline(t) for t in high_demand_high_pay[:5])
        lower_pay = ", ".join(fmt_tag_inline(t) for t in high_demand_low_pay[:5])
        gap_para = (
            f"<strong>Sweet-spot tags &mdash; high demand <em>and</em> high pay.</strong> "
            f"{sweet_spot}. These are the skills the market is willing to pay above-median for "
            f"<em>and</em> hire above-median volumes of. If you're choosing what to learn next, "
            f"this is where leverage compounds."
        )
        gap_para_2 = (
            f"<strong>High demand, lower pay.</strong> {lower_pay}. These tags are popular in "
            f"job postings but compensation has not kept pace &mdash; usually because the labor "
            f"pool is large or the work is more easily commoditized. Volume here doesn't translate "
            f"to negotiating leverage."
        )
    else:
        gap_para = (
            f"The data shows clear concentration: a handful of tags command both high demand and "
            f"top compensation, while many high-volume tags pay closer to the index median."
        )
        gap_para_2 = (
            f"Specialized infrastructure and research-adjacent skills consistently out-pay "
            f"generic application work."
        )

    # Experience-level table — only count is in API; show counts and shares,
    # be honest about salary by level not being in the public stats endpoint.
    total_exp = sum(int(e.get("count", 0)) for e in experience_levels) or 1
    # Order: junior, mid, senior, lead, principal (canonical career ladder)
    canonical_order = ["junior", "mid", "senior", "lead", "principal"]
    exp_map = {e.get("level"): e for e in experience_levels}
    ordered_levels = [exp_map[k] for k in canonical_order if k in exp_map]
    # Add any that aren't in canonical order (defensive)
    for e in experience_levels:
        if e.get("level") not in canonical_order:
            ordered_levels.append(e)

    exp_rows = "\n".join(
        f"          <tr><td>{level_label(e.get('level',''))}</td>"
        f"<td class=\"num\">{fmt_thousands(e.get('count', 0))}</td>"
        f"<td class=\"num\">{(int(e.get('count', 0)) / total_exp * 100):.1f}%</td></tr>"
        for e in ordered_levels
    ) or '          <tr><td colspan="3">No experience-level data available.</td></tr>'

    # Senior+lead+principal share
    senior_share_ct = sum(int(exp_map.get(k, {}).get("count", 0)) for k in ("senior", "lead", "principal"))
    senior_share_pct = (senior_share_ct / total_exp * 100) if total_exp else 0
    junior_share_ct = int(exp_map.get("junior", {}).get("count", 0))
    junior_share_pct = (junior_share_ct / total_exp * 100) if total_exp else 0

    exp_para = (
        f"The ladder skews heavily senior. Senior, lead, and principal roles account for "
        f"{fmt_thousands(senior_share_ct)} of {fmt_thousands(total_exp)} classified roles &mdash; "
        f"{senior_share_pct:.1f}% of the index. Junior makes up just {fmt_thousands(junior_share_ct)} "
        f"({junior_share_pct:.1f}%). The salary endpoint reports a single weighted median of "
        f"${median:,} (p25 ${p25:,}, p75 ${p75:,}, average ${avg_overall:,}); the heavy senior weighting "
        f"is the main reason that median sits well above $200k. <em>Note: the public "
        f"<code>/api/v1/stats</code> endpoint exposes counts by level but not salary by level &mdash; "
        f"to derive average salary per band, query the <a href=\"https://aidevboard.com/api/v1/jobs\">"
        f"/api/v1/jobs</a> endpoint with <code>level=</code> filters and aggregate locally.</em>"
    )

    # Salary distribution table
    total_distribution = sum(int(d.get("count", 0)) for d in distribution) or 1
    distribution_rows = "\n".join(
        f"          <tr><td>{salary_range_label(d.get('range', ''))}</td>"
        f"<td class=\"num\">{fmt_thousands(d.get('count', 0))}</td>"
        f"<td class=\"num\">{(int(d.get('count', 0)) / total_distribution * 100):.1f}%</td></tr>"
        for d in distribution
    )

    def dist_count(key: str) -> int:
        for d in distribution:
            if d.get("range") == key:
                return int(d.get("count", 0))
        return 0

    d_200_250 = dist_count("200k_250k")
    d_150_200 = dist_count("150k_200k")
    d_250_300 = dist_count("250k_300k")
    d_300_400 = dist_count("300k_400k")
    d_400_plus = dist_count("400k_plus")
    d_below_150 = dist_count("under_100k") + dist_count("100k_150k")
    d_above_300 = d_300_400 + d_400_plus
    d_core_band = d_150_200 + d_200_250 + d_250_300
    share_core_band = (d_core_band / total_distribution * 100) if total_distribution else 0
    share_above_300 = (d_above_300 / total_distribution * 100) if total_distribution else 0
    share_below_150 = (d_below_150 / total_distribution * 100) if total_distribution else 0

    distribution_para = (
        f"Of the {fmt_thousands(jobs_with_salary)} roles publishing salary, {fmt_thousands(d_core_band)} "
        f"({share_core_band:.1f}%) fall inside the $150k-$300k core band &mdash; that's where the bulk of "
        f"AI engineering compensation lives. {fmt_thousands(d_above_300)} roles ({share_above_300:.1f}%) "
        f"clear $300k, and {fmt_thousands(d_below_150)} ({share_below_150:.1f}%) sit below $150k. The "
        f"distribution is right-skewed: a meaningful tail above $400k ({fmt_thousands(d_400_plus)} roles) "
        f"pulls the average ${avg_overall:,} above the median ${median:,}."
    )

    # Practical takeaway
    if top_pay_tags and high_demand_high_pay:
        learn_picks = [t.get("tag") for t in high_demand_high_pay[:3]]
        takeaway_para = (
            f"<strong>If you are choosing what to learn next.</strong> The pure-pay leaderboard "
            f"(<code>{html_escape(top_pay_tags[0].get('tag','—'))}</code>, "
            f"<code>{html_escape(top_pay_tags[1].get('tag','—')) if len(top_pay_tags) > 1 else ''}</code>, "
            f"<code>{html_escape(top_pay_tags[2].get('tag','—')) if len(top_pay_tags) > 2 else ''}</code>) "
            f"clusters around research and infrastructure work that takes years to develop. The "
            f"high-leverage practical picks are the sweet-spot tags &mdash; "
            f"{', '.join('<code>'+html_escape(t)+'</code>' for t in learn_picks)} &mdash; where demand "
            f"and pay both sit above the index median. Generic <code>machine-learning</code> and "
            f"<code>data-science</code> are not on that list, even though they remain common job "
            f"titles. The market is rewarding specificity."
        )
    else:
        takeaway_para = (
            f"<strong>If you are choosing what to learn next.</strong> The data favors specificity. "
            f"Specialized infrastructure work, research-adjacent skills, and agent-systems experience "
            f"all out-pay generic ML/data-science listings. Pick a sub-domain, ship something in it, "
            f"and the compensation premium follows."
        )

    # Methodology
    methodology_para = (
        f"This note is generated from the live <a href=\"https://aidevboard.com/api/v1/stats\">"
        f"aidevboard.com/api/v1/stats</a> endpoint &mdash; a public, unauthenticated JSON API. The "
        f"underlying index scrapes 560+ ATS sources (Ashby, Greenhouse, Lever, Workday, custom careers "
        f"pages) on a daily cron, deduplicates by (company, title, location), classifies each role "
        f"into a normalized skill-tag set with a rules-based parser, and stores employer-advertised "
        f"salary ranges where present. Of {fmt_thousands(total_jobs)} roles in the index, "
        f"{fmt_thousands(jobs_with_salary)} disclose a salary range &mdash; the rest are silently "
        f"excluded from the salary tables. <strong>Caveats</strong>: (1) salaries are advertised "
        f"midpoints, not actual offers; (2) US-disclosure laws drive the highest disclosure rates so "
        f"the dataset over-represents California, New York, Washington, and Colorado; (3) tag "
        f"averages assume a role with multiple tags contributes its full salary to each tag's average; "
        f"(4) the {MIN_COUNT_FOR_TOP_PAY}-role minimum on the top-paying table filters out small-n "
        f"noise. This page auto-regenerates weekly."
    )

    # Download data callout
    download_para = (
        f'<strong>Download raw data:</strong> The compensation-by-skill dataset is mirrored as a '
        f'public gist &mdash; <a href="{GIST_CSV_RAW_URL}">CSV</a> &middot; '
        f'<a href="{GIST_MD_RAW_URL}">Markdown</a> &middot; '
        f'<a href="{GIST_URL}">view on GitHub</a>. '
        f"Auto-updated every weekly regeneration; canonical raw URLs are stable across revisions."
    )

    # Meta strings
    subtitle_text = (
        f"Live compensation data from {fmt_thousands(jobs_with_salary)} salary-disclosed AI/ML "
        f"engineering roles across {fmt_thousands(total_companies)} companies, as of {today}. "
        f"The top-paying skill tags out-earn the most in-demand tags by tens of thousands per year. "
        f"Live data pulled from <a href=\"https://aidevboard.com/api/v1/stats\">aidevboard.com/api/v1/stats</a>."
    )

    meta_description = (
        f"Live AI engineering compensation by skill: top-paying tags, most in-demand tags, "
        f"sweet-spot skills, salary by experience level, distribution across {fmt_thousands(jobs_with_salary)} "
        f"salary-disclosed roles. Median ${median:,}. Auto-regenerated weekly from aidevboard.com API."
    )
    og_description = (
        f"Top-paying AI skill: {html_escape(best_tag_name)} at ${best_tag_salary:,}. Most in-demand: "
        f"{html_escape(biggest_tag_name)} ({fmt_thousands(biggest_tag_count)} roles). Median ${median:,}. "
        f"Sweet-spot tags where high demand meets high pay. Live data, {today}."
    )
    twitter_description = (
        f"AI engineering compensation by skill: top-paying = ${best_tag_salary:,} "
        f"({html_escape(best_tag_name)}). Median ${median:,} across "
        f"{fmt_thousands(jobs_with_salary)} salary-disclosed roles. {today}."
    )
    article_description = (
        f"Live AI engineering compensation analysis from aidevboard.com: top-paying skill tags, "
        f"most in-demand tags, sweet-spot skills (high demand + high pay), salary distribution, and "
        f"experience-level breakdown across {fmt_thousands(jobs_with_salary)} salary-disclosed roles."
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="referrer" content="strict-origin-when-cross-origin" />
  <meta name="color-scheme" content="dark light" />
  <meta name="last-updated" content="{today}" />
  <title>Q2 2026 AI Engineering Compensation by Skill -- 8bitconcepts</title>
  <meta name="description" content="{attr_escape(meta_description)}" />
  <meta property="og:title" content="Q2 2026 AI Engineering Compensation by Skill -- 8bitconcepts" />
  <meta property="og:description" content="{attr_escape(og_description)}" />
  <meta property="og:type" content="article" />
  <meta property="og:url" content="https://8bitconcepts.com/research/q2-2026-ai-compensation-by-skill.html" />
  <meta property="og:image" content="{OG_IMAGE_URL}" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="Q2 2026 AI Engineering Compensation by Skill" />
  <meta name="twitter:description" content="{attr_escape(twitter_description)}" />
  <meta name="twitter:image" content="{OG_IMAGE_URL}" />
  <link rel="canonical" href="https://8bitconcepts.com/research/q2-2026-ai-compensation-by-skill.html" />
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
    "headline": "Q2 2026 AI Engineering Compensation by Skill",
    "description": "{attr_escape(article_description)}",
    "url": "https://8bitconcepts.com/research/q2-2026-ai-compensation-by-skill.html",
    "datePublished": "2026-04-17",
    "dateModified": "{today}",
    "author": {{"@type": "Organization", "name": "8bitconcepts", "url": "https://8bitconcepts.com"}},
    "publisher": {{"@type": "Organization", "name": "8bitconcepts", "url": "https://8bitconcepts.com"}},
    "image": "{OG_IMAGE_URL}",
    "inLanguage": "en",
    "isAccessibleForFree": true,
    "about": "AI engineering compensation, salary by skill tag, top-paying AI skills, in-demand AI skills, experience-level distribution",
    "keywords": "AI salary, AI engineering pay, ML salary, LLM compensation, agents salary, AI skill premium, 2026 hiring data"
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
    {{"@type": "ListItem", "position": 3, "name": "Q2 2026 AI Engineering Compensation by Skill"}}
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

    <div class="eyebrow">Research &mdash; Compensation</div>

    <h1>Q2 2026 AI Engineering Compensation by Skill</h1>

    <p class="subtitle">{subtitle_text}</p>

    <div class="meta">
      <span class="meta-date">{today}</span>
      <span class="meta-tag">Live Data</span>
      <span class="meta-read">~800 words</span>
    </div>

    <div class="article-body">

      <h2>Executive summary</h2>

      <p>{lead_stat_para}</p>

{stat_cards_html}

      <h2>Top-paying skill tags</h2>

      <p>The top of the salary table is dominated by tags that take years to develop and don't show up in junior resumes. The {MIN_COUNT_FOR_TOP_PAY}-role minimum filters out small-sample noise so what's left is real, repeatable compensation signal.</p>

      <table class="data-table">
        <thead>
          <tr>
            <th>Tag</th>
            <th class="num" style="text-align:right;">Role count</th>
            <th class="num" style="text-align:right;">Avg salary</th>
          </tr>
        </thead>
        <tbody>
{top_pay_rows}
        </tbody>
      </table>

      <h2>Most in-demand skill tags</h2>

      <p>Volume tells a different story than pay. The biggest tags are the ones every AI/ML team needs at least one of, not the ones the market pays the most for.</p>

      <table class="data-table">
        <thead>
          <tr>
            <th>Tag</th>
            <th class="num" style="text-align:right;">Role count</th>
            <th class="num" style="text-align:right;">Avg salary</th>
          </tr>
        </thead>
        <tbody>
{top_demand_rows}
        </tbody>
      </table>

      <h2>The gap: where demand meets pay</h2>

      <p>{gap_para}</p>

      <p>{gap_para_2}</p>

      <div class="callout">
        <p>The most useful frame for a job seeker isn't "highest paying" or "most posted." It's the intersection &mdash; tags where both axes are above the median. That's where you have negotiating leverage <em>and</em> a healthy supply of openings to negotiate against.</p>
      </div>

      <h2>By experience level</h2>

      <p>{exp_para}</p>

      <table class="data-table">
        <thead>
          <tr>
            <th>Level</th>
            <th class="num" style="text-align:right;">Roles</th>
            <th class="num" style="text-align:right;">Share</th>
          </tr>
        </thead>
        <tbody>
{exp_rows}
        </tbody>
      </table>

      <h2>Salary distribution</h2>

      <p>{distribution_para}</p>

      <table class="data-table">
        <thead>
          <tr>
            <th>Range</th>
            <th class="num" style="text-align:right;">Roles</th>
            <th class="num" style="text-align:right;">Share</th>
          </tr>
        </thead>
        <tbody>
{distribution_rows}
        </tbody>
      </table>

      <h2>Practical takeaway</h2>

      <p>{takeaway_para}</p>

      <h2>Methodology</h2>

      <p>{methodology_para}</p>

      <p>{download_para}</p>

      <h2>What's next</h2>

      <p>For the company-side view of this same dataset &mdash; who is doing the hiring, where the roles are concentrated, and how the workplace mix shakes out &mdash; see <a href="/research/q2-2026-ai-hiring-snapshot.html">Q2 2026 AI Engineering Hiring Snapshot</a>. For the infrastructure side &mdash; how many of the agents these engineers are building actually have a working MCP endpoint to talk to &mdash; see <a href="/research/q2-2026-mcp-ecosystem-health.html">Q2 2026 MCP Ecosystem Health</a>. For the engineering maturity ladder that separates the teams paying these premiums from the teams stuck in pilot, see <a href="/research/beyond-the-prompt.html">Beyond the Prompt</a>. Full reading paths at the <a href="/research/overview.html">Research Atlas</a>.</p>

    </div>

    <div class="related">
      <div class="related-label">Related Research</div>
      <div class="related-grid">
        <a class="related-card" href="/research/q2-2026-ai-hiring-snapshot.html">
          <div class="related-card-title">Q2 2026 AI Hiring Snapshot</div>
          <div class="related-card-sub">Live market data: roles, top companies, workplace mix.</div>
        </a>
        <a class="related-card" href="/research/q2-2026-mcp-ecosystem-health.html">
          <div class="related-card-title">Q2 2026 MCP Ecosystem Health</div>
          <div class="related-card-sub">Live JSON-RPC handshake audit of MCP servers.</div>
        </a>
        <a class="related-card" href="/research/beyond-the-prompt.html">
          <div class="related-card-title">Beyond the Prompt</div>
          <div class="related-card-sub">The engineering maturity ladder for production agents.</div>
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
        <li>AI Dev Jobs &mdash; <a href="https://aidevboard.com/api/v1/stats">/api/v1/stats</a>, pulled {generated_iso}. Public unauthenticated endpoint. Backing index: {fmt_thousands(total_jobs)} roles / {fmt_thousands(total_companies)} companies / {fmt_thousands(jobs_with_salary)} salary-disclosed.</li>
        <li>AI Dev Jobs &mdash; <a href="https://aidevboard.com/api/v1/jobs">/api/v1/jobs</a>, paginated job-level endpoint with <code>level=</code> and <code>tag=</code> filters for deeper aggregation.</li>
        <li>Salary figures are employer-advertised midpoints from public ATS feeds. Of {fmt_thousands(total_jobs)} indexed roles, {fmt_thousands(jobs_with_salary)} disclose a salary range (driven heavily by US pay-transparency laws).</li>
        <li>Tag averages: a role with multiple tags contributes its full salary to each tag's average (no fractional weighting). The {MIN_COUNT_FOR_TOP_PAY}-role minimum on the top-paying table filters out small-sample noise; the most-in-demand table has no minimum.</li>
      </ol>
    </div>

  </div>

  <div style="max-width:640px;margin:40px auto;padding:24px;background:#fafaf8;border:1px solid #e5e5e5;border-radius:8px;">
    <p style="font-size:13px;color:#666;margin:0 0 12px;text-transform:uppercase;letter-spacing:1px;">Hiring for top-paying AI skills?</p>
    <div data-aidev-jobs data-tag="research" data-limit="3" data-theme="light"></div>
    <script src="https://aidevboard.com/static/widget.js" async></script>
  </div>

  <footer>
    <p>&copy; 2026 8bitconcepts &mdash; AI Enablement &amp; Integration Consulting &mdash; <a href="mailto:hello@8bitconcepts.com">hello@8bitconcepts.com</a></p>
    <p style="margin-top:6px;font-size:12px;"><a href="/research/overview.html" style="color:#d97757;">Research Atlas &rarr; all papers + reading paths</a></p>
  </footer>

</body>
</html>
"""


def build_gist_content(stats: dict[str, Any], today: str) -> tuple[str, str]:
    """Build CSV + Markdown for the gist. Top 20 tags by avg_salary, columns: rank, tag, count, avg_salary."""
    ov = stats.get("overview", {}) or {}
    salary = stats.get("salary", {}) or {}
    tags = stats.get("tags", []) or []
    total_jobs = int(ov.get("total_jobs", 0))
    total_companies = int(ov.get("total_companies", 0))
    jobs_with_salary = int(ov.get("jobs_with_salary", 0))
    median = int(salary.get("median", 0) or 0)

    # Top 20 by avg_salary (no minimum count for the gist — let consumers filter)
    sorted_tags = sorted(
        [t for t in tags if int(t.get("avg_salary", 0) or 0) > 0],
        key=lambda x: int(x.get("avg_salary", 0)),
        reverse=True,
    )
    top = sorted_tags[:20]

    csv_lines = ["rank,tag,count,avg_salary"]
    for i, t in enumerate(top, start=1):
        tag = str(t.get("tag", "")).replace(",", "")
        count = int(t.get("count", 0))
        avg_salary = int(t.get("avg_salary", 0))
        csv_lines.append(f"{i},{tag},{count},{avg_salary}")
    csv_text = "\n".join(csv_lines) + "\n"

    md_lines = [
        "# AI Engineering Compensation by Skill",
        "",
        f"**Last updated**: {today}",
        "",
        f"**Snapshot**: {today} \u00b7 **Total jobs**: {total_jobs:,} \u00b7 "
        f"**Companies indexed**: {total_companies:,} \u00b7 "
        f"**Salary-disclosed roles**: {jobs_with_salary:,} \u00b7 "
        f"**Median**: ${median:,}",
        "",
        "Live data from [aidevboard.com/api/v1/stats](https://aidevboard.com/api/v1/stats) \u2014 free public API, no auth, refreshed daily across 560+ ATS sources.",
        "",
        "## Top 20 skill tags by average advertised salary",
        "",
        "| Rank | Tag | Open Roles | Avg Salary |",
        "|---:|---|---:|---:|",
    ]
    for i, t in enumerate(top, start=1):
        tag = str(t.get("tag", "\u2014"))
        count = int(t.get("count", 0))
        avg_salary = int(t.get("avg_salary", 0))
        salary_cell = f"${avg_salary:,}" if avg_salary > 0 else "\u2014"
        md_lines.append(f"| {i} | `{tag}` | {count:,} | {salary_cell} |")

    md_lines += [
        "",
        "## Methodology",
        "",
        "Tags are extracted from job titles + descriptions by a rules-based parser. A role with multiple tags "
        "contributes its full advertised salary to each tag's average (no fractional weighting). Salaries are "
        "employer-advertised midpoints from public ATS feeds; US pay-transparency laws drive the disclosure rates "
        "so the dataset over-represents California, New York, Washington, and Colorado.",
        "",
        "Of the full index, only the salary-disclosed subset contributes to averages. Re-aggregate from the "
        "paginated [/api/v1/jobs](https://aidevboard.com/api/v1/jobs) endpoint if you need filters by location, "
        "experience level, or workplace.",
        "",
        "## Source & License",
        "",
        f"- **Live API**: https://aidevboard.com/api/v1/stats (JSON, public)",
        f"- **Research note**: https://8bitconcepts.com/research/q2-2026-ai-compensation-by-skill.html",
        f"- **Sibling dataset**: [Top AI Companies Hiring](https://gist.github.com/unitedideas/9c59d50a824a075410bd658c96e1f5de)",
        f"- **Sibling dataset**: [MCP Ecosystem Health](https://gist.github.com/unitedideas/c93bd6d9984729070c59b2ea6c6b301b)",
        f"- **Auto-regenerated**: weekly via `tools/regenerate-compensation-by-skill.py`",
        f"- **License**: CC BY 4.0 \u2014 attribution to 8bitconcepts + aidevboard.com",
        "",
    ]
    md_text = "\n".join(md_lines)

    return csv_text, md_text


def update_gist(stats: dict[str, Any], today: str) -> bool:
    """Write CSV + MD to /tmp/compensation-gist/ and push via `gh gist edit`. Non-fatal on failure."""
    try:
        csv_text, md_text = build_gist_content(stats, today)
    except Exception as e:
        print(f"   Gist content build failed (non-fatal): {e}", file=sys.stderr)
        return False

    tmpdir = Path(tempfile.gettempdir()) / "compensation-gist"
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


def run_git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate the Q2 2026 AI compensation-by-skill note from live data.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch + render, don't write anything")
    parser.add_argument("--once", action="store_true", help="Write file + refresh atlas, skip commit/push/pings")
    parser.add_argument("--no-push", action="store_true", help="Skip git push and IndexNow/WebSub pings")
    args = parser.parse_args()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    generated_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"=== Regenerate AI compensation-by-skill ({today}) ===")
    print("1. Fetching live ADB stats...")
    try:
        stats = http_get_json(ADB_STATS_URL)
    except Exception as e:
        print(f"  ADB stats fetch failed: {e}", file=sys.stderr)
        return 2
    ov = stats.get("overview", {}) or {}
    print(f"   ADB: {ov.get('total_jobs')} jobs / {ov.get('total_companies')} cos / {ov.get('jobs_with_salary')} salary-disclosed")
    print(f"   Tags: {len(stats.get('tags', []))} | Levels: {len(stats.get('experience_levels', []))}")

    print("2. Rendering HTML...")
    html = build_html(stats, today, generated_iso)

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
        s = _re.sub(r'\(ADB, \d{4}-\d{2}-\d{2}\)', "(ADB, X)", s)
        s = _re.sub(r'\(\d{4}-\d{2}-\d{2}\)', "(X)", s)
        return s

    new_normalized = normalize_for_diff(html)
    old_normalized = normalize_for_diff(prior)
    data_changed = new_normalized != old_normalized

    print("3. Writing paper...")
    PAPER_PATH.write_text(html, encoding="utf-8")
    print(f"   Wrote {len(html)} chars to {PAPER_PATH}")

    print("3b. Regenerating OG image (paper-specific)...")
    try:
        tags_list = stats.get("tags", []) or []
        tag_map_og = {t.get("tag"): t for t in tags_list}
        research_sal = int((tag_map_og.get("research") or {}).get("avg_salary", 0) or 0)
        genai_sal = int((tag_map_og.get("generative-ai") or {}).get("avg_salary", 0) or 0)
        rl_sal = int((tag_map_og.get("reinforcement-learning") or {}).get("avg_salary", 0) or 0)
        jobs_with_salary_v = int((stats.get("overview") or {}).get("jobs_with_salary", 0))
        median_v = int((stats.get("salary") or {}).get("median", 0) or 0)

        if research_sal and genai_sal:
            premium_k = (research_sal - genai_sal) // 1000
            headline = f"Research pays ${premium_k}k more than genAI"
            subtext = (
                f"Q2 2026 \u2022 research ${research_sal:,} vs gen-AI ${genai_sal:,} avg \u2022 "
                f"{jobs_with_salary_v:,} salary-disclosed roles"
            )
        elif rl_sal and genai_sal:
            premium_k = (rl_sal - genai_sal) // 1000
            headline = f"Reinforcement learning pays ${premium_k}k more than genAI"
            subtext = (
                f"Q2 2026 \u2022 RL ${rl_sal:,} vs gen-AI ${genai_sal:,} avg \u2022 "
                f"{jobs_with_salary_v:,} salary-disclosed roles"
            )
        else:
            headline = f"${median_v:,} median AI engineer salary"
            subtext = (
                f"Q2 2026 \u2022 {jobs_with_salary_v:,} salary-disclosed AI/ML roles"
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

    print("\n4b. Updating public gist (compensation-by-skill CSV + MD)...")
    try:
        update_gist(stats, today)
    except Exception as e:
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
                   "research/q2-2026-ai-compensation-by-skill.html",
                   "research/overview.html",
                   f"research/og/{OG_SLUG}.png"])
    if add.returncode != 0:
        print(f"   git add failed: {add.stderr[:300]}", file=sys.stderr)
        return 3
    msg = f"compensation-by-skill: auto-regenerate {today}"
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

    print("\n=== Done. ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
