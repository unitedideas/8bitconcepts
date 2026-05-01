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
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "."


def x_copy(business: Business, angle_index: int) -> str:
    primary = clipped(business.primary_job, 86)
    motion = clipped(business.current_motion, 84)
    next_move = clipped(business.next_move, 82)
    templates = [
        f"{business.name} is worth talking about because it is not a deck. {primary}\n\nCurrent motion: {motion}\n\n{business.url}",
        f"Current Foundry proof point: {business.name}.\n\nIt tests a concrete wedge: {primary}\n\nThe next useful move is also concrete: {next_move}\n\n{business.url}",
        f"A useful AI product signal is whether the work creates a reusable surface.\n\n{business.name} does that through: {primary}\n\nLive route: {business.url}",
        f"{business.name} is the daily operator note today.\n\nThe interesting part is not the landing page. It is the motion: {motion}\n\n{business.url}",
        f"The next move for {business.name}: {next_move}\n\nThat is the useful level for AI products: one live artifact, one next constraint, one measurable surface.\n\n{business.url}",
    ]
    return templates[angle_index % len(templates)]


def linkedin_copy(business: Business, angle_index: int) -> str:
    templates = [
        f"{business.name} is one of the current Foundry businesses worth watching.\n\nThe job is simple: {business.primary_job}\n\nCurrent motion:\n{business.current_motion}\n\nThe next move is not broad strategy. It is this:\n{business.next_move}\n\nLive route:\n{business.url}",
        f"Daily Foundry business note: {business.name}.\n\nThis is the operating shape:\n\n1. Stage: {business.stage}.\n2. Job: {business.primary_job}\n3. Motion: {business.current_motion}\n4. Next constraint: {business.next_move}\n\nThe useful test is whether this keeps producing public proof instead of internal planning.\n\n{business.url}",
        f"{business.name} is a good example of how I want these products to compound.\n\nOne artifact should do more than one job. It should serve users, give agents something inspectable, create a marketing surface, and expose the next bottleneck.\n\nRight now the bottleneck is:\n{business.next_move}\n\n{business.url}",
        f"The practical question for {business.name} is not whether the idea is interesting.\n\nIt is whether the current motion keeps shrinking the distance between proof and distribution:\n{business.current_motion}\n\nNext useful move:\n{business.next_move}\n\n{business.url}",
        f"{business.name} is the portfolio note today.\n\nWhat it does:\n{business.primary_job}\n\nWhy it matters operationally:\n{business.current_motion}\n\nWhat needs to happen next:\n{business.next_move}\n\n{business.url}",
    ]
    return templates[angle_index % len(templates)]


def posted_fingerprints() -> set[str]:
    if not LEDGER_PATH.exists():
        return set()
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    statuses = {
        "posted",
        "scheduled",
        "queued",
        "claimed",
        "deferred_recent_related_post",
    }
    return {
        item["fingerprint"]
        for item in ledger.get("items", [])
        if item.get("fingerprint") and item.get("status") in statuses
    }


def render_queue(target: date, index_path: Path) -> dict[str, object]:
    existing = posted_fingerprints()
    businesses = parse_active_portfolio(index_path)
    items = []
    for offset, business in enumerate(businesses):
        angle_index = (target.toordinal() + offset) % 5
        x = x_copy(business, angle_index)
        linkedin = linkedin_copy(business, angle_index)
        item_id = f"portfolio-daily-{target.isoformat()}-{slugify(business.name)}"
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
                        "fingerprint": fingerprint(x),
                        "duplicate": fingerprint(x) in existing,
                    },
                    "linkedin": {
                        "profile": LINKEDIN_PROFILE,
                        "copy": linkedin,
                        "fingerprint": fingerprint(linkedin),
                        "duplicate": fingerprint(linkedin) in existing,
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
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD date for deterministic queue generation")
    parser.add_argument("--index", default=str(DEFAULT_INDEX), help="path to foundry-business-index.md")
    parser.add_argument("--no-ledger", action="store_true", help="write queue without upserting social-post-ledger.json")
    args = parser.parse_args()

    target = date.fromisoformat(args.date) if args.date else date.today()
    index_path = Path(args.index).expanduser()
    queue = render_queue(target, index_path)
    QUEUE_PATH.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
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
