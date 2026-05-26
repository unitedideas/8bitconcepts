#!/usr/bin/env python3
"""
Generate one daily X and LinkedIn candidate for each active Foundry business.

This is a queue builder only. It never posts. The channel publishers still own
fact checks, social-editor approval, public-action locks, live URL capture, and
ledger updates.

Usage:
  python3 tools/generate-portfolio-social-queue.py
  python3 tools/generate-portfolio-social-queue.py --date 2026-05-02
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = Path.home() / ".foundry" / "foundry-sync-state" / "systems" / "foundry-business-index.md"
QUEUE_PATH = REPO / "marketing" / "daily-portfolio-social-queue.json"
LEDGER_PATH = REPO / "marketing" / "social-post-ledger.json"
X_ACCOUNT = "@8bitconcepts"
LINKEDIN_PROFILE = "https://www.linkedin.com/in/shane-cheek-9173473b6/"
URL_LENGTH_BUDGET = 23
X_MAX_LENGTH = 280


@dataclass(frozen=True)
class Business:
    name: str
    stage: str
    repo: str
    url: str
    primary_job: str
    current_motion: str
    next_move: str


def slugify(value: str) -> str:
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", value.lower()))


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def fingerprint(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()[:16]


def strip_code(value: str) -> str:
    return value.strip().strip("`")


def clean_text(value: str) -> str:
    value = re.sub(r"`+", "", value)
    value = value.replace("SPT/ACP", "agent-payment rails")
    value = value.replace("x402/MPP", "machine-payment rails")
    value = value.replace("private-preview-gated", "still private-preview gated")
    return " ".join(value.split())


def safe_next_move(value: str) -> str:
    cleaned = clean_text(value)
    lowered = cleaned.lower()
    if "mcp-org/punkpeye" in lowered or "unitedideas" in lowered:
        return "keep distribution moving without platform-specific account dependencies"
    return cleaned


def parse_active_portfolio(index_path: Path) -> list[Business]:
    text = index_path.read_text(encoding="utf-8")
    in_section = False
    rows: list[Business] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == "## Active Portfolio":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section or not line.startswith("|"):
            continue
        if line.startswith("|---") or line.startswith("| Business |"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 7:
            continue
        rows.append(
            Business(
                name=cells[0],
                stage=cells[1],
                repo=strip_code(cells[2]),
                url=strip_code(cells[3]),
                primary_job=cells[4],
                current_motion=cells[5],
                next_move=cells[6],
            )
        )
    if not rows:
        raise SystemExit(f"no active portfolio rows found in {index_path}")
    return rows


def clipped(value: str, limit: int) -> str:
    value = clean_text(value)
    if len(value) <= limit:
        return value
    cut = value[: limit - 1].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0].rstrip()
    cut = cut.rstrip(" ,;:-")
    if ", and " in cut:
        cut = cut.rsplit(", and ", 1)[0].rstrip(" ,;:-")
    while cut.lower().split()[-1:] in (["and"], ["or"], ["with"], ["plus"]):
        cut = cut.rsplit(" ", 1)[0].rstrip(" ,;:-")
    return cut


def first_clause(value: str, limit: int) -> str:
    cleaned = clean_text(value)
    fallback = cleaned
    for separator in ("; ", ": ", ", ", ". "):
        if separator not in cleaned:
            continue
        head = cleaned.split(separator, 1)[0].strip()
        if 16 <= len(head) <= limit:
            return head
        if len(head) > limit:
            fallback = head
            continue
    return clipped(fallback, limit)


def x_length(text: str) -> int:
    text = text.strip()
    if not text:
        return 0
    parts = text.split()
    return sum(URL_LENGTH_BUDGET if token.startswith("http://") or token.startswith("https://") else len(token) for token in parts) + max(0, len(parts) - 1)


def existing_fingerprints() -> dict[str, set[str]]:
    if not LEDGER_PATH.exists():
        return {}
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    statuses = {
        "posted",
        "scheduled",
        "queued",
        "claimed",
        "deferred_recent_related_post",
    }
    fingerprints: dict[str, set[str]] = {}
    for item in ledger.get("items", []):
        if item.get("fingerprint") and item.get("status") in statuses:
            fingerprints.setdefault(item["fingerprint"], set()).add(item.get("id", ""))
    return fingerprints


def x_copy(business: Business, angle_index: int) -> str:
    primary = first_clause(business.primary_job, 88)
    motion = first_clause(business.current_motion, 76)
    next_move = first_clause(safe_next_move(business.next_move), 74)
    templates = [
        f"{primary}\n\nCurrent move at {business.name}: {motion}\n\n{business.url}",
        f"{primary}\n\nNext move for {business.name}: {next_move}\n\n{business.url}",
        f"{business.name} is live: {business.url}\n\n{primary}\n\nConstraint: {next_move}",
        f"{primary}\n\nLive surface: {business.url}\n\nCurrent constraint: {next_move}",
        f"{primary}\n\n{business.name} is shipping around this constraint: {motion}\n\n{business.url}",
    ]
    for template in templates[angle_index % len(templates):] + templates[: angle_index % len(templates)]:
        if x_length(template) <= X_MAX_LENGTH and not template.endswith(".."):
            return template
    fallback = f"{primary}\n\nNext move: {next_move}\n\n{business.url}"
    if x_length(fallback) > X_MAX_LENGTH:
        fallback = f"{primary}\n\n{business.url}"
    return fallback


def linkedin_copy(business: Business, angle_index: int) -> str:
    primary = clipped(business.primary_job, 120)
    motion = clipped(first_clause(business.current_motion, 140), 140)
    next_move = clipped(first_clause(safe_next_move(business.next_move), 140), 140)
    templates = [
        f"{business.name} is live at {business.url}.\n\nWhat is shipping now: {motion}\n\nWhat the product is for: {primary}\n\nNext move: {next_move}",
        f"One live Foundry surface today is {business.name}.\n\nProduct: {primary}\n\nCurrent motion: {motion}\n\nNext move: {next_move}\n\n{business.url}",
        f"{business.name} is a useful operating example because the proof is public.\n\nCurrent motion: {motion}\n\nNext move: {next_move}\n\nRoute: {business.url}",
        f"{business.name} is live, and the interesting part is the current bottleneck.\n\nProduct: {primary}\n\nConstraint: {next_move}\n\n{business.url}",
        f"{business.name} is a live product, not a roadmap.\n\nWhat is visible now: {motion}\n\nWhat needs to happen next: {next_move}\n\n{business.url}",
    ]
    return templates[angle_index % len(templates)]


def render_queue(target: date, index_path: Path) -> dict[str, object]:
    existing = existing_fingerprints()
    businesses = parse_active_portfolio(index_path)
    items = []
    for offset, business in enumerate(businesses):
        angle_index = (target.toordinal() + offset) % 5
        x = x_copy(business, angle_index)
        linkedin = linkedin_copy(business, angle_index)
        item_id = f"portfolio-daily-{target.isoformat()}-{slugify(business.name)}"
        x_id = f"{item_id}-x"
        linkedin_id = f"{item_id}-linkedin"
        x_fp = fingerprint(x)
        linkedin_fp = fingerprint(linkedin)
        items.append(
            {
                "id": item_id,
                "kind": "portfolio_daily",
                "date": target.isoformat(),
                "business": {
                    "name": business.name,
                    "stage": business.stage,
                    "repo": business.repo,
                    "url": business.url,
                    "primary_job": business.primary_job,
                    "current_motion": business.current_motion,
                    "next_move": business.next_move,
                },
                "fact_key": f"portfolio-daily:{target.isoformat()}:{slugify(business.name)}",
                "route": business.url,
                "channels": {
                    "x": {
                        "account": X_ACCOUNT,
                        "copy": x,
                        "fingerprint": x_fp,
                        "duplicate": x_fp in existing and any(existing_id != x_id for existing_id in existing[x_fp]),
                        "length": x_length(x),
                    },
                    "linkedin": {
                        "profile": LINKEDIN_PROFILE,
                        "copy": linkedin,
                        "fingerprint": linkedin_fp,
                        "duplicate": linkedin_fp in existing and any(existing_id != linkedin_id for existing_id in existing[linkedin_fp]),
                    },
                },
                "quality_gate": [
                    "uses the active business index as source",
                    "includes the product URL",
                    "states one concrete current motion or next move",
                    "routes second, teaches first",
                    "requires social-editor approval before posting",
                ],
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_index": str(index_path),
        "cadence": "one X and one LinkedIn candidate per active business per day",
        "items": items,
    }


def upsert_ledger(queue: dict[str, object]) -> None:
    if LEDGER_PATH.exists():
        ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    else:
        ledger = {
            "schema": 1,
            "rule": "Every social post gets a normalized text fingerprint before it is queued or posted. If the fingerprint already exists with status posted, scheduled, or queued, do not post it again.",
            "items": [],
        }
    items = ledger.setdefault("items", [])
    by_id = {item.get("id"): item for item in items}
    preserve_statuses = {
        "posted",
        "scheduled",
        "claimed",
        "blocked",
        "deferred_recent_related_post",
        "removed",
        "sent",
        "submitted",
    }
    for queue_item in queue["items"]:
        business = queue_item["business"]
        for channel, channel_data in queue_item["channels"].items():
            record_id = f"{queue_item['id']}-{channel}"
            existing = by_id.get(record_id)
            if existing and existing.get("status") in preserve_statuses:
                continue
            record = {
                "id": record_id,
                "source": "marketing/daily-portfolio-social-queue.json",
                "channel": channel,
                "account": channel_data.get("account") or channel_data.get("profile"),
                "status": "queued",
                "date": queue_item["date"],
                "business": business["name"],
                "fingerprint": channel_data["fingerprint"],
                "fact_key": queue_item["fact_key"],
                "route": queue_item["route"],
                "note": "Generated by tools/generate-portfolio-social-queue.py; publisher must fact-check, run social-editor, claim lock, post, capture URL, and update this record.",
            }
            if existing:
                existing.update(record)
            else:
                items.append(record)
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD date for deterministic queue generation")
    parser.add_argument("--index", default=str(DEFAULT_INDEX), help="path to foundry-business-index.md")
    parser.add_argument("--no-ledger", action="store_true", help="write queue without upserting social-post-ledger.json")
    args = parser.parse_args()

    target = date.fromisoformat(args.date) if args.date else date.today()
    index_path = Path(args.index).expanduser()
    queue = render_queue(target, index_path)
    QUEUE_PATH.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    if not args.no_ledger:
        upsert_ledger(queue)
    print(f"wrote {QUEUE_PATH}")
    if args.no_ledger:
        print(f"left {LEDGER_PATH} unchanged")
    else:
        print(f"updated {LEDGER_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
