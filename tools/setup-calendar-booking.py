#!/usr/bin/env python3
"""
Replace all "Book a 30-min intro call" CTAs with a Cal.com booking URL.

Usage:
  ./setup-calendar-booking.py --url "https://cal.com/8bitconcepts/30min" --dry-run
  ./setup-calendar-booking.py --url "https://cal.com/8bitconcepts/30min" --apply
  ./setup-calendar-booking.py --verify
"""

import re
import sys
from pathlib import Path

# Files to update (30 instances across 27 files per grep)
FILES_TO_UPDATE = [
    "index.html",
    "work-with-us.html",
    "case-studies.html",
    "faq.html",
    "diagnostic.html",
    "local/index.html",
    "local/vancouver-wa.html",
    "local/camas-wa.html",
    "local/portland-or.html",
    "local/tigard-or.html",
    "research/beyond-the-prompt.html",
    "research/q2-2026-ai-compensation-by-skill.html",
    "research/q2-2026-ai-hiring-geography.html",
    "research/q2-2026-ai-hiring-snapshot.html",
    "research/q2-2026-entry-level-ai-gap.html",
    "research/q2-2026-mcp-ecosystem-health.html",
    "research/q2-2026-remote-vs-onsite-ai-hiring.html",
    "research/shift-handoff-intelligence.html",
    "research/the-agentic-accountability-gap.html",
    "research/the-compounding-gap.html",
    "research/the-context-wall.html",
    "research/the-domain-advantage.html",
    "research/the-expansion-tax.html",
    "research/the-foundation-trap.html",
    "research/the-guardrails-gap.html",
    "research/the-hallucination-budget.html",
    "research/the-integration-tax.html",
    "research/the-mandate-trap.html",
    "research/the-measurement-problem.html",
    "research/the-org-chart-problem.html",
    "research/the-pnw-ai-desert.html",
    "research/the-six-percent.html",
]

def count_instances(root: Path) -> int:
    """Count total instances of the old pattern."""
    count = 0
    for fpath in FILES_TO_UPDATE:
        full = root / fpath
        if full.exists():
            content = full.read_text()
            count += content.count("Book a 30-min intro call")
    return count

def replace_booking_link(content: str, new_url: str) -> str:
    """Replace /work-with-us.html#lead-form with new_url for 'Book a 30-min intro call' links."""
    # Pattern: href="/work-with-us.html#lead-form" (and possibly other attributes)
    # We need to be careful to preserve surrounding HTML
    pattern = r'href="/work-with-us\.html#lead-form"'
    replacement = f'href="{new_url}"'
    return content.replace(pattern, replacement)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Replace Cal.com booking links")
    parser.add_argument("--url", help="Cal.com booking URL (e.g., https://cal.com/8bitconcepts/30min)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change")
    parser.add_argument("--apply", action="store_true", help="Apply changes to files")
    parser.add_argument("--verify", action="store_true", help="Verify all old links have been replaced")
    args = parser.parse_args()

    root = Path(__file__).parent.parent

    if args.verify:
        count = count_instances(root)
        if count == 0:
            print("✓ All booking links replaced. No old #lead-form links remain.")
            return 0
        else:
            print(f"✗ Found {count} old booking links still pointing to #lead-form")
            return 1

    if not args.url:
        print("Error: --url required for dry-run or apply")
        return 1

    if not args.url.startswith("http"):
        print("Error: --url must be absolute (http/https)")
        return 1

    changes = {}
    for fpath in FILES_TO_UPDATE:
        full = root / fpath
        if not full.exists():
            continue

        content = full.read_text()
        new_content = replace_booking_link(content, args.url)

        if content != new_content:
            changes[str(full.relative_to(root))] = (content.count("Book a 30-min intro call"),
                                                      new_content.count("/work-with-us.html#lead-form"))

    if not changes:
        print("No changes needed")
        return 0

    print(f"Found {len(changes)} files with booking links")
    for fpath in sorted(changes.keys()):
        old_count, new_count = changes[fpath]
        print(f"  {fpath}: {old_count} instance(s)")

    if args.dry_run:
        print(f"\nDry run: would replace all with {args.url}")
        print("Run with --apply to confirm")
        return 0

    if args.apply:
        for fpath in FILES_TO_UPDATE:
            full = root / fpath
            if not full.exists():
                continue
            content = full.read_text()
            new_content = replace_booking_link(content, args.url)
            if content != new_content:
                full.write_text(new_content)
                print(f"✓ {fpath}")
        print(f"\nSuccessfully updated {len(changes)} files")
        return 0

    print("Use --dry-run or --apply")
    return 1

if __name__ == "__main__":
    sys.exit(main())
