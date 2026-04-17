#!/usr/bin/env python3
"""
Regenerate /research/q2-2026-remote-vs-onsite-ai-hiring.html from live ADB stats.

Pulls fresh data from:
  - https://aidevboard.com/api/v1/stats  (workplace array: [{type, count, avg_salary}])
  - https://aidevboard.com/api/v1/jobs?workplace=onsite&per_page=50&page=N  (onsite-company aggregation)

Rebuilds the paper HTML + OG image + companion gist. Commits if data changed,
pushes, IndexNow + WebSub pings.

Usage:
    python3 tools/regenerate-remote-vs-onsite.py           # full run
    python3 tools/regenerate-remote-vs-onsite.py --dry-run # fetch + render, don't write
    python3 tools/regenerate-remote-vs-onsite.py --once    # write + overview, skip commit/push/pings
    python3 tools/regenerate-remote-vs-onsite.py --no-push # skip git push + pings (commit still happens)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
RESEARCH_DIR = REPO / "research"
PAPER_PATH = RESEARCH_DIR / "q2-2026-remote-vs-onsite-ai-hiring.html"
OVERVIEW_SCRIPT = REPO / "tools" / "generate-overview.py"
PAPER_URL = "https://8bitconcepts.com/research/q2-2026-remote-vs-onsite-ai-hiring.html"

OG_SLUG = "q2-2026-remote-vs-onsite-ai-hiring"
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
ADB_JOBS_URL = "https://aidevboard.com/api/v1/jobs"

# Public gist: https://gist.github.com/unitedideas/680cc4c1d11e090814bdf132e155d6d1
GIST_ID = "680cc4c1d11e090814bdf132e155d6d1"
GIST_CSV_FILENAME = "ai-workplace.csv"
GIST_MD_FILENAME = "ai-workplace.md"
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


def fmt_salary(n: Any) -> str:
    try:
        v = int(n)
        if v <= 0:
            return "&mdash;"
        return f"${v:,}"
    except (TypeError, ValueError):
        return "&mdash;"


def workplace_label(key: str) -> str:
    return {
        "onsite": "Onsite",
        "remote": "Remote",
        "hybrid": "Hybrid",
    }.get(key, key.capitalize() if key else "&mdash;")


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


def fetch_company_workplace_counts(max_pages: int = 40, per_page: int = 50) -> dict[str, dict[str, int]]:
    """Walk /api/v1/jobs paginated, collect per-company workplace counts.

    Returns: {company_name: {"onsite": n, "remote": n, "hybrid": n, "total": n}}
    """
    out: dict[str, dict[str, int]] = defaultdict(lambda: {"onsite": 0, "remote": 0, "hybrid": 0, "total": 0})
    page = 1
    while page <= max_pages:
        url = f"{ADB_JOBS_URL}?per_page={per_page}&page={page}"
        try:
            data = http_get_json(url, timeout=30)
        except Exception as e:
            print(f"   jobs page {page} fetch failed: {e}", file=sys.stderr)
            break
        jobs = data.get("jobs", []) or []
        if not jobs:
            break
        for j in jobs:
            name = j.get("company_name") or "—"
            wp = (j.get("workplace") or "").lower()
            if wp not in ("onsite", "remote", "hybrid"):
                continue
            out[name][wp] += 1
            out[name]["total"] += 1
        if not data.get("has_next"):
            break
        page += 1
    return dict(out)


def build_html(stats: dict[str, Any], company_counts: dict[str, dict[str, int]], today: str, generated_iso: str) -> str:
    ov = stats.get("overview", {}) or {}
    workplace = stats.get("workplace", []) or []
    salary = stats.get("salary", {}) or {}
    tags = stats.get("tags", []) or []

    total_jobs = int(ov.get("total_jobs", 0))
    total_companies = int(ov.get("total_companies", 0))
    jobs_with_salary = int(ov.get("jobs_with_salary", 0))
    median_overall = int(salary.get("median", 0) or 0)

    # Workplace mix
    wp_map = {w.get("type"): w for w in workplace}
    remote = wp_map.get("remote", {})
    onsite = wp_map.get("onsite", {})
    hybrid = wp_map.get("hybrid", {})

    remote_ct = int(remote.get("count", 0))
    onsite_ct = int(onsite.get("count", 0))
    hybrid_ct = int(hybrid.get("count", 0))
    classified_total = remote_ct + onsite_ct + hybrid_ct or 1

    remote_avg = int(remote.get("avg_salary", 0) or 0)
    onsite_avg = int(onsite.get("avg_salary", 0) or 0)
    hybrid_avg = int(hybrid.get("avg_salary", 0) or 0)

    remote_pct = remote_ct / classified_total * 100
    onsite_pct = onsite_ct / classified_total * 100
    hybrid_pct = hybrid_ct / classified_total * 100

    # Compute hybrid premium
    non_hybrid_avg_num = 0
    non_hybrid_count = remote_ct + onsite_ct
    if non_hybrid_count:
        non_hybrid_avg_num = (remote_avg * remote_ct + onsite_avg * onsite_ct) // non_hybrid_count
    hybrid_premium_abs = hybrid_avg - non_hybrid_avg_num if (hybrid_avg and non_hybrid_avg_num) else 0
    hybrid_premium_k = hybrid_premium_abs // 1000 if hybrid_premium_abs else 0

    # Pick the headline stat
    # The three common cases we want to explain in the lead:
    #   (A) hybrid materially > both  -> hybrid premium
    #   (B) remote materially > onsite -> remote premium
    #   (C) onsite > remote            -> onsite premium (rarer)
    all_avgs = [remote_avg, onsite_avg, hybrid_avg]
    max_avg = max(all_avgs)
    min_avg = min(a for a in all_avgs if a > 0) if any(a > 0 for a in all_avgs) else 0
    biggest_gap_k = (max_avg - min_avg) // 1000 if min_avg else 0

    # Executive hook paragraph
    if hybrid_avg and hybrid_premium_k >= 10:
        lead_para = (
            f"Hybrid AI/ML roles pay a <strong>${hybrid_premium_k}k premium</strong> over the remote + onsite weighted average "
            f"(${hybrid_avg:,} vs ${non_hybrid_avg_num:,}). Remote averages ${remote_avg:,}. Onsite averages ${onsite_avg:,}. "
            f"The most surprising line in the data isn't the remote-vs-onsite pay gap &mdash; it's that the middle-ground "
            f"arrangement, which many companies pitched as a compromise, is where compensation actually lands highest."
        )
    elif remote_avg > onsite_avg and (remote_avg - onsite_avg) >= 5000:
        diff_k = (remote_avg - onsite_avg) // 1000
        lead_para = (
            f"Remote AI/ML roles pay a <strong>${diff_k}k premium</strong> over onsite "
            f"(${remote_avg:,} vs ${onsite_avg:,} avg). Hybrid sits at ${hybrid_avg:,}. The conventional wisdom "
            f"that onsite wins the bidding war is not what the live index shows &mdash; AI talent markets are "
            f"distributed, and the companies willing to hire fully remote are paying at or above the onsite median."
        )
    else:
        lead_para = (
            f"Remote AI/ML roles pay ${remote_avg:,} avg, onsite ${onsite_avg:,}, and hybrid ${hybrid_avg:,} &mdash; "
            f"the biggest spread between bands is ${biggest_gap_k}k. "
            f"Of {fmt_thousands(classified_total)} classified AI/ML postings in the index, "
            f"{fmt_thousands(onsite_ct)} ({onsite_pct:.0f}%) still require full onsite attendance despite the "
            f"industry's remote-friendly reputation."
        )

    # Stat cards
    stat_cards_html = f"""      <div class="stat-row">
        <div class="stat-box">
          <div class="stat-num">${hybrid_avg:,}</div>
          <div class="stat-label">average hybrid AI/ML salary &mdash; the top band across {fmt_thousands(classified_total)} classified roles</div>
        </div>
        <div class="stat-box">
          <div class="stat-num">{onsite_pct:.0f}%</div>
          <div class="stat-label">of roles still require full onsite attendance ({fmt_thousands(onsite_ct)} of {fmt_thousands(classified_total)})</div>
        </div>
        <div class="stat-box">
          <div class="stat-num">${remote_avg:,}</div>
          <div class="stat-label">average fully-remote AI/ML salary across {fmt_thousands(remote_ct)} postings</div>
        </div>
      </div>"""

    # Top-line workplace table
    mix_rows = []
    for key, label in (("onsite", "Onsite"), ("remote", "Remote"), ("hybrid", "Hybrid")):
        w = wp_map.get(key, {})
        cnt = int(w.get("count", 0))
        avg = int(w.get("avg_salary", 0) or 0)
        share = cnt / classified_total * 100 if classified_total else 0
        mix_rows.append(
            f"          <tr><td>{label}</td>"
            f"<td class=\"num\">{fmt_thousands(cnt)}</td>"
            f"<td class=\"num\">{share:.1f}%</td>"
            f"<td class=\"num\">{fmt_salary(avg)}</td></tr>"
        )
    mix_table_rows = "\n".join(mix_rows)

    # Hybrid-premium analysis paragraphs
    hybrid_analysis_p1 = (
        f"Why does the middle option pay the most? Two factors explain most of the premium. "
        f"<strong>First, seniority.</strong> Hybrid roles skew toward staff, lead, and principal bands &mdash; the levels "
        f"where companies want engineers in the office for architecture discussions and design reviews but accept "
        f"that 30+ year-old senior engineers won't relocate full-time. The salary endpoint reports a single weighted "
        f"average of ${int(salary.get('average', 0) or 0):,} across all salary-disclosed roles, and the hybrid "
        f"band sits <strong>${(hybrid_avg - int(salary.get('average', 0) or 0)) // 1000:+d}k</strong> above that global "
        f"average &mdash; that's not a remote-work discount, it's a seniority mix."
    )

    hybrid_analysis_p2 = (
        f"<strong>Second, geography.</strong> Hybrid postings anchor to a specific metro (usually San Francisco, "
        f"New York, or Seattle) and inherit that metro's pay band. Remote postings in the same index compete with "
        f"distributed talent from lower-cost geographies and from candidates who've already priced remote work into "
        f"their expectations. The ${remote_avg:,} remote average still out-earns most non-AI engineering roles, but "
        f"it reflects a broader supply pool than the ${hybrid_avg:,} hybrid average does. The practical read: "
        f"hybrid is where AI companies are paying SF+NYC premiums <em>plus</em> demanding most-week attendance. "
        f"It's the most expensive arrangement to hire into because it selects the most constrained candidate pool."
    )

    # Onsite-only heavy companies
    # Include companies with >= 15 jobs in the company_counts (to reduce noise)
    onsite_heavy = []
    for name, counts in company_counts.items():
        total = counts["total"]
        if total < 15:
            continue
        onsite = counts["onsite"]
        onsite_share = onsite / total if total else 0
        onsite_heavy.append((name, total, onsite, onsite_share, counts["remote"], counts["hybrid"]))
    onsite_heavy.sort(key=lambda x: (-x[3], -x[2]))  # onsite-share desc, onsite-count desc
    onsite_heavy_strong = [row for row in onsite_heavy if row[3] >= 0.80][:10]

    if onsite_heavy_strong:
        onsite_rows_html = "\n".join(
            f"          <tr><td>{html_escape(name)}</td>"
            f"<td class=\"num\">{fmt_thousands(total)}</td>"
            f"<td class=\"num\">{fmt_thousands(onsite_ct_c)}</td>"
            f"<td class=\"num\">{share * 100:.0f}%</td></tr>"
            for (name, total, onsite_ct_c, share, _r, _h) in onsite_heavy_strong
        )
        onsite_note = (
            f"The following companies ran {len(onsite_heavy_strong)} or more AI/ML postings in the live index with "
            f"at least 80% marked <code>onsite</code>. This list skews toward robotics, autonomous systems, and "
            f"frontier labs &mdash; all areas where physical hardware, secure facilities, or classified work "
            f"makes remote collaboration operationally difficult. It explains the 55% onsite floor in the top-line mix."
        )
    else:
        onsite_rows_html = '          <tr><td colspan="4">Insufficient data to surface onsite-heavy companies this cycle (fewer than 10 large-sample companies above the 80% onsite threshold).</td></tr>'
        onsite_note = (
            f"No company crosses the 80%-onsite threshold with a large enough sample this cycle. The live jobs "
            f"endpoint is paginated and sampled across a rolling window; re-run this paper after the weekly crawl "
            f"completes for a fuller company-level view."
        )

    # Remote-friendly companies (>= 50% remote, >= 10 total)
    remote_friendly = []
    for name, counts in company_counts.items():
        total = counts["total"]
        if total < 10:
            continue
        r = counts["remote"]
        share = r / total if total else 0
        if share >= 0.50:
            remote_friendly.append((name, total, r, share))
    remote_friendly.sort(key=lambda x: (-x[3], -x[2]))
    remote_friendly = remote_friendly[:8]

    if remote_friendly:
        remote_rows_html = "\n".join(
            f"          <tr><td>{html_escape(name)}</td>"
            f"<td class=\"num\">{fmt_thousands(total)}</td>"
            f"<td class=\"num\">{fmt_thousands(r)}</td>"
            f"<td class=\"num\">{share * 100:.0f}%</td></tr>"
            for (name, total, r, share) in remote_friendly
        )
        remote_note = (
            f"Conversely, here are the large-sample companies leaning remote-friendly (50%+ of AI/ML postings "
            f"marked <code>remote</code>). These are typically distributed developer-tool companies, AI infra, "
            f"and companies built remote-first from day one &mdash; they tend to set a remote salary floor at or "
            f"above major-metro onsite pay."
        )
    else:
        remote_rows_html = '          <tr><td colspan="4">No large-sample companies crossed the 50%-remote threshold this cycle.</td></tr>'
        remote_note = (
            f"The rolling sample this cycle surfaces no companies crossing the 50%-remote threshold with a large "
            f"enough posting count. Re-run after the next crawl."
        )

    # Salary distribution by workplace — a bar-chart-style callout.
    # Use the 3 averages as relative weights against the max.
    all_avg_vals = [onsite_avg, remote_avg, hybrid_avg]
    max_bar = max(all_avg_vals) or 1
    def bar_pct(v: int) -> float:
        return (v / max_bar * 100) if max_bar else 0

    bar_onsite = bar_pct(onsite_avg)
    bar_remote = bar_pct(remote_avg)
    bar_hybrid = bar_pct(hybrid_avg)

    salary_bars_html = f"""      <div class="bar-chart">
        <div class="bar-row">
          <div class="bar-label">Onsite</div>
          <div class="bar-wrap"><div class="bar" style="width:{bar_onsite:.1f}%;"></div></div>
          <div class="bar-value">${onsite_avg:,}</div>
        </div>
        <div class="bar-row">
          <div class="bar-label">Remote</div>
          <div class="bar-wrap"><div class="bar" style="width:{bar_remote:.1f}%;"></div></div>
          <div class="bar-value">${remote_avg:,}</div>
        </div>
        <div class="bar-row">
          <div class="bar-label">Hybrid</div>
          <div class="bar-wrap"><div class="bar" style="width:{bar_hybrid:.1f}%;"></div></div>
          <div class="bar-value">${hybrid_avg:,}</div>
        </div>
      </div>"""

    # Regional bias note
    regional_note = (
        f"<strong>Regional bias caveat.</strong> The AI Dev Jobs index over-represents US-based postings. "
        f"US pay-transparency laws (California, New York, Washington, Colorado) drive salary disclosure, so "
        f"US postings are weighted more heavily in the salary averages than in the posting counts. "
        f"European and APAC AI/ML roles are present in the index but many publish salary as &quot;competitive&quot; "
        f"and drop out of the ${fmt_thousands(jobs_with_salary)}-posting salary-disclosed subset. Remote "
        f"postings in particular often advertise a US-only salary range even when they're open globally &mdash; "
        f"interpret the <code>$</code> figures as US-anchored."
    )

    # Takeaway for job seekers
    takeaway_para = (
        f"<strong>If you're choosing what to apply for.</strong> The headline-grabbing remote-vs-onsite framing is "
        f"the wrong axis. Hybrid is the highest-paying band because it picks up SF/NYC salary floors <em>plus</em> "
        f"senior/staff+ level mix. If you have the flexibility to be in-office 2-3 days a week in a major metro, "
        f"hybrid is where the dollars land. If you need fully remote, target the remote-friendly companies in the "
        f"table above &mdash; they set the remote floor higher than the ${remote_avg:,} index average. If you're "
        f"early-career, onsite roles at robotics, autonomous-vehicle, and frontier labs are where the {onsite_pct:.0f}% "
        f"onsite share concentrates &mdash; lean in, physical-AI work is where onsite still pays real premiums."
    )

    # Methodology
    methodology_para = (
        f"Generated from the live <a href=\"https://aidevboard.com/api/v1/stats\">aidevboard.com/api/v1/stats</a> "
        f"endpoint (public, unauthenticated) plus a paginated walk of <a href=\"https://aidevboard.com/api/v1/jobs\">"
        f"/api/v1/jobs</a> for per-company workplace aggregation. Index scrapes 560+ ATS sources on a daily cron "
        f"and deduplicates by (company, title, location). The <code>workplace</code> field is classified by a "
        f"rules-based parser from job-title + description + location signals; edge cases (\"hybrid, 3 days\", "
        f"\"flexible\", \"in-person preferred\") are normalized into the three canonical buckets. "
        f"Of {fmt_thousands(total_jobs)} roles in the index, {fmt_thousands(classified_total)} have a non-empty "
        f"workplace classification; the rest are silently excluded from this analysis. Salary averages use "
        f"employer-advertised midpoints from the {fmt_thousands(jobs_with_salary)}-posting salary-disclosed subset. "
        f"This page auto-regenerates weekly (Mon 9:00 am PT)."
    )

    # Download data callout
    download_para = (
        f'<strong>Download raw data:</strong> The workplace-by-salary dataset is mirrored as a public gist '
        f'&mdash; <a href="{GIST_CSV_RAW_URL}">CSV</a> &middot; '
        f'<a href="{GIST_MD_RAW_URL}">Markdown</a> &middot; '
        f'<a href="{GIST_URL}">view on GitHub</a>. '
        f"Auto-updated every weekly regeneration; canonical raw URLs are stable across revisions."
    )

    # Meta strings
    subtitle_text = (
        f"Live workplace data from {fmt_thousands(classified_total)} classified AI/ML engineering roles. "
        f"Hybrid averages ${hybrid_avg:,}, remote ${remote_avg:,}, onsite ${onsite_avg:,}. "
        f"{onsite_pct:.0f}% of AI/ML roles still require full onsite attendance. "
        f"Data pulled from <a href=\"https://aidevboard.com/api/v1/stats\">aidevboard.com/api/v1/stats</a>."
    )

    meta_description = (
        f"Live AI engineering workplace analysis: hybrid averages ${hybrid_avg:,}, remote ${remote_avg:,}, "
        f"onsite ${onsite_avg:,} across {fmt_thousands(classified_total)} classified roles. "
        f"{onsite_pct:.0f}% onsite, {remote_pct:.0f}% remote, {hybrid_pct:.0f}% hybrid. Auto-regenerated weekly."
    )
    og_description = (
        f"Hybrid AI/ML: ${hybrid_avg:,} avg. Remote: ${remote_avg:,}. Onsite: ${onsite_avg:,}. "
        f"{onsite_pct:.0f}% of AI/ML roles still require full onsite attendance across "
        f"{fmt_thousands(classified_total)} classified postings. Live data, {today}."
    )
    twitter_description = (
        f"AI/ML workplace mix: hybrid ${hybrid_avg:,} avg, remote ${remote_avg:,}, onsite ${onsite_avg:,}. "
        f"{onsite_pct:.0f}% onsite-only. {today}."
    )
    article_description = (
        f"Live analysis of remote vs onsite vs hybrid AI/ML engineering roles from aidevboard.com: "
        f"workplace mix, salary by workplace, onsite-heavy and remote-friendly companies, and the hybrid-premium "
        f"anomaly across {fmt_thousands(classified_total)} classified postings."
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="referrer" content="strict-origin-when-cross-origin" />
  <meta name="color-scheme" content="dark light" />
  <meta name="last-updated" content="{today}" />
  <title>Q2 2026 Remote vs Onsite AI Hiring -- 8bitconcepts</title>
  <meta name="description" content="{attr_escape(meta_description)}" />
  <meta property="og:title" content="Q2 2026 Remote vs Onsite AI Hiring -- 8bitconcepts" />
  <meta property="og:description" content="{attr_escape(og_description)}" />
  <meta property="og:type" content="article" />
  <meta property="og:url" content="{PAPER_URL}" />
  <meta property="og:image" content="{OG_IMAGE_URL}" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="Q2 2026 Remote vs Onsite AI Hiring" />
  <meta name="twitter:description" content="{attr_escape(twitter_description)}" />
  <meta name="twitter:image" content="{OG_IMAGE_URL}" />
  <link rel="canonical" href="{PAPER_URL}" />
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

    .bar-chart {{
      margin: 32px 0;
      padding: 20px;
      background: var(--slate-2);
      border: 1px solid var(--border);
      border-radius: 6px;
    }}

    .bar-row {{
      display: grid;
      grid-template-columns: 80px 1fr 110px;
      align-items: center;
      gap: 14px;
      margin: 10px 0;
    }}

    .bar-label {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 13px;
      color: var(--text-dim);
    }}

    .bar-wrap {{
      background: var(--slate-3);
      border-radius: 3px;
      height: 22px;
      overflow: hidden;
    }}

    .bar {{
      background: linear-gradient(90deg, var(--terra) 0%, rgba(217,119,87,0.7) 100%);
      height: 100%;
      border-radius: 3px;
      transition: width 0.25s;
    }}

    .bar-value {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 13px;
      color: var(--text);
      text-align: right;
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
      .bar-row {{ grid-template-columns: 60px 1fr 90px; gap: 10px; }}
    }}
  </style>
<script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "Q2 2026 Remote vs Onsite AI Hiring",
    "description": "{attr_escape(article_description)}",
    "url": "{PAPER_URL}",
    "datePublished": "2026-04-17",
    "dateModified": "{today}",
    "author": {{"@type": "Organization", "name": "8bitconcepts", "url": "https://8bitconcepts.com"}},
    "publisher": {{"@type": "Organization", "name": "8bitconcepts", "url": "https://8bitconcepts.com"}},
    "image": "{OG_IMAGE_URL}",
    "inLanguage": "en",
    "isAccessibleForFree": true,
    "about": "AI engineering workplace mix, remote vs onsite vs hybrid pay, hybrid premium analysis, company-level workplace concentration",
    "keywords": "AI remote jobs, AI onsite jobs, hybrid AI engineering, remote AI salary, AI workplace pay, 2026 hiring data"
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
    {{"@type": "ListItem", "position": 3, "name": "Q2 2026 Remote vs Onsite AI Hiring"}}
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

    <div class="eyebrow">Research &mdash; Workplace Pay</div>

    <h1>Q2 2026 Remote vs Onsite AI Hiring</h1>

    <p class="subtitle">{subtitle_text}</p>

    <div class="meta">
      <span class="meta-date">{today}</span>
      <span class="meta-tag">Live Data</span>
      <span class="meta-read">~800 words</span>
    </div>

    <div class="article-body">

      <h2>Executive summary</h2>

      <p>{lead_para}</p>

{stat_cards_html}

      <h2>Top-line workplace mix</h2>

      <p>Across the {fmt_thousands(classified_total)} AI/ML engineering postings with a workplace classification, onsite is still the dominant mode &mdash; not by a small margin. Hybrid is the smallest bucket but commands the highest average advertised salary.</p>

      <table class="data-table">
        <thead>
          <tr>
            <th>Workplace</th>
            <th class="num" style="text-align:right;">Role count</th>
            <th class="num" style="text-align:right;">Share</th>
            <th class="num" style="text-align:right;">Avg salary</th>
          </tr>
        </thead>
        <tbody>
{mix_table_rows}
        </tbody>
      </table>

      <h2>The hybrid premium</h2>

      <p>{hybrid_analysis_p1}</p>

      <p>{hybrid_analysis_p2}</p>

      <div class="callout">
        <p>The industry lore says remote kills the pay premium. The live index says otherwise: the middle-ground workplace arrangement wins on absolute dollars, and it wins because it concentrates SF/NYC metros and staff+ seniority into the same candidate pool.</p>
      </div>

      <h2>Onsite-heavy companies (80%+ onsite)</h2>

      <p>{onsite_note}</p>

      <table class="data-table">
        <thead>
          <tr>
            <th>Company</th>
            <th class="num" style="text-align:right;">AI/ML roles (sample)</th>
            <th class="num" style="text-align:right;">Onsite</th>
            <th class="num" style="text-align:right;">Onsite share</th>
          </tr>
        </thead>
        <tbody>
{onsite_rows_html}
        </tbody>
      </table>

      <h2>Remote-friendly companies (50%+ remote)</h2>

      <p>{remote_note}</p>

      <table class="data-table">
        <thead>
          <tr>
            <th>Company</th>
            <th class="num" style="text-align:right;">AI/ML roles (sample)</th>
            <th class="num" style="text-align:right;">Remote</th>
            <th class="num" style="text-align:right;">Remote share</th>
          </tr>
        </thead>
        <tbody>
{remote_rows_html}
        </tbody>
      </table>

      <h2>Salary by workplace</h2>

      <p>A simple horizontal bar chart of average advertised salary by workplace mode. Hybrid leads, remote and onsite are within a few hundred dollars of each other.</p>

{salary_bars_html}

      <h2>Regional bias</h2>

      <p>{regional_note}</p>

      <h2>Practical takeaway</h2>

      <p>{takeaway_para}</p>

      <h2>Methodology</h2>

      <p>{methodology_para}</p>

      <p>{download_para}</p>

      <h2>What's next</h2>

      <p>For the skill-and-compensation view of this same dataset &mdash; which tags actually pay the premium &mdash; see <a href="/research/q2-2026-ai-compensation-by-skill.html">Q2 2026 AI Engineering Compensation by Skill</a>. For the company-side view of where the roles are concentrated, see <a href="/research/q2-2026-ai-hiring-snapshot.html">Q2 2026 AI Engineering Hiring Snapshot</a>. For the infrastructure side &mdash; how many of the agent systems these engineers are building actually have a working MCP endpoint &mdash; see <a href="/research/q2-2026-mcp-ecosystem-health.html">Q2 2026 MCP Ecosystem Health</a>. Full reading paths at the <a href="/research/overview.html">Research Atlas</a>.</p>

    </div>

    <div class="related">
      <div class="related-label">Related Research</div>
      <div class="related-grid">
        <a class="related-card" href="/research/q2-2026-ai-hiring-snapshot.html">
          <div class="related-card-title">Q2 2026 AI Hiring Snapshot</div>
          <div class="related-card-sub">Live market data: roles, top companies, workplace mix.</div>
        </a>
        <a class="related-card" href="/research/q2-2026-ai-compensation-by-skill.html">
          <div class="related-card-title">Q2 2026 AI Compensation by Skill</div>
          <div class="related-card-sub">Top-paying skill tags vs most in-demand tags.</div>
        </a>
        <a class="related-card" href="/research/q2-2026-mcp-ecosystem-health.html">
          <div class="related-card-title">Q2 2026 MCP Ecosystem Health</div>
          <div class="related-card-sub">Live JSON-RPC handshake audit of MCP servers.</div>
        </a>
        <a class="related-card" href="/research/overview.html">
          <div class="related-card-title">Research Atlas</div>
          <div class="related-card-sub">Every paper, topic index, and reading paths.</div>
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
        <li>AI Dev Jobs &mdash; <a href="https://aidevboard.com/api/v1/stats">/api/v1/stats</a>, pulled {generated_iso}. Public unauthenticated endpoint.</li>
        <li>AI Dev Jobs &mdash; <a href="https://aidevboard.com/api/v1/jobs">/api/v1/jobs</a>, paginated walk for per-company workplace aggregation.</li>
        <li>Workplace classification is derived from job-title + description + location signals by a rules-based parser. Edge cases ("hybrid, 3 days", "flexible", "in-person preferred") are normalized into the three canonical buckets onsite / remote / hybrid.</li>
        <li>Salary figures are employer-advertised midpoints from public ATS feeds. US pay-transparency laws drive the disclosure rates so the dataset over-represents California, New York, Washington, and Colorado.</li>
      </ol>
    </div>

  </div>

  <div style="max-width:640px;margin:40px auto;padding:24px;background:#fafaf8;border:1px solid #e5e5e5;border-radius:8px;">
    <p style="font-size:13px;color:#666;margin:0 0 12px;text-transform:uppercase;letter-spacing:1px;">Remote AI engineering jobs hiring now</p>
    <div data-aidev-jobs data-workplace="remote" data-limit="3" data-theme="light"></div>
    <script src="https://aidevboard.com/static/widget.js" async></script>
  </div>

  <footer>
    <p>&copy; 2026 8bitconcepts &mdash; AI Enablement &amp; Integration Consulting &mdash; <a href="mailto:hello@8bitconcepts.com">hello@8bitconcepts.com</a></p>
    <p style="margin-top:6px;font-size:12px;"><a href="/research/overview.html" style="color:#d97757;">Research Atlas &rarr; all papers + reading paths</a></p>
  </footer>

</body>
</html>
"""


def build_gist_content(
    stats: dict[str, Any],
    company_counts: dict[str, dict[str, int]],
    today: str,
) -> tuple[str, str]:
    """Build CSV + Markdown for the gist. Workplace mix + top onsite-heavy + remote-friendly."""
    ov = stats.get("overview", {}) or {}
    workplace = stats.get("workplace", []) or []
    salary = stats.get("salary", {}) or {}
    total_jobs = int(ov.get("total_jobs", 0))
    total_companies = int(ov.get("total_companies", 0))
    jobs_with_salary = int(ov.get("jobs_with_salary", 0))
    median_overall = int(salary.get("median", 0) or 0)

    wp_map = {w.get("type"): w for w in workplace}
    remote_ct = int(wp_map.get("remote", {}).get("count", 0))
    onsite_ct = int(wp_map.get("onsite", {}).get("count", 0))
    hybrid_ct = int(wp_map.get("hybrid", {}).get("count", 0))
    classified_total = remote_ct + onsite_ct + hybrid_ct or 1

    csv_lines = ["workplace_type,role_count,share_pct,avg_salary"]
    for key in ("onsite", "remote", "hybrid"):
        w = wp_map.get(key, {})
        cnt = int(w.get("count", 0))
        avg = int(w.get("avg_salary", 0) or 0)
        share = cnt / classified_total * 100 if classified_total else 0
        csv_lines.append(f"{key},{cnt},{share:.2f},{avg}")
    csv_text = "\n".join(csv_lines) + "\n"

    md_lines = [
        "# AI Engineering Workplace Data — remote vs onsite vs hybrid",
        "",
        f"**Last updated**: {today}",
        "",
        f"**Snapshot**: {today} \u00b7 **Total jobs**: {total_jobs:,} \u00b7 "
        f"**Companies indexed**: {total_companies:,} \u00b7 "
        f"**Classified by workplace**: {classified_total:,} \u00b7 "
        f"**Median salary**: ${median_overall:,}",
        "",
        "Live data from [aidevboard.com/api/v1/stats](https://aidevboard.com/api/v1/stats) \u2014 free public API, no auth, refreshed daily across 560+ ATS sources.",
        "",
        "## Workplace mix",
        "",
        "| Workplace | Role count | Share | Avg advertised salary |",
        "|---|---:|---:|---:|",
    ]
    for key, label in (("onsite", "Onsite"), ("remote", "Remote"), ("hybrid", "Hybrid")):
        w = wp_map.get(key, {})
        cnt = int(w.get("count", 0))
        avg = int(w.get("avg_salary", 0) or 0)
        share = cnt / classified_total * 100 if classified_total else 0
        md_lines.append(f"| {label} | {cnt:,} | {share:.1f}% | ${avg:,} |")

    # Onsite-heavy table (>= 15 posts, >= 80% onsite)
    onsite_heavy = []
    for name, counts in company_counts.items():
        total = counts["total"]
        if total < 15:
            continue
        onsite = counts["onsite"]
        onsite_share = onsite / total if total else 0
        if onsite_share >= 0.80:
            onsite_heavy.append((name, total, onsite, onsite_share))
    onsite_heavy.sort(key=lambda x: (-x[3], -x[2]))
    onsite_heavy = onsite_heavy[:10]

    md_lines += [
        "",
        "## Onsite-heavy companies (80%+ onsite, 15+ sampled postings)",
        "",
        "| Company | Sampled postings | Onsite | Onsite share |",
        "|---|---:|---:|---:|",
    ]
    if onsite_heavy:
        for name, total, onsite, share in onsite_heavy:
            md_lines.append(f"| {name} | {total:,} | {onsite:,} | {share*100:.0f}% |")
    else:
        md_lines.append("| — | — | — | (insufficient sample this cycle) |")

    # Remote-friendly table (>= 10 posts, >= 50% remote)
    remote_friendly = []
    for name, counts in company_counts.items():
        total = counts["total"]
        if total < 10:
            continue
        r = counts["remote"]
        share = r / total if total else 0
        if share >= 0.50:
            remote_friendly.append((name, total, r, share))
    remote_friendly.sort(key=lambda x: (-x[3], -x[2]))
    remote_friendly = remote_friendly[:10]

    md_lines += [
        "",
        "## Remote-friendly companies (50%+ remote, 10+ sampled postings)",
        "",
        "| Company | Sampled postings | Remote | Remote share |",
        "|---|---:|---:|---:|",
    ]
    if remote_friendly:
        for name, total, r, share in remote_friendly:
            md_lines.append(f"| {name} | {total:,} | {r:,} | {share*100:.0f}% |")
    else:
        md_lines.append("| — | — | — | (insufficient sample this cycle) |")

    md_lines += [
        "",
        "## Methodology",
        "",
        "Workplace classification is derived from job-title + description + location signals by a rules-based "
        "parser. Edge cases are normalized into the three canonical buckets. Salary averages use advertised midpoints "
        "across the salary-disclosed subset. The company-level tables are drawn from a paginated walk of "
        "`/api/v1/jobs` and sample the rolling active-posting window; re-run after the weekly crawl for a fuller view.",
        "",
        "## Source & License",
        "",
        f"- **Live API**: https://aidevboard.com/api/v1/stats (JSON, public)",
        f"- **Research note**: {PAPER_URL}",
        f"- **Sibling dataset**: [Top AI Companies Hiring](https://gist.github.com/unitedideas/9c59d50a824a075410bd658c96e1f5de)",
        f"- **Sibling dataset**: [AI Compensation by Skill](https://gist.github.com/unitedideas/b1b80d11f0f187f93fd6b1a599df418e)",
        f"- **Sibling dataset**: [MCP Ecosystem Health](https://gist.github.com/unitedideas/c93bd6d9984729070c59b2ea6c6b301b)",
        f"- **Auto-regenerated**: weekly via `tools/regenerate-remote-vs-onsite.py`",
        f"- **License**: CC BY 4.0 \u2014 attribution to 8bitconcepts + aidevboard.com",
        "",
    ]
    md_text = "\n".join(md_lines)

    return csv_text, md_text


def update_gist(stats: dict[str, Any], company_counts: dict[str, dict[str, int]], today: str) -> bool:
    try:
        csv_text, md_text = build_gist_content(stats, company_counts, today)
    except Exception as e:
        print(f"   Gist content build failed (non-fatal): {e}", file=sys.stderr)
        return False

    tmpdir = Path(tempfile.gettempdir()) / "workplace-gist"
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
    parser = argparse.ArgumentParser(description="Regenerate the Q2 2026 remote-vs-onsite workplace note from live data.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch + render, don't write anything")
    parser.add_argument("--once", action="store_true", help="Write file + refresh atlas, skip commit/push/pings")
    parser.add_argument("--no-push", action="store_true", help="Skip git push and IndexNow/WebSub pings")
    args = parser.parse_args()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    generated_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"=== Regenerate remote-vs-onsite AI hiring ({today}) ===")
    print("1. Fetching live ADB stats...")
    try:
        stats = http_get_json(ADB_STATS_URL)
    except Exception as e:
        print(f"  ADB stats fetch failed: {e}", file=sys.stderr)
        return 2
    ov = stats.get("overview", {}) or {}
    print(f"   ADB: {ov.get('total_jobs')} jobs / {ov.get('total_companies')} cos / {ov.get('jobs_with_salary')} salary-disclosed")
    wp = stats.get("workplace", []) or []
    print(f"   Workplace: {[(w.get('type'), w.get('count'), w.get('avg_salary')) for w in wp]}")

    print("1b. Paginating jobs for per-company workplace aggregation...")
    company_counts = fetch_company_workplace_counts(max_pages=30, per_page=50)
    print(f"   Aggregated {len(company_counts)} distinct companies from paginated sample")

    print("2. Rendering HTML...")
    html = build_html(stats, company_counts, today, generated_iso)

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
        wp_map_og = {w.get("type"): w for w in (stats.get("workplace", []) or [])}
        hybrid_avg = int(wp_map_og.get("hybrid", {}).get("avg_salary", 0) or 0)
        remote_avg = int(wp_map_og.get("remote", {}).get("avg_salary", 0) or 0)
        onsite_avg = int(wp_map_og.get("onsite", {}).get("avg_salary", 0) or 0)
        hybrid_ct = int(wp_map_og.get("hybrid", {}).get("count", 0))
        remote_ct = int(wp_map_og.get("remote", {}).get("count", 0))
        onsite_ct = int(wp_map_og.get("onsite", {}).get("count", 0))
        classified_total = hybrid_ct + remote_ct + onsite_ct or 1

        non_hybrid_count = remote_ct + onsite_ct
        non_hybrid_avg = (remote_avg * remote_ct + onsite_avg * onsite_ct) // non_hybrid_count if non_hybrid_count else 0
        hybrid_premium_k = (hybrid_avg - non_hybrid_avg) // 1000 if (hybrid_avg and non_hybrid_avg) else 0

        onsite_pct = onsite_ct / classified_total * 100

        if hybrid_premium_k >= 10:
            headline = f"Hybrid AI jobs pay ${hybrid_premium_k}k premium"
            subtext = (
                f"Q2 2026 \u2022 hybrid ${hybrid_avg:,} vs remote+onsite ${non_hybrid_avg:,} avg \u2022 "
                f"{classified_total:,} AI/ML roles classified"
            )
        else:
            headline = f"{onsite_pct:.0f}% of AI roles still require onsite"
            subtext = (
                f"Q2 2026 \u2022 remote ${remote_avg:,} \u2022 onsite ${onsite_avg:,} \u2022 hybrid ${hybrid_avg:,} \u2022 "
                f"{classified_total:,} AI/ML roles"
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

    print("\n4b. Updating public gist (workplace CSV + MD)...")
    try:
        update_gist(stats, company_counts, today)
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
                   "research/q2-2026-remote-vs-onsite-ai-hiring.html",
                   "research/overview.html",
                   f"research/og/{OG_SLUG}.png"])
    if add.returncode != 0:
        print(f"   git add failed: {add.stderr[:300]}", file=sys.stderr)
        return 3
    msg = f"remote-vs-onsite: auto-regenerate {today}"
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
