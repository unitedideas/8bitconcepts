#!/usr/bin/env python3
"""Verify every local SEO page is discoverable by agents."""

from __future__ import annotations

import json
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
LOCAL_URL_RE = re.compile(r"https://8bitconcepts\.com(/local/[a-z0-9-]+\.html)")


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def local_paths_from_sitemap() -> list[str]:
    paths = sorted(set(LOCAL_URL_RE.findall(read("sitemap.xml"))))
    if not paths:
        raise AssertionError("sitemap.xml has no /local/*.html URLs")
    return paths


def main() -> int:
    paths = local_paths_from_sitemap()
    llms = read("llms.txt")
    openapi = read("openapi.yaml")
    api_root = json.loads(read("api/v1/index.html"))
    local_pages = api_root.get("endpoints", {}).get("local_pages", {})
    local_page_values = sorted(local_pages.values())

    missing_llms = [path for path in paths if f"https://8bitconcepts.com{path}" not in llms]
    missing_files = [path for path in paths if not (ROOT / path.lstrip("/")).exists()]
    missing_api_root = [path for path in paths if path not in local_page_values]
    missing_openapi_enum = [
        path for path in paths
        if f"- {path.rsplit('/', 1)[1].removesuffix('.html')}" not in openapi
    ]

    errors = []
    if missing_files:
        errors.append(f"missing local page files: {missing_files}")
    if missing_llms:
        errors.append(f"missing from llms.txt: {missing_llms}")
    if missing_api_root:
        errors.append(f"missing from api/v1 local_pages: {missing_api_root}")
    if missing_openapi_enum:
        errors.append(f"missing from openapi enum: {missing_openapi_enum}")
    if api_root.get("stats", {}).get("local_service_area_pages") != len(paths):
        errors.append("api/v1 stats.local_service_area_pages does not match sitemap local page count")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(json.dumps({"local_service_area_pages": len(paths), "paths": paths}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
