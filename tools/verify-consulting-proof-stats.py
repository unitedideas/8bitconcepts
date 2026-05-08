#!/usr/bin/env python3
"""Verify 8bc consulting proof stats against live Foundry product APIs."""

from __future__ import annotations

import json
import math
import pathlib
import sys
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]
UA = "curl/8.7.1"


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def rounded_floor(value: int, step: int = 100) -> str:
    return f"{math.floor(value / step) * step:,}+"


def require_contains(path: pathlib.Path, expected: str) -> None:
    text = path.read_text(encoding="utf-8")
    if expected not in text:
        rel = path.relative_to(ROOT)
        raise AssertionError(f"{rel} missing {expected!r}")


def main() -> int:
    adb = get_json("https://aidevboard.com/api/v1/stats")["overview"]
    nhs = get_json("https://nothumansearch.ai/api/v1/stats")
    mcp = get_json("https://nothumansearch.ai/api/v1/search?has_mcp=true&limit=1")
    research_count = len(list((ROOT / "research").glob("*.html")))

    expected = {
        "adb_jobs": rounded_floor(int(adb["total_jobs"])),
        "adb_companies": f"{int(adb['total_companies']):,}",
        "nhs_sites": rounded_floor(int(nhs["total_sites"])),
        "nhs_mcp": f"{int(mcp['total']):,}",
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
