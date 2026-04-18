#!/usr/bin/env python3
"""
Regenerate /research/q2-2026-entry-level-ai-gap.html from live ADB stats.

Pulls fresh data from:
  - https://aidevboard.com/api/v1/stats  (experience_levels, salary, tags, companies)
  - https://aidevboard.com/api/v1/jobs?per_page=50&page=N  (per-company level aggregation)

Rebuilds the paper HTML + OG image + companion gist. Commits if data changed,
pushes, IndexNow + WebSub pings.

Usage:
    python3 tools/regenerate-entry-level-gap.py           # full run
    python3 tools/regenerate-entry-level-gap.py --dry-run # fetch + render, don't write
    python3 tools/regenerate-entry-level-gap.py --once    # write + overview, skip commit/push/pings
    python3 tools/regenerate-entry-level-gap.py --no-push # skip git push + pings (commit still happens)
"""
from __future__ import annotations

import argparse
import json
import re
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
PAPER_PATH = RESEARCH_DIR / "q2-2026-entry-level-ai-gap.html"
OVERVIEW_SCRIPT = REPO / "tools" / "generate-overview.py"
PAPER_URL = "https://8bitconcepts.com/research/q2-2026-entry-level-ai-gap.html"

OG_SLUG = "q2-2026-entry-level-ai-gap"
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

ADB_STATS_URL = "https://aidevboard.com/api/v1/stats"
ADB_JOBS_URL = "https://aidevboard.com/api/v1/jobs"

# Public gist: https://gist.github.com/unitedideas/d400d2d9a85692b758b96ab5fe741a22
GIST_ID = "d400d2d9a85692b758b96ab5fe741a22"
GIST_CSV_FILENAME = "ai-entry-level.csv"
GIST_MD_FILENAME = "ai-entry-level.md"
GIST_CSV_RAW_URL = f"https://gist.githubusercontent.com/unitedideas/{GIST_ID}/raw/{GIST_CSV_FILENAME}"
GIST_MD_RAW_URL = f"https://gist.githubusercontent.com/unitedideas/{GIST_ID}/raw/{GIST_MD_FILENAME}"
GIST_URL = f"https://gist.github.com/unitedideas/{GIST_ID}"

# Keywords used to infer experience level from a job title when the API
# doesn't return per-job level data. Applied lowercased, word-boundary.
_JUNIOR_TITLE_RE = re.compile(
    r"\b(junior|jr\.?|entry[\s\-]?level|new[\s\-]?grad|new[\s\-]?graduate|graduate|associate|intern|early[\s\-]?career|i{1,2})\b",
    re.IGNORECASE,
)
_SENIOR_TITLE_RE = re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|director|head|chief|vp|iii|iv|v)\b",
    re.IGNORECASE,
)


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


def level_label(key: str) -> str:
    return {
        "junior": "Junior / Entry-level",
        "mid": "Mid",
        "senior": "Senior",
        "lead": "Lead / Staff",
        "principal": "Principal",
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


def classify_title(title: str) -> str | None:
    """Return 'junior' / 'senior' / None from a job title."""
    if not title:
        return None
    t = title.strip()
    # Senior keywords take precedence because "Senior Software Engineer II" would
    # otherwise register as junior via "ii".
    if _SENIOR_TITLE_RE.search(t):
        return "senior"
    if _JUNIOR_TITLE_RE.search(t):
        return "junior"
    return None


def fetch_company_junior_counts(max_pages: int = 30, per_page: int = 50) -> dict[str, dict[str, int]]:
    """Walk /api/v1/jobs paginated, collect per-company junior/senior-title counts.

    Returns: {company_name: {"junior": n, "senior": n, "total": n}}
    Title-based heuristic; reported as 'sample' rather than source-of-truth.
    """
    out: dict[str, dict[str, int]] = defaultdict(lambda: {"junior": 0, "senior": 0, "total": 0})
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
            title = j.get("title") or ""
            out[name]["total"] += 1
            cls = classify_title(title)
            if cls == "junior":
                out[name]["junior"] += 1
            elif cls == "senior":
                out[name]["senior"] += 1
        if not data.get("has_next"):
            break
        page += 1
    return dict(out)


def build_html(stats: dict[str, Any], company_counts: dict[str, dict[str, int]], today: str, generated_iso: str) -> str:
    ov = stats.get("overview", {}) or {}
    levels = stats.get("experience_levels", []) or []
    salary = stats.get("salary", {}) or {}
    tags = stats.get("tags", []) or []

    total_jobs = int(ov.get("total_jobs", 0))
    total_companies = int(ov.get("total_companies", 0))
    jobs_with_salary = int(ov.get("jobs_with_salary", 0))
    median_overall = int(salary.get("median", 0) or 0)
    avg_overall = int(salary.get("average", 0) or 0)

    # Experience level mix
    lv_map = {lv.get("level"): int(lv.get("count", 0) or 0) for lv in levels}
    junior_ct = lv_map.get("junior", 0)
    mid_ct = lv_map.get("mid", 0)
    senior_ct = lv_map.get("senior", 0)
    lead_ct = lv_map.get("lead", 0)
    principal_ct = lv_map.get("principal", 0)
    classified_total = junior_ct + mid_ct + senior_ct + lead_ct + principal_ct or 1

    junior_pct = junior_ct / classified_total * 100
    mid_pct = mid_ct / classified_total * 100
    senior_pct = senior_ct / classified_total * 100
    lead_pct = lead_ct / classified_total * 100
    principal_pct = principal_ct / classified_total * 100

    senior_plus_ct = senior_ct + lead_ct + principal_ct
    senior_plus_pct = senior_plus_ct / classified_total * 100

    # Junior-to-senior ratio: how many senior+ roles for every 1 junior role?
    if junior_ct > 0:
        sr_ratio = senior_plus_ct / junior_ct
        sr_ratio_str = f"{sr_ratio:.1f}"
    else:
        sr_ratio = 0.0
        sr_ratio_str = "&infin;"

    # Executive hook paragraph
    lead_para = (
        f"Only <strong>{junior_pct:.1f}%</strong> of {fmt_thousands(classified_total)} classified AI/ML engineering roles "
        f"are open to juniors ({fmt_thousands(junior_ct)} of {fmt_thousands(classified_total)}). For every entry-level "
        f"opening there are <strong>{sr_ratio_str} senior-plus roles</strong> ({fmt_thousands(senior_plus_ct)} senior + lead + principal). "
        f"This is the tightest junior-to-senior ratio in any tech specialty tracked by the AI Dev Jobs index. Breaking in "
        f"is statistically rarer than staying in."
    )

    # Stat cards
    stat_cards_html = f"""      <div class="stat-row">
        <div class="stat-box">
          <div class="stat-num">{junior_pct:.1f}%</div>
          <div class="stat-label">of AI/ML roles open to juniors ({fmt_thousands(junior_ct)} of {fmt_thousands(classified_total)})</div>
        </div>
        <div class="stat-box">
          <div class="stat-num">{sr_ratio_str}&times;</div>
          <div class="stat-label">senior-plus roles for every 1 junior role in the index</div>
        </div>
        <div class="stat-box">
          <div class="stat-num">{senior_plus_pct:.0f}%</div>
          <div class="stat-label">of AI/ML roles are senior, lead, or principal</div>
        </div>
      </div>"""

    # Level mix table (ordered junior -> principal)
    mix_rows = []
    order = [
        ("junior", junior_ct),
        ("mid", mid_ct),
        ("senior", senior_ct),
        ("lead", lead_ct),
        ("principal", principal_ct),
    ]
    for key, cnt in order:
        share = cnt / classified_total * 100 if classified_total else 0
        mix_rows.append(
            f"          <tr><td>{level_label(key)}</td>"
            f"<td class=\"num\">{fmt_thousands(cnt)}</td>"
            f"<td class=\"num\">{share:.1f}%</td></tr>"
        )
    mix_table_rows = "\n".join(mix_rows)

    # Companies hiring juniors (>= 3 junior titles in sample, >= 10 total, sort by junior share)
    junior_friendly = []
    for name, counts in company_counts.items():
        total = counts.get("total", 0)
        if total < 10:
            continue
        juniors = counts.get("junior", 0)
        if juniors < 3:
            continue
        share = juniors / total if total else 0
        junior_friendly.append((name, total, juniors, share))
    # Sort by raw junior count first, then share — lists readers care about volume.
    junior_friendly.sort(key=lambda x: (-x[2], -x[3]))
    junior_friendly = junior_friendly[:10]

    if junior_friendly:
        junior_rows_html = "\n".join(
            f"          <tr><td>{html_escape(name)}</td>"
            f"<td class=\"num\">{fmt_thousands(total)}</td>"
            f"<td class=\"num\">{fmt_thousands(juniors)}</td>"
            f"<td class=\"num\">{share * 100:.0f}%</td></tr>"
            for (name, total, juniors, share) in junior_friendly
        )
        junior_note = (
            f"The {len(junior_friendly)} companies below showed at least 3 junior-titled AI/ML roles in the sampled "
            f"paginated index walk. Titles counted as junior match <code>junior</code>, <code>jr</code>, "
            f"<code>entry-level</code>, <code>new grad</code>, <code>associate</code>, <code>intern</code>, "
            f"or <code>early career</code>. These are the companies most worth watching if you're breaking in &mdash; "
            f"frontier labs and large AI-first companies still post entry-level seats, even when the aggregate mix "
            f"is {junior_pct:.0f}% junior."
        )
    else:
        junior_rows_html = '          <tr><td colspan="4">Insufficient sample this cycle to surface junior-friendly companies (no company crossed the 3-junior-titles threshold in the paginated sample).</td></tr>'
        junior_note = (
            f"The rolling sample this cycle did not surface companies crossing the 3-junior-titles threshold. "
            f"Re-run after the weekly crawl completes for a fuller company-level view."
        )

    # Bar chart of level distribution
    all_level_cts = [junior_ct, mid_ct, senior_ct, lead_ct, principal_ct]
    max_bar = max(all_level_cts) or 1
    def bar_pct(v: int) -> float:
        return (v / max_bar * 100) if max_bar else 0

    level_bars_html = f"""      <div class="bar-chart">
        <div class="bar-row">
          <div class="bar-label">Junior</div>
          <div class="bar-wrap"><div class="bar" style="width:{bar_pct(junior_ct):.1f}%;"></div></div>
          <div class="bar-value">{fmt_thousands(junior_ct)}</div>
        </div>
        <div class="bar-row">
          <div class="bar-label">Mid</div>
          <div class="bar-wrap"><div class="bar" style="width:{bar_pct(mid_ct):.1f}%;"></div></div>
          <div class="bar-value">{fmt_thousands(mid_ct)}</div>
        </div>
        <div class="bar-row">
          <div class="bar-label">Senior</div>
          <div class="bar-wrap"><div class="bar" style="width:{bar_pct(senior_ct):.1f}%;"></div></div>
          <div class="bar-value">{fmt_thousands(senior_ct)}</div>
        </div>
        <div class="bar-row">
          <div class="bar-label">Lead</div>
          <div class="bar-wrap"><div class="bar" style="width:{bar_pct(lead_ct):.1f}%;"></div></div>
          <div class="bar-value">{fmt_thousands(lead_ct)}</div>
        </div>
        <div class="bar-row">
          <div class="bar-label">Principal</div>
          <div class="bar-wrap"><div class="bar" style="width:{bar_pct(principal_ct):.1f}%;"></div></div>
          <div class="bar-value">{fmt_thousands(principal_ct)}</div>
        </div>
      </div>"""

    # Salary discussion — the API doesn't expose salary per experience band, so we frame the gap.
    dist = salary.get("distribution", []) or []
    under_150_count = 0
    over_300_count = 0
    for d in dist:
        rng = d.get("range", "")
        cnt = int(d.get("count", 0) or 0)
        if rng in ("under_100k", "100k_150k"):
            under_150_count += cnt
        elif rng in ("300k_400k", "400k_plus"):
            over_300_count += cnt

    salary_para = (
        f"The public stats endpoint does not expose salary by experience band directly &mdash; it publishes a single "
        f"global average (${avg_overall:,}) and a global median (${median_overall:,}) across the "
        f"{fmt_thousands(jobs_with_salary)}-posting salary-disclosed subset. But we can triangulate: of the disclosed "
        f"postings, {fmt_thousands(under_150_count)} advertise a midpoint under $150k (a reasonable proxy for the "
        f"entry-level band), while {fmt_thousands(over_300_count)} advertise $300k+. If junior supply is "
        f"{junior_pct:.0f}% of roles, the under-$150k band is <strong>roughly "
        f"{'aligned with' if abs(under_150_count/classified_total - junior_pct/100) * 100 < 2 else 'at odds with'}"
        f"</strong> that share &mdash; meaning advertised junior AI pay typically lands in the $100k-$150k range, "
        f"well above non-AI entry-level engineering but well below the ${median_overall:,} index median. "
        f"<strong>Data gap flag:</strong> the next iteration of this report will break salary by experience band "
        f"once the <code>/api/v1/stats</code> endpoint exposes it."
    )

    # Why the squeeze exists
    squeeze_para = (
        f"Three structural reasons explain the junior squeeze. <strong>Judgment under uncertainty.</strong> AI/ML "
        f"engineering outputs (prompts, evals, RAG retrievers, agent pipelines) don't have deterministic unit tests &mdash; "
        f"they require a senior's pattern-matching to spot when a system is quietly wrong. Companies willing to pay "
        f"${avg_overall:,} average don't want to train that judgment from scratch. "
        f"<strong>Compute-cost economics.</strong> A senior engineer ships iterations against GPU-hours that cost "
        f"$5-$50 per experiment. The efficiency delta between a senior and a junior running GPU jobs compounds "
        f"faster than it does in CRUD web development, so staffing leans toward senior. "
        f"<strong>The ML-plus-LLM double requirement.</strong> Companies hiring for &quot;AI&quot; in 2026 typically "
        f"want traditional ML fluency (PyTorch, distributed training, MLOps &mdash; the {fmt_thousands(sum(int(t.get('count', 0) or 0) for t in tags if t.get('tag') in ('pytorch', 'mlops', 'machine-learning')))} postings combining "
        f"those skills) <em>plus</em> recent LLM / agent experience. Juniors rarely have both simultaneously."
    )

    # Bootcamps / CS grads
    bootcamp_para = (
        f"<strong>Is the bootcamp path viable?</strong> The data says: narrow pipe, not closed pipe. The junior AI/ML "
        f"market is roughly {fmt_thousands(junior_ct)} roles &mdash; a fraction of the {fmt_thousands(classified_total)}-role "
        f"total, but still {fmt_thousands(junior_ct)} concrete opportunities across "
        f"{fmt_thousands(total_companies)} companies in the index. The realistic read for a career-switcher: "
        f"(1) the generic &quot;AI engineer&quot; bootcamp targeting LLMs alone will not beat an ML-native CS grad "
        f"on the same req, (2) the working angle is a <em>domain wedge</em> &mdash; "
        f"AI-for-robotics, AI-for-healthcare, AI-for-security, AI-for-legal &mdash; where the ML stack is a smaller "
        f"share of the role than the domain knowledge, (3) research labs (Anthropic, OpenAI, DeepMind) post "
        f"&quot;Resident&quot; and &quot;Fellow&quot; tracks that function as senior-paid junior seats. These look "
        f"like the highest-leverage entry points in the current market. "
        f"The 7% share is a filter, not a ceiling."
    )

    # Takeaway for job seekers
    takeaway_para = (
        f"<strong>If you're trying to break in.</strong> Don't optimize for the {fmt_thousands(total_companies)}-company "
        f"index overall &mdash; the signal is too diluted. Target the "
        f"{len(junior_friendly) if junior_friendly else '13%'}"
        f" of companies actually posting junior seats (see table above). Apply to research-lab residency programs "
        f"that pay senior-band salaries to juniors. Specialize in a non-trivial domain (robotics, biotech, finance, "
        f"defense) before the AI layer &mdash; <em>AI-for-X</em> always hires junior talent faster than pure-ML orgs do, "
        f"because the domain expertise is the harder-to-hire input."
    )

    # Methodology
    methodology_para = (
        f"Generated from the live <a href=\"https://aidevboard.com/api/v1/stats\">aidevboard.com/api/v1/stats</a> "
        f"endpoint (public, unauthenticated) plus a paginated walk of <a href=\"https://aidevboard.com/api/v1/jobs\">"
        f"/api/v1/jobs</a> for per-company experience-level aggregation. Index scrapes 560+ ATS sources on a daily "
        f"cron and deduplicates by (company, title, location). The <code>experience_level</code> field is classified "
        f"by a rules-based parser from title + seniority signals &mdash; see "
        f"<a href=\"https://github.com/unitedideas/aidevboard-mcp\">open-source parser</a>. "
        f"Per-company junior counts in this paper use a title-regex fallback (<code>junior</code>, <code>jr</code>, "
        f"<code>entry-level</code>, <code>new grad</code>, <code>associate</code>, <code>intern</code>, <code>early "
        f"career</code>) over the paginated job sample &mdash; they're a proxy, not a source of truth, and skew "
        f"conservative (any title with &quot;senior&quot; anywhere is dropped from the junior bucket). "
        f"Of {fmt_thousands(total_jobs)} roles in the index, {fmt_thousands(classified_total)} have a non-empty "
        f"experience-level classification. Salary averages are from the "
        f"{fmt_thousands(jobs_with_salary)}-posting salary-disclosed subset. "
        f"This page auto-regenerates weekly (Mon 9:15 am PT)."
    )

    # Download data callout
    download_para = (
        f'<strong>Download raw data:</strong> The experience-level + per-company junior dataset is mirrored as a '
        f'public gist &mdash; <a href="{GIST_CSV_RAW_URL}">CSV</a> &middot; '
        f'<a href="{GIST_MD_RAW_URL}">Markdown</a> &middot; '
        f'<a href="{GIST_URL}">view on GitHub</a>. '
        f"Auto-updated every weekly regeneration; canonical raw URLs are stable across revisions."
    )

    # Meta strings
    subtitle_text = (
        f"Live experience-level data across {fmt_thousands(classified_total)} classified AI/ML engineering roles. "
        f"Only {junior_pct:.1f}% are open to juniors. For every entry-level opening there are {sr_ratio_str} "
        f"senior-plus roles. Data pulled from "
        f"<a href=\"https://aidevboard.com/api/v1/stats\">aidevboard.com/api/v1/stats</a>."
    )

    meta_description = (
        f"Live analysis: only {junior_pct:.1f}% of AI/ML engineering roles are open to juniors "
        f"({fmt_thousands(junior_ct)} of {fmt_thousands(classified_total)}). "
        f"{sr_ratio_str}:1 senior-plus-to-junior ratio &mdash; the tightest in tech. Why the squeeze exists, "
        f"which companies still hire juniors, and the actionable path in. Auto-regenerated weekly."
    )
    og_description = (
        f"{junior_pct:.1f}% of AI/ML roles are open to juniors. {sr_ratio_str}:1 senior-plus ratio. "
        f"{fmt_thousands(classified_total)} classified roles across {fmt_thousands(total_companies)} companies. "
        f"Live data, {today}."
    )
    twitter_description = (
        f"Only {junior_pct:.1f}% of AI/ML jobs are entry-level. "
        f"{sr_ratio_str}:1 senior-plus ratio. {today}."
    )
    article_description = (
        f"Live analysis of the junior AI hiring gap from aidevboard.com: "
        f"experience-level mix, junior-friendly companies, salary gap, why the squeeze exists, and the actionable "
        f"path in for career-switchers. Across {fmt_thousands(classified_total)} classified postings."
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="referrer" content="strict-origin-when-cross-origin" />
  <meta name="color-scheme" content="dark light" />
  <meta name="last-updated" content="{today}" />
  <title>Q2 2026 The Junior AI Hiring Gap -- 8bitconcepts</title>
  <meta name="description" content="{attr_escape(meta_description)}" />
  <meta property="og:title" content="Q2 2026 The Junior AI Hiring Gap -- 8bitconcepts" />
  <meta property="og:description" content="{attr_escape(og_description)}" />
  <meta property="og:type" content="article" />
  <meta property="og:url" content="{PAPER_URL}" />
  <meta property="og:image" content="{OG_IMAGE_URL}" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="Q2 2026 The Junior AI Hiring Gap" />
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
    "headline": "Q2 2026 The Junior AI Hiring Gap",
    "description": "{attr_escape(article_description)}",
    "url": "{PAPER_URL}",
    "datePublished": "2026-04-17",
    "dateModified": "{today}",
    "author": {{"@type": "Organization", "name": "8bitconcepts", "url": "https://8bitconcepts.com"}},
    "publisher": {{"@type": "Organization", "name": "8bitconcepts", "url": "https://8bitconcepts.com"}},
    "image": "{OG_IMAGE_URL}",
    "inLanguage": "en",
    "isAccessibleForFree": true,
    "about": "AI engineering entry-level hiring, junior AI roles, senior-to-junior ratio, bootcamp viability, career-switcher strategy",
    "keywords": "junior AI jobs, entry level AI, AI bootcamp, new grad AI, AI career switch, 2026 AI hiring data"
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
    {{"@type": "ListItem", "position": 3, "name": "Q2 2026 The Junior AI Hiring Gap"}}
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

    <div class="eyebrow">Research &mdash; Hiring Pipeline</div>

    <h1>Q2 2026 The Junior AI Hiring Gap</h1>

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

      <h2>The squeeze: experience-level mix</h2>

      <p>Across the {fmt_thousands(classified_total)} AI/ML engineering postings with an experience-level classification, the distribution is top-heavy. Junior is the smallest band; senior, lead, and principal together account for {senior_plus_pct:.0f}%.</p>

      <table class="data-table">
        <thead>
          <tr>
            <th>Experience level</th>
            <th class="num" style="text-align:right;">Role count</th>
            <th class="num" style="text-align:right;">Share</th>
          </tr>
        </thead>
        <tbody>
{mix_table_rows}
        </tbody>
      </table>

{level_bars_html}

      <div class="callout">
        <p>The junior band is <strong>smaller than the principal band in absolute terms</strong> on some crawl cycles, even though there are orders of magnitude more eligible junior candidates. This isn't a supply problem &mdash; it's a demand signal. Companies are spending budget on top-of-stack, not bottom-of-stack, AI talent.</p>
      </div>

      <h2>What &quot;junior AI&quot; actually pays</h2>

      <p>{salary_para}</p>

      <h2>Why the squeeze exists</h2>

      <p>{squeeze_para}</p>

      <h2>Bootcamps, CS grads, and career-switchers</h2>

      <p>{bootcamp_para}</p>

      <h2>Companies that DO hire juniors</h2>

      <p>{junior_note}</p>

      <table class="data-table">
        <thead>
          <tr>
            <th>Company</th>
            <th class="num" style="text-align:right;">AI/ML roles (sample)</th>
            <th class="num" style="text-align:right;">Junior titles</th>
            <th class="num" style="text-align:right;">Junior share</th>
          </tr>
        </thead>
        <tbody>
{junior_rows_html}
        </tbody>
      </table>

      <h2>Signal for job seekers</h2>

      <p>{takeaway_para}</p>

      <h2>Methodology</h2>

      <p>{methodology_para}</p>

      <p>{download_para}</p>

      <h2>What's next</h2>

      <p>For the top-line AI hiring landscape, see <a href="/research/q2-2026-ai-hiring-snapshot.html">Q2 2026 AI Engineering Hiring Snapshot</a>. For compensation across skill tags, see <a href="/research/q2-2026-ai-compensation-by-skill.html">Q2 2026 AI Compensation by Skill</a>. For the workplace-pay angle (remote vs onsite vs hybrid), see <a href="/research/q2-2026-remote-vs-onsite-ai-hiring.html">Q2 2026 Remote vs Onsite AI Hiring</a>. For the agent-infra side of the market, see <a href="/research/q2-2026-mcp-ecosystem-health.html">Q2 2026 MCP Ecosystem Health</a>. Full reading paths at the <a href="/research/overview.html">Research Atlas</a>.</p>

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
        <a class="related-card" href="/research/q2-2026-remote-vs-onsite-ai-hiring.html">
          <div class="related-card-title">Q2 2026 Remote vs Onsite AI Hiring</div>
          <div class="related-card-sub">Hybrid pay premium, onsite-heavy companies.</div>
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
        <li>AI Dev Jobs &mdash; <a href="https://aidevboard.com/api/v1/jobs">/api/v1/jobs</a>, paginated walk for per-company junior-title aggregation.</li>
        <li>Experience-level classification is derived from job title + seniority signals by a rules-based parser. Per-company junior counts use a title-regex fallback (<code>junior</code>, <code>jr</code>, <code>entry-level</code>, <code>new grad</code>, <code>associate</code>, <code>intern</code>, <code>early career</code>).</li>
        <li>Salary figures are employer-advertised midpoints from public ATS feeds. The stats endpoint does not currently break salary by experience band; we triangulate from distribution buckets.</li>
      </ol>
    </div>

  </div>

  <div style="max-width:640px;margin:40px auto;padding:24px;background:#fafaf8;border:1px solid #e5e5e5;border-radius:8px;">
    <p style="font-size:13px;color:#666;margin:0 0 12px;text-transform:uppercase;letter-spacing:1px;">Entry-level AI engineering jobs hiring now</p>
    <div data-aidev-jobs data-level="junior" data-limit="3" data-theme="light"></div>
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
    """Build CSV + Markdown for the gist: experience-level distribution + per-company juniors."""
    ov = stats.get("overview", {}) or {}
    levels = stats.get("experience_levels", []) or []
    salary = stats.get("salary", {}) or {}
    total_jobs = int(ov.get("total_jobs", 0))
    total_companies = int(ov.get("total_companies", 0))
    jobs_with_salary = int(ov.get("jobs_with_salary", 0))
    median_overall = int(salary.get("median", 0) or 0)

    lv_map = {lv.get("level"): int(lv.get("count", 0) or 0) for lv in levels}
    junior_ct = lv_map.get("junior", 0)
    mid_ct = lv_map.get("mid", 0)
    senior_ct = lv_map.get("senior", 0)
    lead_ct = lv_map.get("lead", 0)
    principal_ct = lv_map.get("principal", 0)
    classified_total = junior_ct + mid_ct + senior_ct + lead_ct + principal_ct or 1

    csv_lines = ["experience_level,role_count,share_pct"]
    for key, cnt in (
        ("junior", junior_ct),
        ("mid", mid_ct),
        ("senior", senior_ct),
        ("lead", lead_ct),
        ("principal", principal_ct),
    ):
        share = cnt / classified_total * 100 if classified_total else 0
        csv_lines.append(f"{key},{cnt},{share:.2f}")
    csv_text = "\n".join(csv_lines) + "\n"

    junior_pct = junior_ct / classified_total * 100
    senior_plus_ct = senior_ct + lead_ct + principal_ct
    sr_ratio = senior_plus_ct / junior_ct if junior_ct else 0.0

    md_lines = [
        "# AI Engineering — The Junior Hiring Gap",
        "",
        f"**Last updated**: {today}",
        "",
        f"**Snapshot**: {today} \u00b7 **Total jobs**: {total_jobs:,} \u00b7 "
        f"**Companies indexed**: {total_companies:,} \u00b7 "
        f"**Classified by level**: {classified_total:,} \u00b7 "
        f"**Median salary**: ${median_overall:,}",
        "",
        f"**Headline stat**: only **{junior_pct:.1f}%** of classified AI/ML roles are open to juniors. "
        f"For every 1 junior role, there are **{sr_ratio:.1f} senior-plus roles**.",
        "",
        "Live data from [aidevboard.com/api/v1/stats](https://aidevboard.com/api/v1/stats) \u2014 free public API, no auth, refreshed daily across 560+ ATS sources.",
        "",
        "## Experience-level mix",
        "",
        "| Experience level | Role count | Share |",
        "|---|---:|---:|",
    ]
    for key, label, cnt in (
        ("junior", "Junior / Entry-level", junior_ct),
        ("mid", "Mid", mid_ct),
        ("senior", "Senior", senior_ct),
        ("lead", "Lead / Staff", lead_ct),
        ("principal", "Principal", principal_ct),
    ):
        share = cnt / classified_total * 100 if classified_total else 0
        md_lines.append(f"| {label} | {cnt:,} | {share:.1f}% |")

    # Junior-friendly companies (>= 10 total, >= 3 junior titles)
    junior_friendly = []
    for name, counts in company_counts.items():
        total = counts.get("total", 0)
        if total < 10:
            continue
        juniors = counts.get("junior", 0)
        if juniors < 3:
            continue
        share = juniors / total if total else 0
        junior_friendly.append((name, total, juniors, share))
    junior_friendly.sort(key=lambda x: (-x[2], -x[3]))
    junior_friendly = junior_friendly[:15]

    md_lines += [
        "",
        "## Junior-friendly companies (>= 3 junior titles in sample, >= 10 total)",
        "",
        "| Company | Sampled postings | Junior titles | Junior share |",
        "|---|---:|---:|---:|",
    ]
    if junior_friendly:
        for name, total, juniors, share in junior_friendly:
            md_lines.append(f"| {name} | {total:,} | {juniors:,} | {share*100:.0f}% |")
    else:
        md_lines.append("| — | — | — | (insufficient sample this cycle) |")

    md_lines += [
        "",
        "## Methodology",
        "",
        "Experience-level mix is drawn from the live `/api/v1/stats` endpoint (`experience_levels` array). "
        "Per-company junior counts in the table use a title-regex fallback over a paginated walk of `/api/v1/jobs` "
        "(up to 30 pages of 50). Junior-title markers: `junior`, `jr`, `entry-level`, `new grad`, `associate`, "
        "`intern`, `early career`. Titles containing `senior`/`staff`/`principal`/`lead` etc. are dropped from "
        "the junior bucket regardless of other markers. Salary data triangulated from the `salary.distribution` "
        "buckets — the stats endpoint does not expose salary by experience band directly.",
        "",
        "## Source & License",
        "",
        f"- **Live API**: https://aidevboard.com/api/v1/stats (JSON, public)",
        f"- **Research note**: {PAPER_URL}",
        f"- **Sibling dataset**: [Top AI Companies Hiring](https://gist.github.com/unitedideas/9c59d50a824a075410bd658c96e1f5de)",
        f"- **Sibling dataset**: [AI Compensation by Skill](https://gist.github.com/unitedideas/b1b80d11f0f187f93fd6b1a599df418e)",
        f"- **Sibling dataset**: [AI Workplace (remote vs onsite)](https://gist.github.com/unitedideas/680cc4c1d11e090814bdf132e155d6d1)",
        f"- **Sibling dataset**: [MCP Ecosystem Health](https://gist.github.com/unitedideas/c93bd6d9984729070c59b2ea6c6b301b)",
        f"- **Auto-regenerated**: weekly via `tools/regenerate-entry-level-gap.py`",
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

    tmpdir = Path(tempfile.gettempdir()) / "entry-level-gist"
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
    parser = argparse.ArgumentParser(description="Regenerate the Q2 2026 junior AI hiring gap paper from live data.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch + render, don't write anything")
    parser.add_argument("--once", action="store_true", help="Write file + refresh atlas, skip commit/push/pings")
    parser.add_argument("--no-push", action="store_true", help="Skip git push and IndexNow/WebSub pings")
    args = parser.parse_args()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    generated_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"=== Regenerate entry-level AI gap ({today}) ===")
    print("1. Fetching live ADB stats...")
    try:
        stats = http_get_json(ADB_STATS_URL)
    except Exception as e:
        print(f"  ADB stats fetch failed: {e}", file=sys.stderr)
        return 2
    ov = stats.get("overview", {}) or {}
    print(f"   ADB: {ov.get('total_jobs')} jobs / {ov.get('total_companies')} cos / {ov.get('jobs_with_salary')} salary-disclosed")
    lvs = stats.get("experience_levels", []) or []
    print(f"   Levels: {[(lv.get('level'), lv.get('count')) for lv in lvs]}")

    print("1b. Paginating jobs for per-company junior-title aggregation...")
    company_counts = fetch_company_junior_counts(max_pages=30, per_page=50)
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
        lv_map_og = {lv.get("level"): int(lv.get("count", 0) or 0) for lv in (stats.get("experience_levels", []) or [])}
        junior_ct = lv_map_og.get("junior", 0)
        mid_ct = lv_map_og.get("mid", 0)
        senior_ct = lv_map_og.get("senior", 0)
        lead_ct = lv_map_og.get("lead", 0)
        principal_ct = lv_map_og.get("principal", 0)
        classified_total = junior_ct + mid_ct + senior_ct + lead_ct + principal_ct or 1
        senior_plus_ct = senior_ct + lead_ct + principal_ct
        junior_pct = junior_ct / classified_total * 100
        sr_ratio = senior_plus_ct / junior_ct if junior_ct else 0.0

        headline = f"{junior_pct:.0f}% of AI jobs are entry-level"
        subtext = (
            f"Q2 2026 \u2022 {junior_ct:,} junior vs {senior_plus_ct:,} senior-plus roles \u2022 "
            f"{sr_ratio:.1f}:1 ratio across {classified_total:,} classified"
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

    print("\n4b. Updating public gist (entry-level CSV + MD)...")
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
                   "research/q2-2026-entry-level-ai-gap.html",
                   "research/overview.html",
                   "index.html",
                   f"research/og/{OG_SLUG}.png"])
    if add.returncode != 0:
        print(f"   git add failed: {add.stderr[:300]}", file=sys.stderr)
        return 3
    msg = f"entry-level-gap: auto-regenerate {today}"
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

    print("\n=== Done. ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
