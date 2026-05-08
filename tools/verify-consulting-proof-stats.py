#!/usr/bin/env python3
"""Verify 8bc consulting proof stats against live Foundry product APIs."""

from __future__ import annotations

import json
import math
import pathlib
import re
import sys
import urllib.error
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]
UA = "curl/8.7.1"


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def get_adb_overview() -> dict:
    """Return public ADB proof stats without requiring paid API quota.

    /api/v1/stats is now a billable anonymous endpoint and can return 402 once
    the shared automation IP exhausts its monthly free quota. The /api/v1 root
    remains intentionally public and carries the same rounded proof totals used
    in 8bc consulting copy.
    """
    try:
        return get_json("https://aidevboard.com/api/v1/stats")["overview"]
    except urllib.error.HTTPError as exc:
        if exc.code != 402:
            raise

    root = get_json("https://aidevboard.com/api/v1")
    description = root.get("description", "")
    jobs_match = re.search(r"([\d,]+)\+\s+(?:curated|current)\s+AI/ML engineering jobs", description)
    companies_match = re.search(r"from ([\d,]+) companies", description)
    if not jobs_match or not companies_match:
        raise AssertionError("ADB /api/v1 fallback missing jobs or companies proof stats")
    return {
        "total_jobs": int(jobs_match.group(1).replace(",", "")),
        "total_companies": int(companies_match.group(1).replace(",", "")),
    }


def get_nhs_mcp_total() -> int:
    try:
        return int(get_json("https://nothumansearch.ai/api/v1/search?has_mcp=true&limit=1")["total"])
    except urllib.error.HTTPError as exc:
        if exc.code != 402:
            raise
    return int(get_json("https://nothumansearch.ai/api/v1/top?has_mcp=true&limit=1")["total"])


def rounded_floor(value: int, step: int = 100) -> str:
    return f"{math.floor(value / step) * step:,}+"


def require_contains(path: pathlib.Path, expected: str) -> None:
    text = path.read_text(encoding="utf-8")
    if expected not in text:
        rel = path.relative_to(ROOT)
        raise AssertionError(f"{rel} missing {expected!r}")


def main() -> int:
    adb = get_adb_overview()
    nhs = get_json("https://nothumansearch.ai/api/v1/stats")
    nhs_mcp_total = get_nhs_mcp_total()
    research_count = len(list((ROOT / "research").glob("*.html")))

    expected = {
        "adb_jobs": rounded_floor(int(adb["total_jobs"])),
        "adb_companies": f"{int(adb['total_companies']):,}",
        "nhs_sites": rounded_floor(int(nhs["total_sites"])),
        "nhs_mcp": f"{nhs_mcp_total:,}",
        "research_count": f"{research_count:,}",
    }

    checks = [
        ("work-with-us.html", expected["adb_jobs"]),
        ("work-with-us.html", f"{expected['adb_companies']}+ companies"),
        ("work-with-us.html", expected["nhs_sites"]),
        ("work-with-us.html", f"{expected['nhs_mcp']} MCP-positive sites"),
        ("work-with-us.html", f"{expected['research_count']} papers"),
        ("case-studies.html", expected["adb_jobs"]),
        ("case-studies.html", expected["adb_companies"]),
        ("case-studies.html", expected["nhs_sites"]),
        ("case-studies.html", expected["nhs_mcp"]),
        ("index.html", f"{expected['research_count']} papers"),
        ("404.html", f"All {expected['research_count']} papers"),
    ]
    for page in [
        "local/vancouver-wa.html",
        "local/camas-wa.html",
        "local/portland-or.html",
        "local/tigard-or.html",
        "local/beaverton-or.html",
        "local/hillsboro-or.html",
        "local/lake-oswego-or.html",
    ]:
        checks.append((page, f"{expected['adb_jobs']} AI/ML jobs"))

    for page, value in checks:
        require_contains(ROOT / page, value)

    print(json.dumps(expected, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
