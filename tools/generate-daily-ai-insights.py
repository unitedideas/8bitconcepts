#!/usr/bin/env python3
"""
Generate the daily 8bitconcepts AI insight queue.

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

from targeted_research import (
    build_target_research,
    render_targeted_research_post,
    targeted_queue_item,
)

REPO = Path(__file__).resolve().parent.parent
OUT_PATH = REPO / "marketing" / "daily-ai-insights.md"
QUEUE_PATH = REPO / "marketing" / "daily-ai-insights-queue.json"
LEDGER_PATH = REPO / "marketing" / "social-post-ledger.json"
X_ACCOUNT = "@8bitconcepts"
LINKEDIN_PROFILE = "https://www.linkedin.com/in/shane-cheek-9173473b6/"
POST_TIMES_LOCAL = {
    "targeted": "08:30",
    "8bit": "10:30",
    "nhs": "12:30",
    "bya": "14:30",
    "adb": "16:30",
}


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


RESEARCH_FACTS = [
    {
        "product": "8bit",
        "theme": "AI integration budgets",
        "route": "https://8bitconcepts.com/research/the-integration-tax.html",
        "funnel": "8bitconcepts research",
        "format": "little fact",
        "asset": "Cost stack: data, integration, evals, observability, maintenance, model fees.",
        "fact_key": "8bit:integration-tax:model-cost-10-20",
        "x": "Little fact from the 8bit research stack: model API fees are usually 10-20% of the AI build cost. The rest is data plumbing, integration, evals, observability, and maintenance.",
        "linkedin": "Little fact from the 8bit research stack: model API fees are usually 10-20% of an AI build. The bigger lines are data pipelines, system integration, evaluation, observability, and maintenance.\n\nThat is why the budget conversation has to happen before the model-choice conversation.",
    },
    {
        "product": "8bit",
        "theme": "Shift handoff intelligence",
        "route": "https://8bitconcepts.com/research/shift-handoff-intelligence.html",
        "funnel": "8bitconcepts research",
        "format": "little fact",
        "asset": "Handoff comparison: digital capture vs verbal retention.",
        "fact_key": "8bit:shift-handoff:100-vs-40-60",
        "x": "Little fact from the shift-handoff paper: the digital scenario retained 100% of prior-shift entries; the modeled verbal handoff retained 40-60%. The lost category is usually the early warning.",
        "linkedin": "Little fact from the shift-handoff paper: the digital scenario retained 100% of prior-shift entries; the modeled verbal handoff retained 40-60%.\n\nThe dangerous loss is not the obvious critical issue. It is the developing trend that is not urgent yet.",
    },
    {
        "product": "nhs",
        "theme": "Live MCP verification",
        "route": "https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html",
        "funnel": "Not Human Search research",
        "format": "little fact",
        "asset": "MCP claim vs live JSON-RPC handshake.",
        "fact_key": "nhs:mcp-ecosystem:7118-417",
        "x": "Little fact from the NHS MCP audit: the index had 7,118 agent-ready sites, but 417 passed the live JSON-RPC MCP handshake. A manifest is not the same as a callable endpoint.",
        "linkedin": "Little fact from the NHS MCP audit: the index had 7,118 agent-ready sites, but 417 passed the live JSON-RPC MCP handshake.\n\nThat gap matters. Agents need a callable endpoint, not a badge or a static manifest.",
    },
    {
        "product": "nhs",
        "theme": "Greenfield MCP verticals",
        "route": "https://8bitconcepts.com/research/q2-2026-mcp-ecosystem-health.html",
        "funnel": "Not Human Search research",
        "format": "little fact",
        "asset": "Vertical maturity: finance, health, education.",
        "fact_key": "nhs:mcp-verticals:finance-health-education",
        "x": "Little fact from the NHS MCP audit: developer tools had 1,686 indexed sites. Health had 72. Education had 28. The agent ecosystem is crowded in tools and thin in regulated verticals.",
        "linkedin": "Little fact from the NHS MCP audit: developer tools had 1,686 indexed sites. Health had 72. Education had 28.\n\nThe agent ecosystem is crowded around tools and still thin in regulated verticals where the workflow value is high.",
    },
    {
        "product": "bya",
        "theme": "Local-first agent migration",
        "route": "https://8bitconcepts.com/case-studies.html#bringyour",
        "funnel": "Bring Your AI proof point",
        "format": "little fact",
        "asset": "Privacy boundary: remote discovery, local movement.",
        "fact_key": "bya:case-study:no-data-remote-mcp",
        "x": "Little fact from the BYA case study: the remote MCP surface has 4 tools and accepts no harness files, GitHub handles, generated memories, API keys, or file contents. The actual move runs locally.",
        "linkedin": "Little fact from the BYA case study: the remote MCP surface has 4 tools and accepts no harness files, GitHub handles, generated memories, API keys, or file contents.\n\nThe product boundary is the point: discovery can happen through an agent surface, but private context moves locally.",
    },
    {
        "product": "bya",
        "theme": "On-device inference",
        "route": "https://8bitconcepts.com/research/on-device-inference.html",
        "funnel": "Bring Your AI research path",
        "format": "little fact",
        "asset": "Local inference as a privacy and cost boundary.",
        "fact_key": "bya:on-device:local-context",
        "x": "Little fact from the local-inference paper: the best model without local context can be worse than a smaller model next to the data. The useful system knows when to stay local.",
        "linkedin": "Little fact from the local-inference paper: the best model without local context can be worse than a smaller model next to the data.\n\nFor agent tooling, that is the same product boundary BYA uses: keep private working context on the user's machine unless there is a real reason to move it.",
    },
    {
        "product": "adb",
        "theme": "AI workplace premium",
        "route": "https://8bitconcepts.com/research/q2-2026-remote-vs-onsite-ai-hiring.html",
        "funnel": "AI Dev Board research",
        "format": "little fact",
        "asset": "Workplace mix and salary bands.",
        "fact_key": "adb:remote-vs-onsite:hybrid-253469",
        "x": "Little fact from the ADB hiring data: hybrid AI/ML roles averaged $253,469, ahead of remote at $218,273 and onsite at $216,846 across 9,161 classified roles.",
        "linkedin": "Little fact from the ADB hiring data: hybrid AI/ML roles averaged $253,469, ahead of remote at $218,273 and onsite at $216,846 across 9,161 classified roles.\n\nThe practical read is that hybrid concentrates seniority and major-metro salary bands.",
    },
    {
        "product": "adb",
        "theme": "AI skill demand",
        "route": "https://8bitconcepts.com/research/q2-2026-ai-compensation-by-skill.html",
        "funnel": "AI Dev Board research",
        "format": "little fact",
        "asset": "Skill demand vs salary.",
        "fact_key": "adb:skills:agents-2437",
        "x": "Little fact from the ADB skill data: agents appeared in 2,437 indexed roles, but distributed-systems paid higher on average: $252,318 vs $229,919.",
        "linkedin": "Little fact from the ADB skill data: agents appeared in 2,437 indexed roles, but distributed-systems paid higher on average: $252,318 vs $229,919.\n\nVolume and negotiating leverage are not the same signal.",
    },
]


def pick_topics(target: date) -> tuple[dict[str, str], dict[str, str]]:
    day_index = target.toordinal()
    morning = TOPICS[day_index % len(TOPICS)]
    afternoon = TOPICS[(day_index + 3) % len(TOPICS)]
    return morning, afternoon


def pick_research_facts(target: date) -> list[dict[str, str]]:
    day_index = target.toordinal()
    facts_by_product: dict[str, list[dict[str, str]]] = {}
    for fact in RESEARCH_FACTS:
        facts_by_product.setdefault(fact["product"], []).append(fact)

    selected: list[dict[str, str]] = []
    for offset, product in enumerate(("8bit", "nhs", "bya", "adb")):
        product_facts = facts_by_product[product]
        selected.append(product_facts[(day_index + offset) % len(product_facts)])
    return selected


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
        if item.get("status") in {"posted", "scheduled", "queued", "claimed", "deferred_recent_related_post"}
    }


def posted_fact_keys(within_days: int = 14) -> set[str]:
    """Fact keys already posted (or queued/scheduled) on any channel within the window.

    Catches the social-editor-rewords-same-fact case that fingerprint dedupe misses:
    if the same fact_key (e.g. "targeted-research:anthropic:283:...") has a posted
    entry in the ledger, the same fact must not be re-queued today regardless of
    how the copy is reworded.
    """
    if not LEDGER_PATH.exists():
        return set()
    data = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    cutoff = datetime.now(timezone.utc).timestamp() - (within_days * 86400)
    keys: set[str] = set()
    for item in data.get("items", []):
        fk = item.get("fact_key")
        if not fk:
            continue
        if item.get("status") not in {"posted", "scheduled", "queued", "claimed"}:
            continue
        ts = item.get("posted_at") or item.get("scheduled_at") or ""
        if ts:
            try:
                if datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() < cutoff:
                    continue
            except ValueError:
                pass
        keys.add(fk)
    return keys


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


def render_research_fact_post(fact: dict[str, str]) -> str:
    slot = fact["product"]
    post_time = POST_TIMES_LOCAL[slot]
    return f"""### {fact["product"].upper()} Research Fact

Post time: {post_time} America/Los_Angeles
Theme: {fact["theme"]}
Format: {fact["format"]}
Route: {fact["route"]}
Funnel: {fact["funnel"]}
Asset brief: {fact["asset"]}
Fact key: {fact["fact_key"]}

#### X

```text
{fact["x"]}

Source: {fact["route"]}
```

#### LinkedIn

```text
{fact["linkedin"]}

Source:
{fact["route"]}
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
        "kind": "generic_insight",
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


def research_fact_queue_item(
    target: date,
    fact: dict[str, str],
    existing_fingerprints: set[str],
) -> dict[str, object]:
    slot = fact["product"]
    route = fact["route"]
    x_copy = f"{fact['x']}\n\nSource: {route}"
    linkedin_copy = f"{fact['linkedin']}\n\nSource:\n{route}"
    x_fingerprint = fingerprint(x_copy)
    linkedin_fingerprint = fingerprint(linkedin_copy)
    return {
        "id": f"daily-research-fact-{target.isoformat()}-{slot}",
        "kind": "research_fact",
        "date": target.isoformat(),
        "slot": slot,
        "post_time_local": POST_TIMES_LOCAL[slot],
        "timezone": "America/Los_Angeles",
        "product": fact["product"],
        "theme": fact["theme"],
        "format": fact["format"],
        "asset_brief": fact["asset"],
        "route": route,
        "funnel": fact["funnel"],
        "fact_key": fact["fact_key"],
        "research_sources": [route],
        "channels": {
            "x": {
                "account": X_ACCOUNT,
                "copy": x_copy,
                "fingerprint": x_fingerprint,
                "duplicate": x_fingerprint in existing_fingerprints,
            },
            "linkedin": {
                "profile": LINKEDIN_PROFILE,
                "copy": linkedin_copy,
                "fingerprint": linkedin_fingerprint,
                "duplicate": linkedin_fingerprint in existing_fingerprints,
            },
        },
        "quality_gate": [
            "one small verified fact",
            "source-backed by 8bit research or case-study page",
            "routes to the relevant product or paper",
            "no sales-first CTA",
            "materially different fact_key from previous posts",
        ],
    }


def render(target: date) -> str:
    targeted = build_target_research(target)
    facts = pick_research_facts(target)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""# Daily AI Insight Drafts

Generated: {generated}
Post date: {target.isoformat()}
X account: {X_ACCOUNT}
LinkedIn profile: {LINKEDIN_PROFILE}

Rule: multiple posts per day, always AI, always informative, always routed to an 8bitconcepts / Foundry proof point, never sales-first. Each daily run includes one documented target/company/person research post plus four small research facts across 8bit, NHS, BYA, and ADB.

{render_targeted_research_post(targeted, POST_TIMES_LOCAL["targeted"])}
{"".join(render_research_fact_post(fact) for fact in facts)}
Machine queue: `marketing/daily-ai-insights-queue.json`

## Operator Checklist

- Claim first. No "new post" framing.
- Teach one thing specific.
- Route to methodology, data, or a working artifact.
- For the morning post, use the target mention/tag naturally and never as a dunk or negative callout.
- For research facts, keep the post to one claim and one source link.
- Refresh stale stats before posting old drafts.
- If the morning research flags a paper trigger, draft the paper before the next recurring distribution run.
"""


def render_queue(target: date) -> dict[str, object]:
    targeted = build_target_research(target)
    existing = posted_fingerprints()
    fact_items = [
        research_fact_queue_item(target, fact, existing)
        for fact in pick_research_facts(target)
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "account_policy": {
            "x": X_ACCOUNT,
            "linkedin": LINKEDIN_PROFILE,
            "hacker_news": "8bitconcepts; only for technical systems artifacts",
        },
        "cadence": "five AI insight posts per day; one targeted documented research post plus four rotating research facts across 8bit, NHS, BYA, and ADB",
        "items": [
            targeted_queue_item(target, targeted, existing, POST_TIMES_LOCAL["targeted"]),
            *fact_items,
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
    recent_fact_keys = posted_fact_keys()
    for queue_item_data in queue["items"]:
        item_fact_key = queue_item_data.get("fact_key")
        for channel, channel_data in queue_item_data["channels"].items():
            item_id = f"{queue_item_data['id']}-{channel}"
            existing = by_id.get(item_id)
            if existing and existing.get("status") in preserve_statuses:
                continue
            fact_already_posted = bool(item_fact_key and item_fact_key in recent_fact_keys)
            status_for_record = "deferred_recent_related_post" if fact_already_posted else "queued"
            record = {
                "id": item_id,
                "source": "marketing/daily-ai-insights-queue.json",
                "channel": channel,
                "account": channel_data.get("account") or channel_data.get("profile"),
                "status": status_for_record,
                "date": queue_item_data["date"],
                "post_time_local": queue_item_data["post_time_local"],
                "fingerprint": channel_data["fingerprint"],
                "fact_key": queue_item_data.get("fact_key"),
                "route": queue_item_data["route"],
                "format": queue_item_data["format"],
                "target": queue_item_data.get("target"),
                "research_sources": queue_item_data.get("research_sources"),
                "note": ("Fact key already posted within 14d; deferred to avoid duplicate."
                         if fact_already_posted
                         else "Generated by tools/generate-daily-ai-insights.py; update to posted with URL after publication."),
            }
            if existing:
                existing.update(record)
            else:
                items.append(record)

    LEDGER_PATH.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD date for deterministic topic rotation")
    parser.add_argument("--no-ledger", action="store_true", help="write drafts/queue without upserting social-post-ledger.json")
    args = parser.parse_args()

    target = date.fromisoformat(args.date) if args.date else date.today()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(render(target), encoding="utf-8")
    queue = render_queue(target)
    QUEUE_PATH.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    if not args.no_ledger:
        upsert_queued_items(queue)
    print(f"wrote {OUT_PATH}")
    print(f"wrote {QUEUE_PATH}")
    if args.no_ledger:
        print(f"left {LEDGER_PATH} unchanged")
    else:
        print(f"updated {LEDGER_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
