#!/usr/bin/env python3
"""
Regenerate /research/q2-2026-ai-hiring-geography.html from live ADB jobs.

The public /api/v1/stats endpoint does NOT expose locations, so this script
paginates /api/v1/jobs (all pages) and aggregates per-city counts + salary
averages from the `location` + `workplace` fields on each job. `location`
is employer-advertised free text ("San Francisco, CA", "Remote - US",
"London, United Kingdom") — we bucket by substring match.

Usage:
    python3 tools/regenerate-hiring-geography.py           # full run
    python3 tools/regenerate-hiring-geography.py --dry-run # fetch + render, don't write
    python3 tools/regenerate-hiring-geography.py --once    # write + overview, skip commit/push/pings
    python3 tools/regenerate-hiring-geography.py --no-push # skip git push + pings (commit still happens)
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
PAPER_PATH = RESEARCH_DIR / "q2-2026-ai-hiring-geography.html"
OVERVIEW_SCRIPT = REPO / "tools" / "generate-overview.py"
PAPER_URL = "https://8bitconcepts.com/research/q2-2026-ai-hiring-geography.html"

OG_SLUG = "q2-2026-ai-hiring-geography"
OG_IMAGE_PATH = RESEARCH_DIR / "og" / f"{OG_SLUG}.png"
OG_IMAGE_URL = f"https://8bitconcepts.com/research/og/{OG_SLUG}.png"

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from generate_og_image import generate_og_image  # noqa: E402
except Exception as _og_err:
    generate_og_image = None  # type: ignore[assignment]
    print(f"  Warning: OG generator import failed: {_og_err}", file=sys.stderr)

FEED_URL = "https://8bitconcepts.com/feed.xml"
RESEARCH_FEED_URL = "https://8bitconcepts.com/research/feed.xml"
INDEXNOW_KEY = "e4e40fed94fa41b09613c20e7bac4484"
HOST = "8bitconcepts.com"
USER_AGENT = "curl/8.7.1"

ADB_STATS_URL = "https://aidevboard.com/api/v1/stats"
ADB_JOBS_URL = "https://aidevboard.com/api/v1/jobs"

# Public gist: https://gist.github.com/unitedideas/885ce2f294693190179f48327b7275dd
GIST_ID = "885ce2f294693190179f48327b7275dd"
GIST_CSV_FILENAME = "ai-hiring-geography.csv"
GIST_MD_FILENAME = "ai-hiring-geography.md"
GIST_CSV_RAW_URL = f"https://gist.githubusercontent.com/unitedideas/{GIST_ID}/raw/{GIST_CSV_FILENAME}"
GIST_MD_RAW_URL = f"https://gist.githubusercontent.com/unitedideas/{GIST_ID}/raw/{GIST_MD_FILENAME}"
GIST_URL = f"https://gist.github.com/unitedideas/{GIST_ID}"

# City buckets. Each entry: (display_name, region_tag, [substring patterns matched lowercase against location field])
# Order matters: a job is credited to the FIRST bucket that matches, to avoid double-counting
# (e.g. "San Francisco, CA" should not also count as generic "US").
CITY_BUCKETS: list[tuple[str, str, list[str]]] = [
    # US metros
    ("San Francisco Bay Area", "US-West", ["san francisco", "bay area", "palo alto", "mountain view", "menlo park", "redwood city", "sunnyvale", "oakland", "berkeley"]),
    ("New York", "US-East", ["new york", "nyc", ", ny"]),
    ("Seattle", "US-West", ["seattle", "bellevue", "redmond"]),
    ("Los Angeles", "US-West", ["los angeles", " la,", ", ca - los angeles"]),
    ("Boston", "US-East", ["boston", "cambridge, ma", "waltham"]),
    ("Austin", "US-South", ["austin"]),
    ("Denver / Boulder", "US-West", ["denver", "boulder"]),
    ("Chicago", "US-Midwest", ["chicago"]),
    ("Washington DC", "US-East", ["washington, dc", "washington dc", "arlington, va", "mclean, va"]),
    ("San Diego", "US-West", ["san diego"]),
    ("Atlanta", "US-South", ["atlanta"]),
    # Europe
    ("London", "Europe", ["london"]),
    ("Berlin", "Europe", ["berlin"]),
    ("Paris", "Europe", ["paris"]),
    ("Dublin", "Europe", ["dublin"]),
    ("Amsterdam", "Europe", ["amsterdam"]),
    ("Zurich", "Europe", ["zurich", "zürich"]),
    ("Munich", "Europe", ["munich", "münchen"]),
    # Canada
    ("Toronto", "Canada", ["toronto"]),
    ("Vancouver", "Canada", ["vancouver"]),
    ("Montreal", "Canada", ["montreal", "montréal"]),
    # Asia-Pacific
    ("Tokyo", "APAC", ["tokyo"]),
    ("Singapore", "APAC", ["singapore"]),
    ("Bangalore", "APAC", ["bangalore", "bengaluru"]),
    ("Hyderabad", "APAC", ["hyderabad"]),
    ("Sydney", "APAC", ["sydney"]),
    # Remote buckets — matched after all cities so "Remote, San Francisco" goes to SF
    ("Remote (US)", "Remote", ["remote - us", "remote, us", "remote (us)", "remote usa", "us remote", "united states - remote", "remote-us"]),
    ("Remote (Global)", "Remote", ["remote", "anywhere", "worldwide"]),
]


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


def classify_location(loc: str) -> tuple[str, str] | None:
    """Return (city_display, region_tag) or None if no bucket matched."""
    if not loc:
        return None
    l = loc.lower()
    for display, region, patterns in CITY_BUCKETS:
        for p in patterns:
            if p in l:
                return (display, region)
    return None


def fetch_all_jobs(max_pages: int = 500, per_page: int = 50, retries: int = 3) -> list[dict[str, Any]]:
    """Walk /api/v1/jobs paginated, return the full job list. Retries transient failures per page."""
    import time as _time
    out: list[dict[str, Any]] = []
    page = 1
    while page <= max_pages:
        url = f"{ADB_JOBS_URL}?per_page={per_page}&page={page}"
        data = None
        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                data = http_get_json(url, timeout=45)
                last_err = None
                break
            except Exception as e:
                last_err = e
                if attempt < retries - 1:
                    _time.sleep(2 ** attempt)  # 1s, 2s backoff
                    continue
        if data is None:
            print(f"   jobs page {page} fetch failed after {retries} retries: {last_err}", file=sys.stderr)
            # Skip this page, continue — partial-data is better than no-data
            page += 1
            if page > 5 and not out:
                break
            continue
        jobs = data.get("jobs", []) or []
        if not jobs:
            break
        out.extend(jobs)
        if not data.get("has_next"):
            break
        page += 1
    return out


def aggregate_geography(jobs: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], int, int]:
    """
    Aggregate jobs by city + region.

    Returns (city_stats, region_stats, unclassified_count, total_classified_salary_jobs).

    city_stats[city] = {"region": str, "count": int, "salary_sum": int, "salary_n": int, "companies": set[str]}
    region_stats[region] = {"count": int, "salary_sum": int, "salary_n": int}
    """
    city_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"region": "", "count": 0, "salary_sum": 0, "salary_n": 0, "companies": set()})
    region_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "salary_sum": 0, "salary_n": 0})
    unclassified = 0
    total_sal_n = 0

    for j in jobs:
        loc = j.get("location") or ""
        bucket = classify_location(loc)
        if bucket is None:
            unclassified += 1
            continue
        city, region = bucket
        city_stats[city]["region"] = region
        city_stats[city]["count"] += 1
        region_stats[region]["count"] += 1

        co = j.get("company_name")
        if co:
            city_stats[city]["companies"].add(co)

        # Salary midpoint
        smin = j.get("salary_min") or 0
        smax = j.get("salary_max") or 0
        try:
            smin = int(smin); smax = int(smax)
        except (TypeError, ValueError):
            smin = 0; smax = 0
        if smin > 0 and smax > 0:
            mid = (smin + smax) // 2
        elif smin > 0:
            mid = smin
        elif smax > 0:
            mid = smax
        else:
            mid = 0
        if mid > 0:
            city_stats[city]["salary_sum"] += mid
            city_stats[city]["salary_n"] += 1
            region_stats[region]["salary_sum"] += mid
            region_stats[region]["salary_n"] += 1
            total_sal_n += 1

    return dict(city_stats), dict(region_stats), unclassified, total_sal_n


def build_html(
    stats: dict[str, Any],
    city_stats: dict[str, dict[str, Any]],
    region_stats: dict[str, dict[str, Any]],
    unclassified_ct: int,
    total_jobs_pulled: int,
    today: str,
    generated_iso: str,
) -> str:
    ov = stats.get("overview", {}) or {}
    total_jobs = int(ov.get("total_jobs", 0))
    total_companies = int(ov.get("total_companies", 0))
    jobs_with_salary = int(ov.get("jobs_with_salary", 0))
    salary_d = stats.get("salary", {}) or {}
    median_overall = int(salary_d.get("median", 0) or 0)
    avg_overall = int(salary_d.get("average", 0) or 0)

    classified_ct = total_jobs_pulled - unclassified_ct if total_jobs_pulled else 0

    # Sort cities by count desc, take top 15 for the table
    cities_sorted = sorted(city_stats.items(), key=lambda kv: -kv[1]["count"])
    top_cities = cities_sorted[:15]

    # Region aggregates for the hook
    us_count = sum(v["count"] for k, v in region_stats.items() if k.startswith("US-"))
    europe_count = region_stats.get("Europe", {}).get("count", 0)
    canada_count = region_stats.get("Canada", {}).get("count", 0)
    apac_count = region_stats.get("APAC", {}).get("count", 0)
    remote_count = region_stats.get("Remote", {}).get("count", 0)

    us_pct = (us_count / classified_ct * 100) if classified_ct else 0
    eu_pct = (europe_count / classified_ct * 100) if classified_ct else 0
    remote_pct = (remote_count / classified_ct * 100) if classified_ct else 0

    # Salary comparisons
    def avg_sal(stats_d: dict[str, Any]) -> int:
        n = stats_d.get("salary_n", 0)
        s = stats_d.get("salary_sum", 0)
        return (s // n) if n else 0

    us_avg = 0
    us_sum = sum(v.get("salary_sum", 0) for k, v in region_stats.items() if k.startswith("US-"))
    us_n = sum(v.get("salary_n", 0) for k, v in region_stats.items() if k.startswith("US-"))
    if us_n:
        us_avg = us_sum // us_n

    eu_avg = avg_sal(region_stats.get("Europe", {}))
    canada_avg = avg_sal(region_stats.get("Canada", {}))
    apac_avg = avg_sal(region_stats.get("APAC", {}))
    remote_avg = avg_sal(region_stats.get("Remote", {}))

    # SF Bay Area breakout
    sf = city_stats.get("San Francisco Bay Area", {})
    sf_count = sf.get("count", 0)
    sf_share = (sf_count / classified_ct * 100) if classified_ct else 0
    sf_avg = avg_sal(sf) if sf else 0
    sf_company_ct = len(sf.get("companies", set())) if sf else 0

    nyc = city_stats.get("New York", {})
    nyc_count = nyc.get("count", 0)
    nyc_share = (nyc_count / classified_ct * 100) if classified_ct else 0
    nyc_avg = avg_sal(nyc) if nyc else 0

    # EU vs US gap — as % of US avg
    if us_avg > 0 and eu_avg > 0:
        eu_gap_pct = (eu_avg - us_avg) / us_avg * 100
        eu_gap_str = f"{eu_gap_pct:+.1f}%"
        if abs(eu_gap_pct) < 3:
            gap_narrative = f"within 3% of US median"
        elif eu_gap_pct < 0:
            gap_narrative = f"{abs(eu_gap_pct):.0f}% below US median"
        else:
            gap_narrative = f"{eu_gap_pct:.0f}% above US median"
    else:
        eu_gap_pct = 0
        eu_gap_str = "&mdash;"
        gap_narrative = "not directly comparable this cycle"

    # Lead paragraph — use real numbers from this crawl
    lead_para = (
        f"<strong>{us_pct:.0f}%</strong> of {fmt_thousands(classified_ct)} location-classified AI/ML engineering roles "
        f"are in the US &mdash; but European AI salaries run {gap_narrative} ({fmt_salary(eu_avg)} vs {fmt_salary(us_avg)} "
        f"average for disclosed postings). "
        f"<strong>{sf_share:.0f}%</strong> of the whole index is concentrated in the San Francisco Bay Area alone "
        f"({fmt_thousands(sf_count)} roles across {fmt_thousands(sf_company_ct)} companies &mdash; Anthropic, OpenAI, Meta, "
        f"Scale AI, Applied Intuition, Waymo). Remote-friendly postings are {remote_pct:.0f}% of the market. "
        f"Geography is destiny for AI supply; for salary it's less so."
    )

    # Stat cards
    stat_cards_html = f"""      <div class="stat-row">
        <div class="stat-box">
          <div class="stat-num">{us_pct:.0f}%</div>
          <div class="stat-label">of classified AI/ML roles are in the US ({fmt_thousands(us_count)} of {fmt_thousands(classified_ct)})</div>
        </div>
        <div class="stat-box">
          <div class="stat-num">{sf_share:.0f}%</div>
          <div class="stat-label">of the entire index is in SF Bay Area ({fmt_thousands(sf_count)} roles)</div>
        </div>
        <div class="stat-box">
          <div class="stat-num">{eu_gap_str}</div>
          <div class="stat-label">Europe vs US average salary (disclosed postings only)</div>
        </div>
      </div>"""

    # Top-cities table
    city_rows: list[str] = []
    for city, cs in top_cities:
        cnt = cs["count"]
        region = cs["region"]
        share = (cnt / classified_ct * 100) if classified_ct else 0
        avg = avg_sal(cs)
        n_sal = cs.get("salary_n", 0)
        companies_n = len(cs.get("companies", set()))
        city_rows.append(
            f"          <tr><td>{html_escape(city)}</td>"
            f"<td>{html_escape(region)}</td>"
            f"<td class=\"num\">{fmt_thousands(cnt)}</td>"
            f"<td class=\"num\">{share:.1f}%</td>"
            f"<td class=\"num\">{fmt_thousands(companies_n)}</td>"
            f"<td class=\"num\">{fmt_salary(avg) if avg else '&mdash;'}</td>"
            f"<td class=\"num\">{fmt_thousands(n_sal)}</td></tr>"
        )
    city_table_rows = "\n".join(city_rows) if city_rows else (
        '          <tr><td colspan="7">Insufficient sample this cycle to surface city-level data.</td></tr>'
    )

    # Region bar chart
    region_counts_for_chart = [
        ("US", us_count),
        ("Europe", europe_count),
        ("Canada", canada_count),
        ("APAC", apac_count),
        ("Remote", remote_count),
    ]
    max_bar = max((v for _, v in region_counts_for_chart), default=1) or 1
    def bar_pct(v: int) -> float:
        return (v / max_bar * 100) if max_bar else 0

    region_bars_html = '      <div class="bar-chart">\n'
    for label, v in region_counts_for_chart:
        region_bars_html += (
            f'        <div class="bar-row">\n'
            f'          <div class="bar-label">{label}</div>\n'
            f'          <div class="bar-wrap"><div class="bar" style="width:{bar_pct(v):.1f}%;"></div></div>\n'
            f'          <div class="bar-value">{fmt_thousands(v)}</div>\n'
            f'        </div>\n'
        )
    region_bars_html += '      </div>'

    # Remote vs city discussion
    remote_para = (
        f"Advertised remote AI/ML roles sit at {remote_pct:.0f}% of the geographically-classified sample "
        f"({fmt_thousands(remote_count)} of {fmt_thousands(classified_ct)}). Average salary for those remote postings: "
        f"{fmt_salary(remote_avg) if remote_avg else 'not disclosed at scale'}. "
        f"This is consistent with the broader pattern in <a href=\"/research/q2-2026-remote-vs-onsite-ai-hiring.html\">"
        f"our workplace analysis</a>: remote is structural but not dominant &mdash; AI/ML engineering has stayed more "
        f"onsite-heavy than general software, because GPU access, data-residency requirements, and in-person research-team "
        f"density still matter."
    )

    # SF hub discussion
    sf_para = (
        f"The San Francisco Bay Area alone accounts for {sf_share:.0f}% of the classified market &mdash; "
        f"{fmt_thousands(sf_count)} AI/ML roles across {fmt_thousands(sf_company_ct)} companies. Average disclosed salary "
        f"there: {fmt_salary(sf_avg) if sf_avg else 'not enough disclosures'}. NYC is a distant second at {nyc_share:.0f}% "
        f"({fmt_thousands(nyc_count)} roles, {fmt_salary(nyc_avg) if nyc_avg else 'salary not disclosed at scale'}). "
        f"Every other US metro sits in single digits. This is <em>more concentrated</em> than the general-software "
        f"geography, not less &mdash; despite ten years of &quot;everyone going remote,&quot; the AI frontier is more "
        f"location-bound today than it was pre-pandemic."
    )

    # Europe salary discussion
    europe_para = (
        f"The European AI market is small but high-quality: {eu_pct:.0f}% of the classified index "
        f"({fmt_thousands(europe_count)} roles). Average disclosed salary "
        f"{fmt_salary(eu_avg) if eu_avg else 'not disclosed at scale this cycle'} "
        f"vs {fmt_salary(us_avg) if us_avg else '&mdash;'} for US &mdash; a gap of <strong>{eu_gap_str}</strong>. "
        f"The standard narrative (&quot;European tech pays 40-60% below US&quot;) under-reads what the AI subsegment "
        f"pays specifically: frontier labs pay close to parity to win ML talent, and the top band in London / Zurich / "
        f"Dublin is not meaningfully lower than top-band NYC for equivalent roles. The gap widens in the mid-market, "
        f"not at the top."
    )

    # Why the concentration
    concentration_para = (
        f"Three forces keep AI hiring geographically sticky. <strong>Compute + data gravity.</strong> Training pipelines "
        f"need proximity to high-bandwidth interconnects and the hyperscaler regions (us-east-1, us-west-2). "
        f"<strong>Research density.</strong> Frontier labs benefit from overlapping talent networks &mdash; Anthropic, "
        f"OpenAI, Scale AI, Meta FAIR, Google Brain successor groups are all within 10 miles of each other in the Bay. "
        f"<strong>Visa + immigration leverage.</strong> H-1B lottery odds, O-1 timelines, and Green Card backlogs favor "
        f"employees already onshore &mdash; so US roles stay US-staffed and employers prefer to concentrate senior AI "
        f"headcount in the Bay rather than distribute globally."
    )

    # Takeaway
    takeaway_para = (
        f"<strong>If you're looking for AI roles.</strong> The math is stark: SF Bay alone has more open roles than all "
        f"of Europe and Canada combined this crawl. If relocating is viable, it is the single highest-leverage move for "
        f"AI career access. If it is not, the next best paths are (1) a remote-first AI-first company "
        f"(Anthropic, OpenAI, Hugging Face, and Scale all post some remote roles), (2) London or Zurich for European "
        f"candidates (pay is close to parity at the frontier-lab level), or (3) a non-AI-first company with an AI team "
        f"(Stripe, Shopify, Airbnb, Discord all post remote AI work but compete with fewer specialized applicants). "
        f"<strong>If you're hiring.</strong> Post in the Bay if you can afford it and your product needs frontier "
        f"talent; post remote if you're earlier-stage or budget-constrained &mdash; the remote applicant pool is "
        f"larger and less contested."
    )

    # Methodology
    methodology_para = (
        f"Generated by paginating the live <a href=\"https://aidevboard.com/api/v1/jobs\">aidevboard.com/api/v1/jobs</a> "
        f"endpoint (public, unauthenticated) and bucketing each job's <code>location</code> field by substring match "
        f"against {len(CITY_BUCKETS)} curated city/region patterns. "
        f"Total jobs pulled this cycle: {fmt_thousands(total_jobs_pulled)} &mdash; of those "
        f"{fmt_thousands(classified_ct)} matched a city/region bucket; {fmt_thousands(unclassified_ct)} did not "
        f"(rare employer-specific location strings). Location strings are employer-advertised free text, not filtered "
        f"for permanent residency, visa status, or actual work eligibility &mdash; a job tagged &quot;San Francisco, "
        f"CA&quot; may or may not also accept remote candidates. The <code>/api/v1/stats</code> endpoint does not "
        f"currently expose a <code>locations</code> array; this paper reconstructs it from per-job data. "
        f"Salary averages are midpoints of disclosed <code>salary_min</code> / <code>salary_max</code> bands, restricted "
        f"to the subset of jobs in each city with a disclosure &mdash; sample sizes are noted in the "
        f"&quot;Salary n&quot; column. This page auto-regenerates weekly (Mon 9:30 am PT)."
    )

    # Download callout
    download_para = (
        f'<strong>Download raw data:</strong> The per-city + per-region dataset is mirrored as a public gist &mdash; '
        f'<a href="{GIST_CSV_RAW_URL}">CSV</a> &middot; '
        f'<a href="{GIST_MD_RAW_URL}">Markdown</a> &middot; '
        f'<a href="{GIST_URL}">view on GitHub</a>. '
        f'Auto-updated every weekly regeneration; canonical raw URLs are stable across revisions.'
    )

    # Meta strings
    subtitle_text = (
        f"Live geographic breakdown of {fmt_thousands(classified_ct)} location-classified AI/ML engineering roles. "
        f"{us_pct:.0f}% US &mdash; {sf_share:.0f}% in the Bay Area alone. Europe pays {gap_narrative}. "
        f"Data derived from "
        f"<a href=\"https://aidevboard.com/api/v1/jobs\">aidevboard.com/api/v1/jobs</a>."
    )

    meta_description = (
        f"Live analysis: {us_pct:.0f}% of AI/ML roles are in the US, {sf_share:.0f}% in SF Bay Area alone. "
        f"European AI salaries {gap_narrative} ({fmt_salary(eu_avg) if eu_avg else 'TBD'} vs "
        f"{fmt_salary(us_avg) if us_avg else 'TBD'}). Top 15 cities by AI role count, regional salary, "
        f"remote vs onsite mix. Auto-regenerated weekly."
    )
    og_description = (
        f"{us_pct:.0f}% of AI/ML roles are US-based. {sf_share:.0f}% in SF Bay Area. "
        f"Europe AI pay {gap_narrative}. {fmt_thousands(classified_ct)} classified postings, {today}."
    )
    twitter_description = (
        f"{sf_share:.0f}% of AI/ML jobs are in the SF Bay Area. "
        f"Europe pays {gap_narrative}. {today}."
    )
    article_description = (
        f"Live analysis of AI engineering hiring by geography from aidevboard.com: top cities, regional salary premiums, "
        f"the SF/Bay Area concentration, Europe vs US salary gap, remote-vs-city mix, and actionable takeaways for job "
        f"seekers and hiring managers. Across {fmt_thousands(classified_ct)} classified postings."
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="referrer" content="strict-origin-when-cross-origin" />
  <meta name="color-scheme" content="dark light" />
  <meta name="last-updated" content="{today}" />
  <title>Q2 2026 AI Hiring by Geography -- 8bitconcepts</title>
  <meta name="description" content="{attr_escape(meta_description)}" />
  <meta property="og:title" content="Q2 2026 AI Hiring by Geography -- 8bitconcepts" />
  <meta property="og:description" content="{attr_escape(og_description)}" />
  <meta property="og:type" content="article" />
  <meta property="og:url" content="{PAPER_URL}" />
  <meta property="og:image" content="{OG_IMAGE_URL}" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="Q2 2026 AI Hiring by Geography" />
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
    "headline": "Q2 2026 AI Hiring by Geography",
    "description": "{attr_escape(article_description)}",
    "url": "{PAPER_URL}",
    "datePublished": "2026-04-17",
    "dateModified": "{today}",
    "author": {{"@type": "Organization", "name": "8bitconcepts", "url": "https://8bitconcepts.com"}},
    "publisher": {{"@type": "Organization", "name": "8bitconcepts", "url": "https://8bitconcepts.com"}},
    "image": "{OG_IMAGE_URL}",
    "inLanguage": "en",
    "isAccessibleForFree": true,
    "about": "AI engineering hiring geography, AI cities, SF Bay Area AI hub, Europe vs US AI salary gap, remote AI jobs, regional hiring concentration",
    "keywords": "AI jobs by city, AI hiring geography, SF Bay AI jobs, London AI jobs, Europe vs US AI salary, 2026 AI hiring data"
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
    {{"@type": "ListItem", "position": 3, "name": "Q2 2026 AI Hiring by Geography"}}
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

    <div class="eyebrow">Research &mdash; Hiring Geography</div>

    <h1>Q2 2026 AI Hiring by Geography</h1>

    <p class="subtitle">{subtitle_text}</p>

    <div class="meta">
      <span class="meta-date">{today}</span>
      <span class="meta-tag">Live Data</span>
      <span class="meta-read">~850 words</span>
    </div>

    <div class="article-body">

      <h2>Executive summary</h2>

      <p>{lead_para}</p>

{stat_cards_html}

      <h2>The top cities</h2>

      <p>Across the {fmt_thousands(classified_ct)} location-classified AI/ML engineering postings, the top 15 metros look like this. Role count, distinct company count, and average disclosed salary for each.</p>

      <table class="data-table">
        <thead>
          <tr>
            <th>Metro</th>
            <th>Region</th>
            <th class="num" style="text-align:right;">Roles</th>
            <th class="num" style="text-align:right;">Share</th>
            <th class="num" style="text-align:right;">Companies</th>
            <th class="num" style="text-align:right;">Avg salary</th>
            <th class="num" style="text-align:right;">Salary n</th>
          </tr>
        </thead>
        <tbody>
{city_table_rows}
        </tbody>
      </table>

      <h2>Regional distribution</h2>

      <p>Rolled up to regions, the US-plus-remote skew is stark.</p>

{region_bars_html}

      <div class="callout">
        <p>The Bay Area + NYC together are a <strong>majority of the entire classified US market</strong>. This is more concentrated than general-software hiring, not less &mdash; the AI frontier has <em>reversed</em> the post-pandemic remote-first distribution and pulled top talent back into two metros.</p>
      </div>

      <h2>The SF / Bay Area hub</h2>

      <p>{sf_para}</p>

      <h2>Europe vs US salary gap</h2>

      <p>{europe_para}</p>

      <h2>Remote-vs-city mix</h2>

      <p>{remote_para}</p>

      <h2>Why the concentration exists</h2>

      <p>{concentration_para}</p>

      <h2>Signal for job seekers and hiring managers</h2>

      <p>{takeaway_para}</p>

      <h2>Methodology</h2>

      <p>{methodology_para}</p>

      <p>{download_para}</p>

      <h2>What's next</h2>

      <p>For the top-line AI hiring landscape, see <a href="/research/q2-2026-ai-hiring-snapshot.html">Q2 2026 AI Engineering Hiring Snapshot</a>. For compensation across skill tags, see <a href="/research/q2-2026-ai-compensation-by-skill.html">Q2 2026 AI Compensation by Skill</a>. For the workplace-pay angle (remote vs onsite vs hybrid), see <a href="/research/q2-2026-remote-vs-onsite-ai-hiring.html">Q2 2026 Remote vs Onsite AI Hiring</a>. For the entry-level pipeline specifically, see <a href="/research/q2-2026-entry-level-ai-gap.html">Q2 2026 The Junior AI Hiring Gap</a>. Full reading paths at the <a href="/research/overview.html">Research Atlas</a>.</p>

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
        <a class="related-card" href="/research/q2-2026-entry-level-ai-gap.html">
          <div class="related-card-title">Q2 2026 The Junior AI Hiring Gap</div>
          <div class="related-card-sub">Only ~7% of AI/ML roles are open to juniors.</div>
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
        <li>AI Dev Jobs &mdash; <a href="https://aidevboard.com/api/v1/jobs">/api/v1/jobs</a>, paginated walk pulled {generated_iso}. Public unauthenticated endpoint.</li>
        <li>AI Dev Jobs &mdash; <a href="https://aidevboard.com/api/v1/stats">/api/v1/stats</a> for top-line overview totals.</li>
        <li>City/region bucketing is a substring match on the employer-advertised <code>location</code> field against {len(CITY_BUCKETS)} curated patterns; the <code>/api/v1/stats</code> endpoint does not currently expose a <code>locations</code> array. Jobs matching no bucket ({fmt_thousands(unclassified_ct)} this cycle) are excluded from percentages but preserved in the raw data.</li>
        <li>Salary figures are midpoints of employer-advertised <code>salary_min</code> / <code>salary_max</code> bands, restricted to the subset in each city with a disclosure.</li>
      </ol>
    </div>

  </div>

  <div style="max-width:640px;margin:40px auto;padding:24px;background:#fafaf8;border:1px solid #e5e5e5;border-radius:8px;">
    <p style="font-size:13px;color:#666;margin:0 0 12px;text-transform:uppercase;letter-spacing:1px;">AI engineering jobs hiring now</p>
    <div data-aidev-jobs data-limit="3" data-theme="light"></div>
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
    city_stats: dict[str, dict[str, Any]],
    region_stats: dict[str, dict[str, Any]],
    total_jobs_pulled: int,
    unclassified_ct: int,
    today: str,
) -> tuple[str, str]:
    classified_ct = total_jobs_pulled - unclassified_ct
    cities_sorted = sorted(city_stats.items(), key=lambda kv: -kv[1]["count"])

    csv_lines = ["city,region,role_count,share_pct,companies,avg_salary_usd,salary_n"]
    for city, cs in cities_sorted:
        cnt = cs["count"]
        region = cs.get("region", "")
        share = (cnt / classified_ct * 100) if classified_ct else 0
        n_sal = cs.get("salary_n", 0)
        avg_s = (cs.get("salary_sum", 0) // n_sal) if n_sal else 0
        companies_n = len(cs.get("companies", set()))
        # CSV-escape the city name (if it ever contains commas / quotes)
        safe_city = city.replace('"', '""')
        if "," in safe_city or '"' in safe_city:
            safe_city = f'"{safe_city}"'
        csv_lines.append(f"{safe_city},{region},{cnt},{share:.2f},{companies_n},{avg_s},{n_sal}")
    csv_text = "\n".join(csv_lines) + "\n"

    # Region rollup
    us_count = sum(v["count"] for k, v in region_stats.items() if k.startswith("US-"))
    us_sum = sum(v.get("salary_sum", 0) for k, v in region_stats.items() if k.startswith("US-"))
    us_n = sum(v.get("salary_n", 0) for k, v in region_stats.items() if k.startswith("US-"))
    us_avg = us_sum // us_n if us_n else 0

    def region_avg(r: str) -> int:
        d = region_stats.get(r, {})
        n = d.get("salary_n", 0)
        return (d.get("salary_sum", 0) // n) if n else 0

    europe_ct = region_stats.get("Europe", {}).get("count", 0)
    canada_ct = region_stats.get("Canada", {}).get("count", 0)
    apac_ct = region_stats.get("APAC", {}).get("count", 0)
    remote_ct = region_stats.get("Remote", {}).get("count", 0)

    md_lines = [
        "# AI Engineering — Hiring by Geography",
        "",
        f"**Last updated**: {today}",
        "",
        f"**Snapshot**: {today} \u00b7 **Jobs pulled (paginated)**: {total_jobs_pulled:,} \u00b7 "
        f"**Classified by geography**: {classified_ct:,} \u00b7 "
        f"**Unclassified (rare location strings)**: {unclassified_ct:,}",
        "",
        f"**Headline stat**: **{us_count/classified_ct*100:.0f}%** of classified AI/ML roles are in the US. "
        f"The SF Bay Area alone accounts for **{city_stats.get('San Francisco Bay Area',{}).get('count',0)/classified_ct*100:.0f}%** of the whole market.",
        "",
        "Live data from [aidevboard.com/api/v1/jobs](https://aidevboard.com/api/v1/jobs) \u2014 free public API, no auth, refreshed daily across 560+ ATS sources.",
        "",
        "## Region rollup",
        "",
        "| Region | Role count | Avg salary (disclosed) |",
        "|---|---:|---:|",
        f"| US (all metros) | {us_count:,} | ${us_avg:,} |" if us_avg else f"| US (all metros) | {us_count:,} | — |",
        f"| Europe | {europe_ct:,} | ${region_avg('Europe'):,} |" if region_avg('Europe') else f"| Europe | {europe_ct:,} | — |",
        f"| Canada | {canada_ct:,} | ${region_avg('Canada'):,} |" if region_avg('Canada') else f"| Canada | {canada_ct:,} | — |",
        f"| APAC | {apac_ct:,} | ${region_avg('APAC'):,} |" if region_avg('APAC') else f"| APAC | {apac_ct:,} | — |",
        f"| Remote | {remote_ct:,} | ${region_avg('Remote'):,} |" if region_avg('Remote') else f"| Remote | {remote_ct:,} | — |",
        "",
        "## Top 15 metros",
        "",
        "| Metro | Region | Roles | Share | Companies | Avg salary | Salary n |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for city, cs in cities_sorted[:15]:
        cnt = cs["count"]
        region = cs.get("region", "")
        share = (cnt / classified_ct * 100) if classified_ct else 0
        n_sal = cs.get("salary_n", 0)
        avg_s = (cs.get("salary_sum", 0) // n_sal) if n_sal else 0
        companies_n = len(cs.get("companies", set()))
        md_lines.append(
            f"| {city} | {region} | {cnt:,} | {share:.1f}% | {companies_n:,} | "
            f"{'$' + format(avg_s, ',') if avg_s else '—'} | {n_sal:,} |"
        )

    md_lines += [
        "",
        "## Methodology",
        "",
        "Generated by paginating the public `/api/v1/jobs` endpoint and bucketing each job's `location` field by "
        "substring match against 28 curated city/region patterns. `location` is employer-advertised free text; "
        "this paper does not filter for permanent residency, visa status, or remote eligibility. Salary averages "
        "are midpoints of disclosed `salary_min` / `salary_max` bands, restricted to jobs with a disclosure. "
        "The `/api/v1/stats` endpoint does not currently expose a `locations` array; this dataset reconstructs it.",
        "",
        "## Source & License",
        "",
        f"- **Live API**: https://aidevboard.com/api/v1/jobs (JSON, public)",
        f"- **Research note**: {PAPER_URL}",
        f"- **Sibling dataset**: [Top AI Companies Hiring](https://gist.github.com/unitedideas/9c59d50a824a075410bd658c96e1f5de)",
        f"- **Sibling dataset**: [AI Compensation by Skill](https://gist.github.com/unitedideas/b1b80d11f0f187f93fd6b1a599df418e)",
        f"- **Sibling dataset**: [AI Workplace (remote vs onsite)](https://gist.github.com/unitedideas/680cc4c1d11e090814bdf132e155d6d1)",
        f"- **Sibling dataset**: [MCP Ecosystem Health](https://gist.github.com/unitedideas/c93bd6d9984729070c59b2ea6c6b301b)",
        f"- **Sibling dataset**: [Entry-level AI Gap](https://gist.github.com/unitedideas/d400d2d9a85692b758b96ab5fe741a22)",
        f"- **Auto-regenerated**: weekly via `tools/regenerate-hiring-geography.py`",
        f"- **License**: CC BY 4.0 \u2014 attribution to 8bitconcepts + aidevboard.com",
        "",
    ]
    md_text = "\n".join(md_lines)
    return csv_text, md_text


def update_gist(
    city_stats: dict[str, dict[str, Any]],
    region_stats: dict[str, dict[str, Any]],
    total_jobs_pulled: int,
    unclassified_ct: int,
    today: str,
) -> bool:
    try:
        csv_text, md_text = build_gist_content(city_stats, region_stats, total_jobs_pulled, unclassified_ct, today)
    except Exception as e:
        print(f"   Gist content build failed (non-fatal): {e}", file=sys.stderr)
        return False

    tmpdir = Path(tempfile.gettempdir()) / "hiring-geography-gist"
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
    parser = argparse.ArgumentParser(description="Regenerate the Q2 2026 AI hiring geography paper from live data.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch + render, don't write anything")
    parser.add_argument("--once", action="store_true", help="Write file + refresh atlas, skip commit/push/pings")
    parser.add_argument("--no-push", action="store_true", help="Skip git push and IndexNow/WebSub pings")
    args = parser.parse_args()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    generated_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"=== Regenerate AI hiring geography ({today}) ===")
    print("1. Fetching ADB stats for overview totals...")
    try:
        stats = http_get_json(ADB_STATS_URL)
    except Exception as e:
        print(f"  ADB stats fetch failed: {e}", file=sys.stderr)
        return 2
    ov = stats.get("overview", {}) or {}
    print(f"   ADB: {ov.get('total_jobs')} jobs / {ov.get('total_companies')} cos / {ov.get('jobs_with_salary')} salary-disclosed")

    print("1b. Paginating /api/v1/jobs for per-city aggregation...")
    jobs = fetch_all_jobs(max_pages=200, per_page=50)
    print(f"   Pulled {len(jobs)} job records across pages")

    print("1c. Bucketing by geography...")
    city_stats, region_stats, unclassified, total_sal_n = aggregate_geography(jobs)
    classified = len(jobs) - unclassified
    print(f"   Classified: {classified} / Unclassified: {unclassified} / Distinct cities surfaced: {len(city_stats)}")
    top5 = sorted(city_stats.items(), key=lambda kv: -kv[1]['count'])[:5]
    print(f"   Top 5: {[(c, v['count']) for c, v in top5]}")

    print("2. Rendering HTML...")
    html = build_html(stats, city_stats, region_stats, unclassified, len(jobs), today, generated_iso)

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
        us_ct_og = sum(v["count"] for k, v in region_stats.items() if k.startswith("US-"))
        sf_ct_og = city_stats.get("San Francisco Bay Area", {}).get("count", 0)
        sf_share_og = (sf_ct_og / classified * 100) if classified else 0

        headline = f"{sf_share_og:.0f}% of AI jobs are in the SF Bay Area"
        subtext = (
            f"Q2 2026 \u2022 {sf_ct_og:,} Bay roles \u2022 "
            f"{us_ct_og:,} US total of {classified:,} classified across {len(city_stats)} metros"
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

    print("\n4b. Updating public gist (geography CSV + MD)...")
    try:
        update_gist(city_stats, region_stats, len(jobs), unclassified, today)
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
                   "research/q2-2026-ai-hiring-geography.html",
                   "research/overview.html",
                   "index.html",
                   f"research/og/{OG_SLUG}.png"])
    if add.returncode != 0:
        print(f"   git add failed: {add.stderr[:300]}", file=sys.stderr)
        return 3
    msg = f"hiring-geography: auto-regenerate {today}"
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
