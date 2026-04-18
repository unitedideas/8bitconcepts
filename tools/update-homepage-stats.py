#!/usr/bin/env python3
"""
Refresh the five auto-regenerating headline stats on /index.html from live APIs.

The homepage hero shows one-liner stats for the five live-data research papers:
  - Q2 2026 AI Hiring Snapshot   (aidevboard.com/api/v1/stats)
  - Q2 2026 AI Compensation by Skill
  - Q2 2026 Remote vs Onsite AI Hiring
  - Q2 2026 The Junior AI Hiring Gap
  - Q2 2026 MCP Ecosystem Health (nothumansearch.ai/digest.json)

This script fetches both APIs and rewrites the five stat elements by DOM id,
plus the "Last updated YYYY-MM-DD" timestamp. Idempotent: if values didn't
change it does nothing (so the outer regenerator sees no diff -> no commit).

Called from:
  - tools/generate-overview.py (end of main, so every paper regen rolls the
    homepage forward in the same commit that refreshes the atlas).
  - Directly as a Monday morning job if you just want stats-only refresh.

Usage:
    python3 tools/update-homepage-stats.py           # fetch + rewrite
    python3 tools/update-homepage-stats.py --dry-run # fetch + show diff, no write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
INDEX_PATH = REPO / "index.html"
ADB_STATS_URL = "https://aidevboard.com/api/v1/stats"
NHS_DIGEST_URL = "https://nothumansearch.ai/digest.json"
USER_AGENT = "curl/8.7.1"


def http_get_json(url: str, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fmt_thousands(n: Any) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n)


def build_stats(stats: dict[str, Any], digest: dict[str, Any]) -> dict[str, str]:
    """Compute the five headline-stat inner HTML fragments.

    Returns a dict keyed by the <span id=...> on index.html. Each value is the
    exact inner HTML we want inside that element (including <em>...</em> for
    the terracotta number).
    """
    ov = stats.get("overview", {}) or {}
    tags = stats.get("tags", []) or []
    companies = stats.get("companies", []) or []
    workplaces = stats.get("workplace", []) or []
    experience_levels = stats.get("experience_levels", []) or []

    total_jobs = int(ov.get("total_jobs", 0) or 0)

    # Hiring: "<em>{total}</em> live AI/ML roles — {top_company} leads with {top_count}"
    top_co = companies[0] if companies else {}
    top_co_name = str(top_co.get("company", "")) or "—"
    top_co_roles = int(top_co.get("roles", 0) or 0)
    hiring = (
        f"<em>{fmt_thousands(total_jobs)}</em> live AI/ML roles &mdash; "
        f"{top_co_name} leads with {fmt_thousands(top_co_roles)}"
    )

    # Compensation: research vs generative-ai premium
    def tag_row(name: str) -> dict[str, Any]:
        for t in tags:
            if t.get("tag") == name:
                return t
        return {}

    research_avg = int(tag_row("research").get("avg_salary", 0) or 0)
    genai_avg = int(tag_row("generative-ai").get("avg_salary", 0) or 0)
    if research_avg > genai_avg > 0:
        premium_k = (research_avg - genai_avg) // 1000
        comp = f"Research pays <em>${premium_k}k</em> more than generative-AI"
    elif genai_avg > research_avg > 0:
        premium_k = (genai_avg - research_avg) // 1000
        comp = f"Generative-AI pays <em>${premium_k}k</em> more than research roles"
    else:
        comp = "Research vs generative-AI: premium data unavailable this week"

    # Remote vs onsite: hybrid premium vs max(remote, onsite)
    ws_map = {w.get("type"): w for w in workplaces}
    hybrid = ws_map.get("hybrid", {})
    remote = ws_map.get("remote", {})
    onsite = ws_map.get("onsite", {})
    hybrid_sal = int(hybrid.get("avg_salary", 0) or 0)
    remote_sal = int(remote.get("avg_salary", 0) or 0)
    onsite_sal = int(onsite.get("avg_salary", 0) or 0)
    non_hybrid = max(remote_sal, onsite_sal)
    if hybrid_sal > non_hybrid > 0:
        premium_k = (hybrid_sal - non_hybrid) // 1000
        remote_vs = f"Hybrid AI roles pay a <em>${premium_k}k</em> premium"
    elif remote_sal > onsite_sal > 0:
        premium_k = (remote_sal - onsite_sal) // 1000
        remote_vs = f"Remote AI roles pay <em>${premium_k}k</em> more than onsite"
    elif onsite_sal > remote_sal > 0:
        premium_k = (onsite_sal - remote_sal) // 1000
        remote_vs = f"Onsite AI roles pay <em>${premium_k}k</em> more than remote"
    else:
        remote_vs = "Workplace premium data unavailable this week"

    # Entry-level: junior share of total
    junior_count = 0
    total_level_count = 0
    for lvl in experience_levels:
        c = int(lvl.get("count", 0) or 0)
        total_level_count += c
        if lvl.get("level") == "junior":
            junior_count = c
    if total_level_count > 0 and junior_count > 0:
        pct = junior_count / total_level_count * 100
        entry = f"Only <em>{pct:.1f}%</em> of AI roles are junior"
    elif total_jobs > 0 and junior_count > 0:
        pct = junior_count / total_jobs * 100
        entry = f"Only <em>{pct:.1f}%</em> of AI roles are junior"
    else:
        entry = "Entry-level share data unavailable this week"

    # MCP: verified share of total
    nhs_total = int(digest.get("total_sites", 0) or 0)
    nhs_mcp = int(digest.get("mcp_verified", 0) or 0)
    if nhs_total > 0:
        pct = nhs_mcp / nhs_total * 100
        mcp = f"Only <em>{pct:.1f}%</em> of MCP claims verify live"
    else:
        mcp = "MCP verification data unavailable this week"

    return {
        "stat-hiring": hiring,
        "stat-comp": comp,
        "stat-remote": remote_vs,
        "stat-entry": entry,
        "stat-mcp": mcp,
    }


# Matches an element like:  <... id="stat-hiring"...>INNER</...>
# where the same element is on one line (which it is in our homepage).
STAT_RE = re.compile(
    r'(<[^>]*\bid="([^"]+)"[^>]*>)([^<]*(?:<(?!/[a-z]+>)[^<]*)*)(</[a-z]+>)',
    re.IGNORECASE,
)


def replace_stat(html: str, stat_id: str, new_inner: str) -> tuple[str, bool]:
    """Rewrite the inner HTML of the element with id=stat_id.

    Only rewrites when the inner differs (so idempotent refresh).
    Returns (new_html, changed).
    """
    # Find the opening tag with this id
    open_pat = re.compile(
        r'(<(?P<tag>[a-zA-Z]+)[^>]*\bid="' + re.escape(stat_id) + r'"[^>]*>)',
    )
    m = open_pat.search(html)
    if not m:
        print(f"  WARN: id={stat_id!r} not found in index.html", file=sys.stderr)
        return html, False
    tag = m.group("tag")
    start_inner = m.end()
    close_tag = f"</{tag}>"
    end_inner = html.find(close_tag, start_inner)
    if end_inner < 0:
        print(f"  WARN: no {close_tag} after id={stat_id!r}", file=sys.stderr)
        return html, False
    current_inner = html[start_inner:end_inner]
    if current_inner == new_inner:
        return html, False
    return html[:start_inner] + new_inner + html[end_inner:], True


LAST_UPDATED_RE = re.compile(
    r'(<span[^>]*\bid="live-last-updated"[^>]*>)Last updated [0-9]{4}-[0-9]{2}-[0-9]{2}(</span>)'
)


def replace_last_updated(html: str, today: str) -> tuple[str, bool]:
    new_html, n = LAST_UPDATED_RE.subn(
        r"\1Last updated " + today + r"\2", html, count=1
    )
    return new_html, n > 0 and new_html != html


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh homepage headline stats from live APIs."
    )
    parser.add_argument("--dry-run", action="store_true", help="Fetch + render, don't write")
    args = parser.parse_args()

    if not INDEX_PATH.is_file():
        print(f"ERROR: {INDEX_PATH} not found", file=sys.stderr)
        return 2

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"=== Update homepage stats ({today}) ===")

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

    print("2. Computing stat fragments...")
    new_stats = build_stats(stats, digest)
    for k, v in new_stats.items():
        print(f"   {k}: {v}")

    print("3. Rewriting index.html...")
    html = INDEX_PATH.read_text(encoding="utf-8")
    changed_any = False
    for stat_id, new_inner in new_stats.items():
        html, changed = replace_stat(html, stat_id, new_inner)
        if changed:
            print(f"   updated {stat_id}")
            changed_any = True
        else:
            print(f"   {stat_id} unchanged")

    html, last_changed = replace_last_updated(html, today)
    if last_changed:
        print(f"   updated live-last-updated -> {today}")
        changed_any = True

    if args.dry_run:
        print("   [DRY RUN] not writing")
        return 0

    if not changed_any:
        print("   No changes; skipping write.")
        return 0

    INDEX_PATH.write_text(html, encoding="utf-8")
    print(f"   Wrote {INDEX_PATH} ({len(html)} chars)")
    print("\n=== Done. ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
