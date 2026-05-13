#!/usr/bin/env python3
"""
IndexNow submission for 8bitconcepts local + research pages.
Notifies Google/Bing of new/updated URLs for faster crawling.

Usage:
  python3 tools/submit-indexnow.py [--dry-run]

Requires:
  - Bing IndexNow API key in environment var INDEXNOW_KEY
    (or stored in macOS Keychain as `security find-generic-password -a foundry -s indexnow-8bc-key`)
"""

import json
import sys
import os
import subprocess
from datetime import datetime
from typing import List

BASE_URL = "https://8bitconcepts.com"

# All URLs that need IndexNow submission
URLS_TO_SUBMIT = [
    "/local/",
    "/local/vancouver-wa.html",
    "/local/camas-wa.html",
    "/local/portland-or.html",
    "/local/tigard-or.html",
    "/research/claude-code-context-limit-fix.html",
    "/research/claude-md-guide.html",
    "/research/the-self-testing-layer.html",
    "/research/on-device-inference.html",
    "/research/q2-2026-ai-hiring-geography.html",
    "/local/beaverton-or.html",
    "/local/hillsboro-or.html",
    "/local/lake-oswego-or.html",
    "/local/salem-or.html",
    "/local/oregon-city-or.html",
    "/local/gresham-or.html",
    "/local/tualatin-or.html",
    "/local/",
    "/research/the-agentic-commerce-gap.html",
    "/research/claude-code-vs-cursor.html",
    "/local/battle-ground-wa.html",
    "/local/sherwood-or.html",
    "/local/ridgefield-wa.html",
    "/local/washougal-wa.html",
    "/local/newberg-or.html",
    "/research/claude-code-pricing.html",
    "/research/how-to-use-claude-code.html",
    "/research/claude-code-vs-github-copilot.html",
    "/research/claude-code-for-teams.html",
    "/research/claude-code-mcp.html",
    "/research/claude-code-vs-windsurf.html",
    "/research/claude-code-vs-aider.html",
    "/research/claude-code-tips.html",
    "/research/claude-code-hooks.html",
    "/research/claude-code-vs-codex.html",
    "/research/claude-code-vs-gemini.html",
]

def get_indexnow_key() -> str:
    """Get IndexNow key from env or keychain."""
    key = os.getenv("INDEXNOW_KEY")
    if key:
        return key
    
    try:
        key = subprocess.check_output(
            ['security', 'find-generic-password', '-a', 'foundry', '-s', 'indexnow-8bc-key', '-w'],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        return key
    except:
        raise RuntimeError(
            "INDEXNOW_KEY not set. Set via env or store in keychain:\n"
            "  security add-generic-password -a foundry -s indexnow-8bc-key -w '<key>' 2>/dev/null"
        )

def submit_to_indexnow(urls: List[str], key: str, dry_run: bool = False) -> bool:
    """
    Submit URLs to IndexNow.
    Returns True if all succeeded, False otherwise.
    """
    import urllib.request
    import urllib.error
    
    full_urls = [f"{BASE_URL}{url}" for url in urls]
    
    payload = {
        "host": "8bitconcepts.com",
        "key": key,
        "keyLocation": f"{BASE_URL}/{key}.txt",
        "urlList": full_urls
    }
    
    print(f"[{datetime.now().isoformat()}] Submitting {len(full_urls)} URLs to IndexNow")
    if dry_run:
        print(f"[DRY RUN] Would POST to https://api.indexnow.org/indexnow")
        print(json.dumps(payload, indent=2))
        return True
    
    try:
        req = urllib.request.Request(
            "https://api.indexnow.org/indexnow",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            print(f"  IndexNow: HTTP {status} ({'ok' if status in (200, 202) else 'check response'})")
            return status in (200, 202)
    except urllib.error.HTTPError as e:
        print(f"  IndexNow HTTP error: {e.code} {e.reason}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  IndexNow failed: {e}", file=sys.stderr)
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Submit 8bitconcepts pages to IndexNow")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be submitted without actually submitting")
    args = parser.parse_args()
    
    try:
        key = get_indexnow_key()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    ok = submit_to_indexnow(URLS_TO_SUBMIT, key, dry_run=args.dry_run)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
