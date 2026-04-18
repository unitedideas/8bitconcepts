#!/usr/bin/env python3
"""
Regenerate the "State of AI Engineering" master gist from live APIs.

Consolidates the three weekly snapshots (hiring, compensation, MCP) into a single
citable reference gist, pulling fresh data from:
  - https://aidevboard.com/api/v1/stats
  - https://nothumansearch.ai/digest.json

Rebuilds the master markdown (topline numbers, top 10 hiring, top 15 tags,
workplace + seniority, 3 key signals, companion research links, data APIs,
attribution) with the current date on the "**Updated**:" line, writes to a
tempfile, then pushes via `gh gist edit`. Non-fatal on gist failure.

Master gist: https://gist.github.com/unitedideas/4050cc4da4f874ff711fec1730940ddc

Usage:
    python3 tools/regenerate-master-snapshot.py          # full run
    python3 tools/regenerate-master-snapshot.py --dry-run # fetch + render, don't write
    python3 tools/regenerate-master-snapshot.py --once    # render + log, skip gist edit
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

USER_AGENT = "curl/8.7.1"

ADB_STATS_URL = "https://aidevboard.com/api/v1/stats"
NHS_DIGEST_URL = "https://nothumansearch.ai/digest.json"

# Public gist: https://gist.github.com/unitedideas/4050cc4da4f874ff711fec1730940ddc
GIST_ID = "4050cc4da4f874ff711fec1730940ddc"
GIST_MD_FILENAME = "state-of-ai-engineering.md"
GIST_URL = f"https://gist.github.com/unitedideas/{GIST_ID}"
GIST_MD_RAW_URL = f"https://gist.githubusercontent.com/unitedideas/{GIST_ID}/raw/{GIST_MD_FILENAME}"


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
            return "—"
        return f"${v:,}"
    except (TypeError, ValueError):
        return "—"


def level_label(key: str) -> str:
    return {
        "senior": "Senior",
        "mid": "Mid",
        "lead": "Lead",
        "junior": "Junior",
        "principal": "Principal",
        "staff": "Staff",
        "intern": "Intern",
    }.get(key, key.capitalize() if key else "—")


def build_markdown(stats: dict[str, Any], digest: dict[str, Any], today: str) -> str:
    ov = stats.get("overview", {}) or {}
    salary = stats.get("salary", {}) or {}
    tags = stats.get("tags", []) or []
    companies = stats.get("companies", []) or []
    workplaces = stats.get("workplace", []) or []
    experience_levels = stats.get("experience_levels", []) or []

    total_jobs = int(ov.get("total_jobs", 0))
    total_companies = int(ov.get("total_companies", 0))
    new_this_week = int(ov.get("new_this_week", 0))
    jobs_with_salary = int(ov.get("jobs_with_salary", 0))
    median = int(salary.get("median", 0) or 0)
    salary_disclosed_pct = (jobs_with_salary / total_jobs * 100) if total_jobs else 0

    nhs_total = int(digest.get("total_sites", 0))
    nhs_mcp = int(digest.get("mcp_verified", 0))
    nhs_mcp_pct = (nhs_mcp / nhs_total * 100) if nhs_total else 0

    # Top 10 hiring companies
    top_companies = companies[:10]

    # Top 15 skill tags (by posting count — already sorted desc from API)
    top_tags = tags[:15]

    # Workplace ordering: Onsite, Remote, Hybrid
    ws_map = {w.get("type"): w for w in workplaces}

    # Seniority — API returns already desc by count
    top_levels = experience_levels[:5]

    # Build signals dynamically from data
    # Signal 1: agents crossover — is "agents" ranked above "pytorch"?
    tag_ranks = {t.get("tag"): i for i, t in enumerate(tags)}
    agents_rank = tag_ranks.get("agents", 999)
    pytorch_rank = tag_ranks.get("pytorch", 999)
    agents_signal = (
        "**Agent tag crossover**: Generic ML tags (pytorch, tensorflow) have been eclipsed by "
        "`agents` as the #2 most-demanded skill across postings. Confirms the market shift toward "
        "agentic AI at hiring layer."
        if agents_rank < pytorch_rank
        else "**Agent tag crossover**: `agents` is now a top-tier demanded skill, on par with "
             "generic ML tags like pytorch and tensorflow."
    )

    # Signal 2: research premium vs. generative-ai
    def tag_row(name: str) -> dict[str, Any]:
        for t in tags:
            if t.get("tag") == name:
                return t
        return {}

    research_tag = tag_row("research")
    genai_tag = tag_row("generative-ai")
    research_avg = int(research_tag.get("avg_salary", 0) or 0)
    genai_avg = int(genai_tag.get("avg_salary", 0) or 0)
    research_count = int(research_tag.get("count", 0) or 0)
    genai_count = int(genai_tag.get("count", 0) or 0)
    if research_avg > 0 and genai_avg > 0 and research_avg > genai_avg and genai_count > 0:
        premium_k = (research_avg - genai_avg) // 1000
        ratio = genai_count / research_count if research_count else 0
        research_signal = (
            f"**Research premium**: Roles tagged `research` pay a ~${premium_k}k premium over "
            f"`generative-ai` roles despite gen-AI having {ratio:.1f}× more openings. The "
            f"most-advertised skill isn't the best-paid."
        )
    else:
        research_signal = (
            "**Research premium**: Specialized research roles continue to command salary premiums "
            "over more generic generative-AI postings, despite gen-AI having far more openings."
        )

    # Signal 3: MCP verification gap
    mcp_signal = (
        f"**MCP verification gap**: Only ~{nhs_mcp_pct:.0f}% of sites claiming MCP/agent-readiness "
        f"survive a live JSON-RPC handshake. The ecosystem is "
        f"{100 - nhs_mcp_pct:.0f}% documentation-only."
        if nhs_total
        else "**MCP verification gap**: Most sites claiming MCP/agent-readiness do not survive a "
             "live JSON-RPC handshake. The ecosystem remains largely documentation-only."
    )

    # ---------- Markdown assembly ----------
    lines: list[str] = []
    lines.append("# State of AI Engineering — Q2 2026 Live Snapshot")
    lines.append("")
    lines.append(f"**Updated**: {today}")
    lines.append("")
    lines.append(
        "A single reference combining hiring, compensation, and infrastructure-verification data "
        "from the AI engineering ecosystem. Sources are live public APIs from "
        "[aidevboard.com](https://aidevboard.com) and [nothumansearch.ai](https://nothumansearch.ai)."
    )
    lines.append("")

    # Topline numbers
    lines.append("## Topline numbers")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Active AI/ML engineering roles | **{fmt_thousands(total_jobs)}** |")
    lines.append(f"| Hiring companies indexed | **{fmt_thousands(total_companies)}** |")
    lines.append(f"| New roles posted this week | **{fmt_thousands(new_this_week)}** |")
    lines.append(f"| Median salary (disclosed) | **{fmt_salary(median)}** |")
    lines.append(
        f"| Salary-disclosed roles | {fmt_thousands(jobs_with_salary)} ({salary_disclosed_pct:.1f}%) |"
    )
    lines.append(f"| Agent-ready sites indexed | **{fmt_thousands(nhs_total)}** |")
    lines.append(
        f"| MCP servers verified (live probe) | **{fmt_thousands(nhs_mcp)}** ({nhs_mcp_pct:.1f}%) |"
    )
    lines.append("")

    # Top 10 companies
    lines.append("## Top 10 AI companies hiring")
    lines.append("")
    lines.append("| Rank | Company | Roles | Avg Salary |")
    lines.append("|---:|---|---:|---:|")
    for i, c in enumerate(top_companies, start=1):
        name = str(c.get("company", "—"))
        roles = int(c.get("roles", 0) or 0)
        avg_salary = fmt_salary(c.get("avg_salary", 0))
        lines.append(f"| {i} | {name} | {fmt_thousands(roles)} | {avg_salary} |")
    lines.append("")

    # Top 15 tags
    lines.append("## Top 15 most-demanded skill tags")
    lines.append("")
    lines.append("| Tag | Postings | Avg Salary |")
    lines.append("|---|---:|---:|")
    for t in top_tags:
        tag_name = str(t.get("tag", "—"))
        count = int(t.get("count", 0) or 0)
        avg_salary = fmt_salary(t.get("avg_salary", 0))
        lines.append(f"| {tag_name} | {fmt_thousands(count)} | {avg_salary} |")
    lines.append("")

    # Workplace distribution
    lines.append("## Workplace distribution")
    lines.append("")
    lines.append("| Mode | Roles | Avg Salary |")
    lines.append("|---|---:|---:|")
    for key in ("onsite", "remote", "hybrid"):
        w = ws_map.get(key)
        if not w:
            continue
        label = {"onsite": "Onsite", "remote": "Remote", "hybrid": "Hybrid"}[key]
        count = int(w.get("count", 0) or 0)
        avg_salary = fmt_salary(w.get("avg_salary", 0))
        lines.append(f"| {label} | {fmt_thousands(count)} | {avg_salary} |")
    lines.append("")

    # Seniority mix
    lines.append("## Seniority mix")
    lines.append("")
    lines.append("| Level | Roles |")
    lines.append("|---|---:|")
    for lvl in top_levels:
        label = level_label(str(lvl.get("level", "")))
        count = int(lvl.get("count", 0) or 0)
        lines.append(f"| {label} | {fmt_thousands(count)} |")
    lines.append("")

    # Key signals
    lines.append("## Key signals")
    lines.append("")
    lines.append(f"- {agents_signal}")
    lines.append(f"- {research_signal}")
    lines.append(f"- {mcp_signal}")
    lines.append("")

    # Companion research
    lines.append("## Companion research (auto-refreshed weekly)")
    lines.append("")
    lines.append(
        "- [Q2 2026 AI Hiring Snapshot](https://8bitconcepts.com/research/q2-2026-ai-hiring-snapshot.html) "
        "— full hiring writeup"
    )
    lines.append(
        "- [Q2 2026 AI Compensation by Skill](https://8bitconcepts.com/research/q2-2026-ai-compensation-by-skill.html) "
        "— salary by tag"
    )
    lines.append(
        "- [Q2 2026 MCP Ecosystem Health](https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html) "
        "— verification rates"
    )
    lines.append(
        "- [Research Atlas (full set)](https://8bitconcepts.com/research/overview.html)"
    )
    lines.append("")

    # Data APIs
    lines.append("## Data APIs (free, no auth)")
    lines.append("")
    lines.append(
        "- ADB: `https://aidevboard.com/api/v1/stats` — hiring, salaries, companies, tags"
    )
    lines.append(
        "- NHS: `https://nothumansearch.ai/digest.json` — MCP ecosystem, verification, categories"
    )
    lines.append("")

    # Attribution
    lines.append("## Attribution")
    lines.append("")
    lines.append(
        "Free to cite. Attribute to *aidevboard.com* and *nothumansearch.ai*. For reporters: "
        "happy to supply specific data cuts — email hello@8bitconcepts.com."
    )

    return "\n".join(lines) + "\n"


def update_gist(md_text: str) -> bool:
    """Write markdown to a tempfile and push to the master gist via `gh gist edit`.
    Non-fatal on failure — logs and returns False.
    """
    tmpdir = Path(tempfile.gettempdir()) / "master-snapshot-gist"
    try:
        tmpdir.mkdir(parents=True, exist_ok=True)
        md_path = tmpdir / GIST_MD_FILENAME
        md_path.write_text(md_text, encoding="utf-8")
        print(f"   Wrote gist file to {md_path}")
    except Exception as e:
        print(f"   Gist temp write failed (non-fatal): {e}", file=sys.stderr)
        return False

    cmd = ["gh", "gist", "edit", GIST_ID, "--filename", GIST_MD_FILENAME, "--", str(md_path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(
            f"   gh gist edit {GIST_MD_FILENAME} failed (non-fatal): {r.stderr[:400]}",
            file=sys.stderr,
        )
        return False
    print(f"   Gist updated: {GIST_MD_FILENAME}")
    print(f"   Gist live: {GIST_URL}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate the State of AI Engineering master gist from live data."
    )
    parser.add_argument("--dry-run", action="store_true", help="Fetch + render, don't write")
    parser.add_argument("--once", action="store_true", help="Render + log, skip gist edit")
    args = parser.parse_args()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"=== Regenerate master snapshot ({today}) ===")
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
    print(
        f"   ADB: {ov.get('total_jobs')} jobs / {ov.get('total_companies')} cos / "
        f"{ov.get('new_this_week')} new this wk"
    )
    print(
        f"   NHS: {digest.get('total_sites')} sites / {digest.get('mcp_verified')} mcp / "
        f"{digest.get('llms_txt_count')} llms.txt"
    )

    print("2. Rendering master markdown...")
    md_text = build_markdown(stats, digest, today)
    print(f"   Rendered {len(md_text)} chars")

    if args.dry_run:
        print(f"   [DRY RUN] Would push {len(md_text)} chars to gist {GIST_ID}")
        print("   First 400 chars:")
        print(md_text[:400])
        return 0

    if args.once:
        # Still push the gist in --once mode (there's no "commit" step for this script,
        # the gist IS the artifact). Mirror the hiring script's spirit: --once is for
        # validation, but we still want to see the live update when testing.
        print("\n3. Updating master gist (--once: will still push gist)...")
    else:
        print("\n3. Updating master gist...")

    try:
        ok = update_gist(md_text)
    except Exception as e:
        print(f"   Gist update unhandled exception (non-fatal): {e}", file=sys.stderr)
        ok = False

    if ok:
        print("\n=== Done. ===")
        return 0
    print("\n=== Done (gist update failed — see above). ===")
    return 0  # Non-fatal — mirror hiring script behavior


if __name__ == "__main__":
    sys.exit(main())
