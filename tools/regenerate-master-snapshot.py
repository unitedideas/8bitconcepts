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
tempfile, then pushes via `gh gist edit` and verifies the stored content.
Invalid source data and publication failures return a nonzero exit status.

Master gist: https://gist.github.com/unitedideas/4050cc4da4f874ff711fec1730940ddc

Usage:
    python3 tools/regenerate-master-snapshot.py          # full run
    python3 tools/regenerate-master-snapshot.py --dry-run # fetch + render, don't write
    python3 tools/regenerate-master-snapshot.py --once    # one run, including publication
"""
from __future__ import annotations

import argparse
import json
import math
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
GIST_DESCRIPTION = "State of AI Engineering: AI Dev Board and Not Human Search catalog snapshot"
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
            return "Not reported"
        return f"${v:,}"
    except (TypeError, ValueError):
        return "Not reported"


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


def validate_sources(stats: dict[str, Any], digest: dict[str, Any]) -> None:
    if not isinstance(stats, dict) or not isinstance(digest, dict):
        raise ValueError("Source responses must be JSON objects")
    overview = stats.get("overview")
    salary = stats.get("salary")
    if not isinstance(overview, dict) or not isinstance(salary, dict):
        raise ValueError("Hiring overview or salary data is missing")
    for key in ("total_jobs", "total_companies", "new_this_week", "jobs_with_salary"):
        value = overview.get(key)
        minimum = 1 if key in ("total_jobs", "total_companies") else 0
        if type(value) is not int or value < minimum:
            raise ValueError(f"Invalid hiring count: {key}")
    if overview["jobs_with_salary"] > overview["total_jobs"]:
        raise ValueError("Salary coverage exceeds the role count")
    median = salary.get("median")
    if overview["jobs_with_salary"] and (
        type(median) not in (int, float) or not math.isfinite(median) or median <= 0
    ):
        raise ValueError("Disclosed salary median is missing or invalid")
    for name, label, count in (
        ("companies", "company", "roles"),
        ("tags", "tag", "count"),
        ("workplace", "type", "count"),
        ("experience_levels", "level", "count"),
    ):
        rows = stats.get(name)
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"Missing hiring table: {name}")
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get(label), str) or not row[label]:
                raise ValueError(f"Invalid label in {name}")
            if type(row.get(count)) is not int or row[count] < 0:
                raise ValueError(f"Invalid count in {name}")
    for key in ("total_sites", "mcp_verified"):
        value = digest.get(key)
        minimum = 1 if key == "total_sites" else 0
        if type(value) is not int or value < minimum:
            raise ValueError(f"Invalid infrastructure count: {key}")
    if digest["mcp_verified"] > digest["total_sites"]:
        raise ValueError("MCP-verified entries exceed indexed entries")
    for stamp in (overview.get("updated_at"), digest.get("generated_at")):
        if not isinstance(stamp, str) or not stamp:
            raise ValueError("Source timestamps are missing")
        datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def build_markdown(stats: dict[str, Any], digest: dict[str, Any], today: str) -> str:
    validate_sources(stats, digest)
    ov = stats["overview"]
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
    top_companies = sorted(companies, key=lambda row: row["roles"], reverse=True)[:10]

    # Top 15 skill tags by reported posting count.
    top_tags = sorted(tags, key=lambda row: row["count"], reverse=True)[:15]

    # Workplace ordering: Onsite, Remote, Hybrid
    ws_map = {w.get("type"): w for w in workplaces}

    # Most frequent seniority labels returned by the API.
    top_levels = sorted(experience_levels, key=lambda row: row["count"], reverse=True)[:5]

    top_tag = top_tags[0]
    tag_observation = (
        f"**Most frequent returned tag**: `{top_tag['tag']}` appears on "
        f"{fmt_thousands(top_tag['count'])} indexed roles. A role can carry multiple tags."
    )
    salary_observation = (
        f"**Salary coverage**: {fmt_thousands(jobs_with_salary)} of "
        f"{fmt_thousands(total_jobs)} roles disclose salary ({salary_disclosed_pct:.1f}%). "
        "Salary summaries cover those disclosures."
    )
    mcp_observation = (
        f"**MCP coverage**: {fmt_thousands(nhs_mcp)} of {fmt_thousands(nhs_total)} "
        f"indexed entries are marked MCP-verified ({nhs_mcp_pct:.1f}%) in the NHS snapshot."
    )

    # ---------- Markdown assembly ----------
    lines: list[str] = []
    lines.append("# State of AI Engineering: Catalog Snapshot")
    lines.append("")
    lines.append(f"**Updated**: {today}")
    lines.append("")
    lines.append(
        "Correction (2026-11-24): The previous zero-role figures and trend claims "
        "were not validated and have been withdrawn. Figures below describe the "
        "linked catalog snapshots."
    )
    lines.append("")
    lines.append(
        "Hiring figures describe [AI Dev Board](https://aidevboard.com)'s indexed roles. "
        "Infrastructure figures describe [Not Human Search](https://nothumansearch.ai)'s "
        "indexed websites. Both catalogs are operated by 8BitConcepts."
    )
    lines.append("")
    lines.append(f"Source timestamps: ADB {ov['updated_at']}; NHS {digest['generated_at']}.")
    lines.append("")

    # Topline numbers
    lines.append("## Topline numbers")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Active roles indexed by AI Dev Board | **{fmt_thousands(total_jobs)}** |")
    lines.append(f"| Hiring companies indexed | **{fmt_thousands(total_companies)}** |")
    lines.append(f"| New roles posted this week | **{fmt_thousands(new_this_week)}** |")
    lines.append(f"| Median salary (disclosed) | **{fmt_salary(median)}** |")
    lines.append(
        f"| Salary-disclosed roles | {fmt_thousands(jobs_with_salary)} ({salary_disclosed_pct:.1f}%) |"
    )
    lines.append(f"| Websites indexed by NHS | **{fmt_thousands(nhs_total)}** |")
    lines.append(
        f"| Entries marked MCP-verified by NHS | **{fmt_thousands(nhs_mcp)}** ({nhs_mcp_pct:.1f}%) |"
    )
    lines.append("")

    # Top 10 companies
    lines.append("## Top 10 hiring companies in this catalog")
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
    lines.append("## Top 15 returned tags by posting count")
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
    for key in ["onsite", "remote", "hybrid"] + [
        key for key in ws_map if key not in ("onsite", "remote", "hybrid")
    ]:
        w = ws_map.get(key)
        if not w:
            continue
        label = key.capitalize()
        count = int(w.get("count", 0) or 0)
        avg_salary = fmt_salary(w.get("avg_salary", 0))
        lines.append(f"| {label} | {fmt_thousands(count)} | {avg_salary} |")
    lines.append("")

    # Seniority mix
    lines.append("## Most frequent seniority labels")
    lines.append("")
    lines.append("| Level | Roles |")
    lines.append("|---|---:|")
    for lvl in top_levels:
        label = level_label(str(lvl.get("level", "")))
        count = int(lvl.get("count", 0) or 0)
        lines.append(f"| {label} | {fmt_thousands(count)} |")
    lines.append("")

    # Key signals
    lines.append("## Observations from these catalogs")
    lines.append("")
    lines.append(f"- {tag_observation}")
    lines.append(f"- {salary_observation}")
    lines.append(f"- {mcp_observation}")
    lines.append("")

    # Companion research
    lines.append("## Related research")
    lines.append("")
    lines.append(
        "- [Q2 2026 AI Hiring Snapshot](https://8bitconcepts.com/research/q2-2026-ai-hiring-snapshot.html) "
        "(hiring writeup)"
    )
    lines.append(
        "- [Q2 2026 AI Compensation by Skill](https://8bitconcepts.com/research/q2-2026-ai-compensation-by-skill.html) "
        "(salary by tag)"
    )
    lines.append(
        "- [Q2 2026 MCP Ecosystem Health](https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html) "
        "(infrastructure coverage)"
    )
    lines.append(
        "- [Research Atlas (full set)](https://8bitconcepts.com/research/overview.html)"
    )
    lines.append("")

    # Data APIs
    lines.append("## Data APIs (free, no auth)")
    lines.append("")
    lines.append(
        "- ADB: `https://aidevboard.com/api/v1/stats` (hiring, salaries, companies, tags)"
    )
    lines.append(
        "- NHS: `https://nothumansearch.ai/digest.json` (indexed infrastructure and categories)"
    )
    lines.append("")

    # Attribution
    lines.append("## Attribution")
    lines.append("")
    lines.append(
        "Published by [8BitConcepts](https://8bitconcepts.com/?utm_source=github-gist&utm_medium=referral&utm_campaign=master-snapshot). "
        "[AI consulting and workflow automation](https://8bitconcepts.com/work-with-us.html?utm_source=github-gist&utm_medium=referral&utm_campaign=master-snapshot). "
        "Free to cite with attribution to AI Dev Board and Not Human Search. "
        "Questions: hello@8bitconcepts.com."
    )

    return "\n".join(lines) + "\n"


def update_gist(md_text: str) -> bool:
    """Publish only to the expected owned gist, then verify all changed fields."""
    current = subprocess.run(["gh", "api", f"gists/{GIST_ID}"], capture_output=True, text=True)
    if current.returncode != 0:
        print("   Gist preflight read failed", file=sys.stderr)
        return False
    data = json.loads(current.stdout)
    if (data.get("owner", {}).get("login") != "unitedideas" or data.get("public") is not True
            or GIST_MD_FILENAME not in data.get("files", {})):
        print("   Gist owner, visibility or filename differs from expected", file=sys.stderr)
        return False
    tmpdir = Path(tempfile.gettempdir()) / "master-snapshot-gist"
    try:
        tmpdir.mkdir(parents=True, exist_ok=True)
        md_path = tmpdir / GIST_MD_FILENAME
        md_path.write_text(md_text, encoding="utf-8")
        print(f"   Wrote gist file to {md_path}")
    except Exception as e:
        print(f"   Gist temp write failed: {type(e).__name__}", file=sys.stderr)
        return False

    cmd = ["gh", "gist", "edit", GIST_ID, "--desc", GIST_DESCRIPTION,
           "--filename", GIST_MD_FILENAME, "--", str(md_path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(
            f"   gh gist edit failed with exit status {r.returncode}",
            file=sys.stderr,
        )
        return False
    readback = subprocess.run(["gh", "api", f"gists/{GIST_ID}"], capture_output=True, text=True)
    if readback.returncode != 0:
        print("   Gist write returned success; readback failed", file=sys.stderr)
        return False
    stored = json.loads(readback.stdout)
    if (stored.get("owner", {}).get("login") != "unitedideas" or stored.get("public") is not True
            or stored.get("description") != GIST_DESCRIPTION
            or stored.get("files", {}).get(GIST_MD_FILENAME, {}).get("content") != md_text):
        print("   Gist readback differs from requested content or description", file=sys.stderr)
        return False
    print(f"   Gist content and description verified: {GIST_URL}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate the State of AI Engineering master gist from live data."
    )
    parser.add_argument("--dry-run", action="store_true", help="Fetch + render, don't write")
    parser.add_argument("--once", action="store_true", help="One run including publication (same as default)")
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
    print("2. Validating sources and rendering master markdown...")
    try:
        md_text = build_markdown(stats, digest, today)
    except (ValueError, TypeError, KeyError) as e:
        print(f"   Source validation failed: {e}", file=sys.stderr)
        return 2
    ov = stats["overview"]
    print(
        f"   ADB: {ov.get('total_jobs')} jobs / {ov.get('total_companies')} cos / "
        f"{ov.get('new_this_week')} new this wk"
    )
    print(
        f"   NHS: {digest.get('total_sites')} sites / {digest.get('mcp_verified')} mcp / "
        f"{digest.get('llms_txt_count')} llms.txt"
    )

    print(f"   Rendered {len(md_text)} chars")

    if args.dry_run:
        print(f"   [DRY RUN] Would push {len(md_text)} chars to gist {GIST_ID}")
        print("   First 400 chars:")
        print(md_text[:400])
        return 0

    if args.once:
        print("\n3. Updating master gist (--once: will still push gist)...")
    else:
        print("\n3. Updating master gist...")

    try:
        ok = update_gist(md_text)
    except Exception as e:
        print(f"   Gist update failed: {type(e).__name__}", file=sys.stderr)
        ok = False

    if ok:
        print("\n=== Done. ===")
        return 0
    print("\n=== Publication failed; inspect the current gist before retrying. ===")
    return 1


if __name__ == "__main__":
    sys.exit(main())
