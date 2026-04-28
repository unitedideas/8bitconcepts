#!/usr/bin/env python3
"""
Generate the twice-daily 8bitconcepts AI insight queue.

The cadence is deliberately broad, but every post teaches something concrete,
uses a rotating format, and routes back to an 8bitconcepts / Foundry proof
point without hard selling.

Usage:
  python3 tools/generate-daily-ai-insights.py
  python3 tools/generate-daily-ai-insights.py --date 2026-04-27
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_PATH = REPO / "marketing" / "daily-ai-insights.md"
QUEUE_PATH = REPO / "marketing" / "daily-ai-insights-queue.json"
LEDGER_PATH = REPO / "marketing" / "social-post-ledger.json"
X_ACCOUNT = "@8bitconcepts"
LINKEDIN_PROFILE = "https://www.linkedin.com/in/shane-cheek-9173473b6/"
POST_TIMES_LOCAL = {"morning": "08:30", "afternoon": "14:30"}


TOPICS = [
    {
        "theme": "Agent readiness is a live behavior, not a badge.",
        "route": "https://nothumansearch.ai",
        "offering": "agent-readiness audits and Not Human Search",
        "format": "mini teardown",
        "asset": "Three-column table: claim, endpoint response, what broke.",
        "morning": "The next AI SEO problem is verification. A site can publish llms.txt, OpenAPI, and an MCP badge and still fail the first live handshake. Agents need endpoints, not claims.",
        "afternoon": "A useful agent-readiness audit has three columns: what the site claims, what the endpoint returns, and what breaks under a real request. The gap is usually where the work is.",
    },
    {
        "theme": "AI hiring signals are harder to fake than job titles.",
        "route": "https://aidevboard.com",
        "offering": "AI Dev Board hiring data",
        "format": "data point",
        "asset": "Small bar chart: title keywords vs. stack signals.",
        "morning": "AI hiring data gets noisy when every backend role adds 'LLM' to the description. The cleaner signal is the stack: evals, inference, RLHF, retrieval, agents, and data infrastructure.",
        "afternoon": "The best AI hiring filter I have seen is proof of work. Deployed agents, eval harnesses, MCP servers, and boring operational reliability beat a resume full of model names.",
    },
    {
        "theme": "Prompt quality stops compounding without memory.",
        "route": "https://8bitconcepts.com/research/",
        "offering": "embedded AI operating systems",
        "format": "think piece",
        "asset": "Simple diagram: prompt -> run -> lesson -> expertise file -> next run.",
        "morning": "A prompt that never learns becomes a tax. The useful pattern is a small expertise file per agent: what surprised it, what it got wrong, and which local rules actually mattered.",
        "afternoon": "The mistake is treating agent instructions like a constitution. Most of them are lab notes. They need revision, pruning, and evidence from real runs.",
    },
    {
        "theme": "Hooks beat rules when failure is expensive.",
        "route": "https://8bitconcepts.com/research/",
        "offering": "agent workflow hardening",
        "format": "field note",
        "asset": "Before/after: paragraph reminder vs. hook that blocks the bad action.",
        "morning": "Every agent rule has a half-life under context pressure. If the failure matters, move it out of the prompt and into a hook, test, or guardrail the agent cannot talk its way around.",
        "afternoon": "A good agent safety rule starts with a real incident and ends as code. If it only lives in a paragraph, it is still a reminder, not a control.",
    },
    {
        "theme": "Autonomous loops fail silently before they fail loudly.",
        "route": "https://8bitconcepts.com/case-studies.html",
        "offering": "production agent ops",
        "format": "infographic",
        "asset": "Checklist graphic: heartbeat, freshness deadline, lock age, last output, alert path.",
        "morning": "The dangerous failure mode in autonomous agents is absence: no heartbeat, no fresh state, no new log line, no notification. Error handling catches noise. Freshness checks catch silence.",
        "afternoon": "A production agent loop needs a status file before it needs another model upgrade. 'What is it doing now?' has to be machine-answerable.",
    },
    {
        "theme": "AI ROI hides in integration, not inference.",
        "route": "https://8bitconcepts.com/research/the-integration-tax.html",
        "offering": "AI integration audits",
        "format": "meme",
        "asset": "Two-panel meme: 'we budgeted for tokens' vs. 'permissions, evals, workflow, observability'.",
        "morning": "Model cost is the easy line item. The real AI budget goes to data plumbing, permissions, evals, observability, workflow redesign, and the last mile into the system people already use.",
        "afternoon": "If an AI project budget starts with token costs, it is probably missing the hard part. The question is not 'what does the model cost?' It is 'what has to change around it?'",
    },
]


def pick_topics(target: date) -> tuple[dict[str, str], dict[str, str]]:
    day_index = target.toordinal()
    morning = TOPICS[day_index % len(TOPICS)]
    afternoon = TOPICS[(day_index + 3) % len(TOPICS)]
    return morning, afternoon


def fingerprint(text: str) -> str:
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def posted_fingerprints() -> set[str]:
    if not LEDGER_PATH.exists():
        return set()
    data = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    return {
        item["fingerprint"]
        for item in data.get("items", [])
        if item.get("status") in {"posted", "scheduled", "queued"}
    }


def render_post(kind: str, topic: dict[str, str], body_key: str) -> str:
    body = topic[body_key]
    route = topic["route"]
    slot = "morning" if body_key == "morning" else "afternoon"
    return f"""### {kind}

Post time: {POST_TIMES_LOCAL[slot]} America/Los_Angeles
Theme: {topic["theme"]}
Format: {topic["format"]}
Route: {route}
Funnel: {topic["offering"]}
Asset brief: {topic["asset"]}

#### X

```text
{body}

More field notes: {route}
```

#### LinkedIn

```text
{body}

The useful question for operators is what changes in the system around the model: state, workflow, evals, policy, and feedback loops.

More field notes:
{route}
```
"""


def queue_item(target: date, slot: str, topic: dict[str, str]) -> dict[str, object]:
    body = topic[slot]
    route = topic["route"]
    x_copy = f"{body}\n\nMore field notes: {route}"
    linkedin_copy = f"{body}\n\nThe useful question for operators is what changes in the system around the model: state, workflow, evals, policy, and feedback loops.\n\nMore field notes:\n{route}"
    existing = posted_fingerprints()
    x_fingerprint = fingerprint(x_copy)
    linkedin_fingerprint = fingerprint(linkedin_copy)
    return {
        "id": f"daily-ai-insight-{target.isoformat()}-{slot}",
        "date": target.isoformat(),
        "slot": slot,
        "post_time_local": POST_TIMES_LOCAL[slot],
        "timezone": "America/Los_Angeles",
        "theme": topic["theme"],
        "format": topic["format"],
        "asset_brief": topic["asset"],
        "route": route,
        "funnel": topic["offering"],
        "channels": {
            "x": {
                "account": X_ACCOUNT,
                "copy": x_copy,
                "fingerprint": x_fingerprint,
                "duplicate": x_fingerprint in existing,
            },
            "linkedin": {
                "profile": LINKEDIN_PROFILE,
                "copy": linkedin_copy,
                "fingerprint": linkedin_fingerprint,
                "duplicate": linkedin_fingerprint in existing,
            },
        },
        "quality_gate": [
            "AI topic",
            "teaches one specific thing",
            "routes to a proof point",
            "not sales-first",
            "has a click/comment trigger",
        ],
    }


def render(target: date) -> str:
    morning, afternoon = pick_topics(target)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""# Daily AI Insight Drafts

Generated: {generated}
Post date: {target.isoformat()}
X account: {X_ACCOUNT}
LinkedIn profile: {LINKEDIN_PROFILE}

Rule: two posts per day, always AI, always informative, always routed to an 8bitconcepts / Foundry proof point, never sales-first.

{render_post("Morning Post", morning, "morning")}
{render_post("Afternoon Post", afternoon, "afternoon")}
Machine queue: `marketing/daily-ai-insights-queue.json`

## Operator Checklist

- Claim first. No "new post" framing.
- Teach one thing specific.
- Route to methodology, data, or a working artifact.
- Avoid "book a call" unless the post is explicitly about applying the pattern.
- Rotate formats: data point, teardown, field note, infographic, meme, poll, thread, or short think piece.
- If using Hacker News, submit only technical systems artifacts from the `8bitconcepts` account.
"""


def render_queue(target: date) -> dict[str, object]:
    morning, afternoon = pick_topics(target)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "account_policy": {
            "x": X_ACCOUNT,
            "linkedin": LINKEDIN_PROFILE,
            "hacker_news": "8bitconcepts; only for technical systems artifacts",
        },
        "cadence": "two AI insight posts per day",
        "items": [
            queue_item(target, "morning", morning),
            queue_item(target, "afternoon", afternoon),
        ],
    }


def upsert_queued_items(queue: dict[str, object]) -> None:
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
    for queue_item_data in queue["items"]:
        for channel, channel_data in queue_item_data["channels"].items():
            item_id = f"{queue_item_data['id']}-{channel}"
            existing = by_id.get(item_id)
            if existing and existing.get("status") == "posted":
                continue
            record = {
                "id": item_id,
                "source": "marketing/daily-ai-insights-queue.json",
                "channel": channel,
                "account": channel_data.get("account") or channel_data.get("profile"),
                "status": "queued",
                "date": queue_item_data["date"],
                "post_time_local": queue_item_data["post_time_local"],
                "fingerprint": channel_data["fingerprint"],
                "route": queue_item_data["route"],
                "format": queue_item_data["format"],
                "note": "Generated by tools/generate-daily-ai-insights.py; update to posted with URL after publication.",
            }
            if existing:
                existing.update(record)
            else:
                items.append(record)

    LEDGER_PATH.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD date for deterministic topic rotation")
    args = parser.parse_args()

    target = date.fromisoformat(args.date) if args.date else date.today()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(render(target), encoding="utf-8")
    queue = render_queue(target)
    QUEUE_PATH.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    upsert_queued_items(queue)
    print(f"wrote {OUT_PATH}")
    print(f"wrote {QUEUE_PATH}")
    print(f"updated {LEDGER_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
