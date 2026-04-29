#!/usr/bin/env python3
"""
Generate X-ready AI stats/facts/memes from Foundry research without repeats.

Default mode is draft-only. Live posting is intentionally gated by environment
and by a verified expected X handle so a stale browser session cannot post from
the wrong account.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent.parent
LEDGER_PATH = REPO / "marketing" / "x-ai-stat-bot-ledger.json"
OUTBOX_PATH = REPO / "marketing" / "x-ai-stat-bot-outbox.json"
LOG_PATH = REPO / "marketing" / "x-ai-stat-bot.log"
STATE_PATH = REPO / "marketing" / "x-ai-stat-bot-state.json"
SOCIAL_LEDGER_PATH = REPO / "marketing" / "social-post-ledger.json"

DEFAULT_ACCOUNT = "@8bitconcepts"
MIN_MINUTES = 29
MAX_MINUTES = 114
MAX_POST_CHARS = 240
LOCAL_TZ = ZoneInfo("America/Los_Angeles")
QUIET_START_HOUR = 23
QUIET_END_HOUR = 5
POSTABLE_STATUSES = {"reserved", "drafted", "queued", "scheduled", "posted"}

UA = "8bitconcepts-x-ai-stat-bot/1.0 (+https://8bitconcepts.com)"


@dataclass(frozen=True)
class Candidate:
    kind: str
    source: str
    source_url: str
    fact_id: str
    text: str
    route: str
    weight: int = 1

    @property
    def fact_key(self) -> str:
        raw = f"{self.kind}|{self.source_url}|{self.fact_id}|{canonical_fact(self.text)}"
        return digest(raw, 24)


STATIC_FACTS = [
    Candidate(
        kind="stat",
        source="8bitconcepts MCP Ecosystem Health",
        source_url="https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html",
        fact_id="mcp-verified-share-2026-04-27",
        text="7,040 agent-ready sites were indexed, but only 407 passed a live JSON-RPC MCP handshake. That is 5.8%.",
        route="https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html",
        weight=5,
    ),
    Candidate(
        kind="stat",
        source="8bitconcepts MCP Ecosystem Health",
        source_url="https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html",
        fact_id="llms-txt-share-2026-04-27",
        text="5,027 of 7,040 agent-ready sites publish llms.txt. The easier discovery file is winning; live MCP is still the bottleneck.",
        route="https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html",
        weight=4,
    ),
    Candidate(
        kind="stat",
        source="8bitconcepts MCP Ecosystem Health",
        source_url="https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html",
        fact_id="developer-tools-mcp-category",
        text="Developer tools account for 1,672 agent-ready sites, 23.8% of the indexed MCP/agent-ready web.",
        route="https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html",
        weight=3,
    ),
    Candidate(
        kind="stat",
        source="AI Dev Board Hiring Snapshot",
        source_url="https://8bitconcepts.com/research/q2-2026-ai-hiring-snapshot.html",
        fact_id="ai-jobs-total-2026-04-27",
        text="The AI Dev Board index had 9,161 AI/ML roles across 524 companies on 2026-04-27.",
        route="https://8bitconcepts.com/research/q2-2026-ai-hiring-snapshot.html",
        weight=4,
    ),
    Candidate(
        kind="stat",
        source="AI Dev Board Hiring Snapshot",
        source_url="https://8bitconcepts.com/research/q2-2026-ai-hiring-snapshot.html",
        fact_id="ai-jobs-salary-median-2026-04-27",
        text="The median advertised salary across salary-disclosed AI/ML roles was $212,500.",
        route="https://8bitconcepts.com/research/q2-2026-ai-hiring-snapshot.html",
        weight=4,
    ),
    Candidate(
        kind="stat",
        source="AI Compensation by Skill",
        source_url="https://8bitconcepts.com/research/q2-2026-ai-compensation-by-skill.html",
        fact_id="research-premium-vs-genai",
        text="Research AI roles averaged $273,880, while generative-AI roles averaged $230,707 despite having about 2.5x more openings.",
        route="https://8bitconcepts.com/research/q2-2026-ai-compensation-by-skill.html",
        weight=4,
    ),
    Candidate(
        kind="stat",
        source="Remote vs Onsite AI Hiring",
        source_url="https://8bitconcepts.com/research/q2-2026-remote-vs-onsite-ai-hiring.html",
        fact_id="hybrid-premium-2026-04-27",
        text="Hybrid AI/ML roles averaged $253,469, while remote roles averaged $218,273 and onsite roles averaged $216,846.",
        route="https://8bitconcepts.com/research/q2-2026-remote-vs-onsite-ai-hiring.html",
        weight=4,
    ),
    Candidate(
        kind="stat",
        source="Entry-Level AI Gap",
        source_url="https://8bitconcepts.com/research/q2-2026-entry-level-ai-gap.html",
        fact_id="junior-share-2026-04-27",
        text="Only 6.6% of classified AI/ML roles were entry-level. Senior, lead, and principal roles made up 67%.",
        route="https://8bitconcepts.com/research/q2-2026-entry-level-ai-gap.html",
        weight=4,
    ),
    Candidate(
        kind="field_note",
        source="8bitconcepts Integration Tax",
        source_url="https://8bitconcepts.com/research/the-integration-tax.html",
        fact_id="model-api-cost-share",
        text="Model API costs are usually the easy 10-20%. The expensive part is permissions, evals, workflow redesign, observability, and the last mile into existing systems.",
        route="https://8bitconcepts.com/research/the-integration-tax.html",
        weight=3,
    ),
    Candidate(
        kind="meme",
        source="8bitconcepts Integration Tax",
        source_url="https://8bitconcepts.com/research/the-integration-tax.html",
        fact_id="token-budget-meme",
        text="AI project budget, before launch: tokens. AI project budget, after launch: permissions, evals, workflow, observability, retries, owners, rollback plans, and one cursed CSV export.",
        route="https://8bitconcepts.com/research/the-integration-tax.html",
        weight=2,
    ),
    Candidate(
        kind="field_note",
        source="8bitconcepts Context Wall",
        source_url="https://8bitconcepts.com/research/the-context-wall.html",
        fact_id="context-infra",
        text="The hard part of agent work is rarely the prompt. It is giving the agent the operating context a senior teammate already has in their head.",
        route="https://8bitconcepts.com/research/the-context-wall.html",
        weight=3,
    ),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def normalize_text(value: str) -> str:
    return " ".join(html.unescape(value).lower().split())


def canonical_fact(value: str) -> str:
    normalized = normalize_text(value)
    normalized = re.sub(r"https?://\\S+", "", normalized)
    normalized = re.sub(r"[$,]", "", normalized)
    return normalized.strip()


def copy_fingerprint(value: str) -> str:
    return digest(normalize_text(value), 16)


def x_weighted_length(value: str) -> int:
    # X currently counts each URL as a fixed-length t.co link. Generated posts
    # are linkless by default, but keep this correct for manually routed copy.
    collapsed = re.sub(r"https?://\S+", "x" * 23, value)
    return len(collapsed)


def http_json(url: str, timeout: float = 10) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_text(url: str, timeout: float = 10) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def live_candidates() -> list[Candidate]:
    candidates: list[Candidate] = []

    try:
        stats = http_json("https://aidevboard.com/api/v1/stats")
        overview = stats.get("overview", stats)
        total_jobs = int(overview.get("total_jobs") or stats.get("total_jobs") or 0)
        companies = int(overview.get("total_companies") or stats.get("total_companies") or 0)
        if total_jobs and companies:
            candidates.append(
                Candidate(
                    kind="live_stat",
                    source="AI Dev Board live stats",
                    source_url="https://aidevboard.com/api/v1/stats",
                    fact_id=f"adb-total-jobs-{total_jobs}-companies-{companies}",
                    text=f"AI Dev Board is tracking {total_jobs:,} AI/ML roles across {companies:,} companies right now.",
                    route="https://aidevboard.com",
                    weight=3,
                )
            )
    except Exception as exc:  # noqa: BLE001
        log(f"live source failed aidevboard stats: {exc}")

    try:
        stats = http_json("https://nothumansearch.ai/api/v1/stats")
        total_sites = int(stats.get("total_sites") or stats.get("sites") or 0)
        avg_score = stats.get("avg_score") or stats.get("average_score")
        if total_sites:
            score_text = f" Average agent-readiness score: {float(avg_score):.1f}/100." if avg_score else ""
            candidates.append(
                Candidate(
                    kind="live_stat",
                    source="Not Human Search live stats",
                    source_url="https://nothumansearch.ai/api/v1/stats",
                    fact_id=f"nhs-total-sites-{total_sites}-avg-{avg_score}",
                    text=f"Not Human Search is tracking {total_sites:,} agent-ready sites.{score_text}",
                    route="https://nothumansearch.ai",
                    weight=3,
                )
            )
    except Exception as exc:  # noqa: BLE001
        log(f"live source failed nhs stats: {exc}")

    try:
        digest_json = http_json("https://nothumansearch.ai/digest.json")
        verified = int(digest_json.get("verified_mcp_count") or digest_json.get("mcp_verified") or 0)
        total = int(digest_json.get("total_sites") or digest_json.get("agent_ready_sites") or 0)
        if total and verified:
            pct = (verified / total) * 100
            candidates.append(
                Candidate(
                    kind="live_stat",
                    source="Not Human Search digest",
                    source_url="https://nothumansearch.ai/digest.json",
                    fact_id=f"nhs-mcp-verified-{verified}-total-{total}",
                    text=f"Live MCP check: {verified:,} of {total:,} agent-ready sites pass a real MCP handshake. That is {pct:.1f}%.",
                    route="https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html",
                    weight=4,
                )
            )
    except Exception as exc:  # noqa: BLE001
        log(f"live source failed nhs digest: {exc}")

    return candidates


def news_candidates(limit: int = 10) -> list[Candidate]:
    url = (
        "https://news.google.com/rss/search?q="
        "AI%20OR%20%22AI%20agents%22%20OR%20OpenAI%20OR%20Anthropic%20OR%20MCP"
        "&hl=en-US&gl=US&ceid=US:en"
    )
    candidates: list[Candidate] = []
    try:
        xml = http_text(url, timeout=10)
        root = ET.fromstring(xml)
        for item in root.findall(".//item")[:limit]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue
            title = re.sub(r"\\s+-\\s+[^-]+$", "", html.unescape(title)).strip()
            if not re.search(r"\\b(ai|openai|anthropic|agent|mcp|llm|model)\\b", title, re.I):
                continue
            candidates.append(
                Candidate(
                    kind="news",
                    source="Google News AI RSS",
                    source_url=link,
                    fact_id=digest(title, 16),
                    text=f"AI news watch: {title}",
                    route="https://8bitconcepts.com/research/",
                    weight=1,
                )
            )
    except Exception as exc:  # noqa: BLE001
        log(f"news source failed: {exc}")
    return candidates


def all_candidates(include_news: bool) -> list[Candidate]:
    items = list(STATIC_FACTS)
    items.extend(live_candidates())
    if include_news:
        items.extend(news_candidates())
    return items


def load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def load_ledger() -> dict[str, Any]:
    return load_json(
        LEDGER_PATH,
        {
            "schema": 1,
            "rule": "Never post or queue the same canonical fact/snippet twice. fact_key blocks repeated facts; fingerprint blocks repeated wording.",
            "items": [],
        },
    )


def blocked_fact_keys(ledger: dict[str, Any]) -> set[str]:
    return {
        item.get("fact_key", "")
        for item in ledger.get("items", [])
        if item.get("fact_key")
    }


def blocked_fingerprints(ledger: dict[str, Any]) -> set[str]:
    blocked = {
        item.get("fingerprint", "")
        for item in ledger.get("items", [])
        if item.get("status") in POSTABLE_STATUSES and item.get("fingerprint")
    }
    if SOCIAL_LEDGER_PATH.exists():
        social = json.loads(SOCIAL_LEDGER_PATH.read_text(encoding="utf-8"))
        for item in social.get("items", []):
            if item.get("status") in {"posted", "scheduled", "queued"} and item.get("fingerprint"):
                blocked.add(item["fingerprint"])
    return blocked


def render_copy(candidate: Candidate) -> str:
    if candidate.kind == "meme":
        body = candidate.text
    elif candidate.kind == "news":
        body = f"{candidate.text}. The useful question is what becomes a real workflow."
    else:
        body = candidate.text
    return body


def choose_candidate(candidates: list[Candidate], ledger: dict[str, Any]) -> tuple[Candidate, str]:
    fact_keys = blocked_fact_keys(ledger)
    fingerprints = blocked_fingerprints(ledger)
    available: list[tuple[Candidate, str]] = []
    for candidate in candidates:
        copy = render_copy(candidate)
        fp = copy_fingerprint(copy)
        if x_weighted_length(copy) > MAX_POST_CHARS:
            continue
        if candidate.fact_key in fact_keys or fp in fingerprints:
            continue
        available.extend([(candidate, copy)] * max(1, candidate.weight))
    if not available:
        raise RuntimeError("no non-duplicate candidate available")
    return random.choice(available)


def reserve(candidate: Candidate, copy: str, mode: str) -> dict[str, Any]:
    ledger = load_ledger()
    fp = copy_fingerprint(copy)
    if candidate.fact_key in blocked_fact_keys(ledger):
        raise RuntimeError(f"duplicate fact_key blocked: {candidate.fact_key}")
    if fp in blocked_fingerprints(ledger):
        raise RuntimeError(f"duplicate fingerprint blocked: {fp}")

    item = {
        "id": f"x-ai-stat-{now_iso()}-{candidate.fact_key[:8]}",
        "status": "reserved" if mode == "live" else "drafted",
        "created_at": now_iso(),
        "channel": "x",
        "account": DEFAULT_ACCOUNT,
        "kind": candidate.kind,
        "source": candidate.source,
        "source_url": candidate.source_url,
        "route": candidate.route,
        "fact_id": candidate.fact_id,
        "fact_key": candidate.fact_key,
        "fingerprint": fp,
        "copy": copy,
    }
    ledger.setdefault("items", []).append(item)
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    return item


def append_outbox(item: dict[str, Any]) -> None:
    outbox = load_json(OUTBOX_PATH, {"schema": 1, "items": []})
    outbox.setdefault("items", []).append(item)
    OUTBOX_PATH.write_text(json.dumps(outbox, indent=2) + "\n", encoding="utf-8")


def update_item_status(item_id: str, status: str, **fields: Any) -> None:
    ledger = load_ledger()
    for item in ledger.get("items", []):
        if item.get("id") == item_id:
            item["status"] = status
            item["updated_at"] = now_iso()
            item.update(fields)
            break
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")


def current_x_handle() -> str | None:
    """Best-effort browser check for the visible Brave X account."""
    script = 'tell application "Brave Browser" to return URL of active tab of front window'
    try:
        url = subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True).stdout.strip()
        if not ("x.com/" in url or "twitter.com/" in url):
            return None
    except Exception:
        return None

    # The active account can be inferred from the Profile link URL when X is open.
    # Browser DOM access is intentionally not attempted here; unattended live
    # posting should use a dedicated posting command with its own account check.
    return os.environ.get("X_VISIBLE_HANDLE")


def post_live(item: dict[str, Any], expected_handle: str) -> str:
    if os.environ.get("X_BOT_LIVE") != "1":
        raise RuntimeError("live posting blocked: set X_BOT_LIVE=1 at action time")

    visible = current_x_handle()
    if visible and visible.lower().lstrip("@") != expected_handle.lower().lstrip("@"):
        raise RuntimeError(f"live posting blocked: visible X account is @{visible.lstrip('@')}, expected {expected_handle}")

    command = os.environ.get("X_POSTER_COMMAND")
    if not command:
        raise RuntimeError("live posting blocked: X_POSTER_COMMAND is not configured")

    proc = subprocess.run(
        [command, "--expected-handle", expected_handle, "--text", item["copy"]],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "X poster command failed")
    return proc.stdout.strip()


def run_once(args: argparse.Namespace) -> dict[str, Any]:
    candidates = all_candidates(include_news=not args.no_news)
    ledger = load_ledger()
    candidate, copy = choose_candidate(candidates, ledger)
    item = reserve(candidate, copy, args.mode)

    if args.mode == "live":
        try:
            url = post_live(item, args.expected_handle)
        except Exception:
            update_item_status(item["id"], "failed")
            raise
        update_item_status(item["id"], "posted", url=url, posted_at=now_iso())
        item["status"] = "posted"
        item["url"] = url
    else:
        append_outbox(item)

    return item


def log(message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"{now_iso()} {message}\n")


def write_state(**fields: Any) -> None:
    state = {
        "schema": 1,
        "updated_at": now_iso(),
        **fields,
    }
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def quiet_until(now: datetime) -> datetime | None:
    local = now.astimezone(LOCAL_TZ)
    if local.hour >= QUIET_START_HOUR:
        wake_local = (local + timedelta(days=1)).replace(hour=QUIET_END_HOUR, minute=0, second=0, microsecond=0)
        return wake_local.astimezone(timezone.utc)
    if local.hour < QUIET_END_HOUR:
        wake_local = local.replace(hour=QUIET_END_HOUR, minute=0, second=0, microsecond=0)
        return wake_local.astimezone(timezone.utc)
    return None


def next_run_after_random_delay(now: datetime, minutes: int) -> datetime:
    candidate = now + timedelta(minutes=minutes)
    quiet_end = quiet_until(candidate)
    return quiet_end or candidate


def daemon(args: argparse.Namespace) -> int:
    while True:
        now = datetime.now(timezone.utc)
        quiet_end = quiet_until(now)
        if quiet_end:
            sleep_seconds = max(1, int((quiet_end - now).total_seconds()))
            write_state(
                status="quiet_hours",
                mode=args.mode,
                account=args.expected_handle,
                min_minutes=args.min_minutes,
                max_minutes=args.max_minutes,
                quiet_hours_local=f"{QUIET_START_HOUR:02d}:00-{QUIET_END_HOUR:02d}:00",
                timezone=str(LOCAL_TZ),
                sleep_seconds=sleep_seconds,
                next_run_at=quiet_end.isoformat(timespec="seconds"),
            )
            log(f"quiet_hours next_run_at={quiet_end.isoformat(timespec='seconds')}")
            time.sleep(sleep_seconds)
            continue

        try:
            item = run_once(args)
            log(f"{args.mode} {item['id']} {item['fingerprint']} {item['source']}")
        except Exception as exc:  # noqa: BLE001
            log(f"ERROR {exc}")
        minutes = random.randint(args.min_minutes, args.max_minutes)
        now = datetime.now(timezone.utc)
        next_run = next_run_after_random_delay(now, minutes)
        sleep_seconds = max(1, int((next_run - now).total_seconds()))
        write_state(
            status="sleeping",
            mode=args.mode,
            account=args.expected_handle,
            min_minutes=args.min_minutes,
            max_minutes=args.max_minutes,
            random_minutes=minutes,
            sleep_seconds=sleep_seconds,
            next_run_at=next_run.isoformat(timespec="seconds"),
            quiet_hours_local=f"{QUIET_START_HOUR:02d}:00-{QUIET_END_HOUR:02d}:00",
            timezone=str(LOCAL_TZ),
        )
        log(f"random_minutes={minutes} next_run_at={next_run.isoformat(timespec='seconds')} sleep_seconds={sleep_seconds}")
        time.sleep(sleep_seconds)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["draft", "live"], default="draft")
    parser.add_argument("--daemon", action="store_true", help="Run forever with random sleep between posts/drafts")
    parser.add_argument("--min-minutes", type=int, default=MIN_MINUTES)
    parser.add_argument("--max-minutes", type=int, default=MAX_MINUTES)
    parser.add_argument("--expected-handle", default=DEFAULT_ACCOUNT)
    parser.add_argument("--no-news", action="store_true", help="Disable live news RSS source")
    args = parser.parse_args()

    if args.min_minutes < 1 or args.max_minutes < args.min_minutes:
        parser.error("invalid minute range")

    if args.daemon:
        return daemon(args)

    item = run_once(args)
    print(json.dumps(item, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
