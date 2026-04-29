#!/usr/bin/env python3
"""
Source-backed daily target research for 8bitconcepts social posts.

This module is imported by generate-daily-ai-insights.py. It deliberately uses
only public/live sources: AI Dev Board, Not Human Search, and official target
pages. The copy frames targets as useful public lenses, never as negative
callouts.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import statistics
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple
import urllib.parse
import urllib.request

USER_AGENT = "8bitconcepts-social-research/1.0 (+https://8bitconcepts.com)"
ADB_STATS_URL = "https://aidevboard.com/api/v1/stats"
ADB_JOBS_URL = "https://aidevboard.com/api/v1/jobs"
NHS_SITE_URL = "https://nothumansearch.ai/api/v1/site/{domain}"

X_ACCOUNT = "@8bitconcepts"
LINKEDIN_PROFILE = "https://www.linkedin.com/in/shane-cheek-9173473b6/"

Target = Dict[str, str]
JsonMap = Dict[str, Any]


TARGETS: List[Target] = [
    {
        "name": "OpenAI",
        "slug": "openai",
        "domain": "openai.com",
        "x_mention": "@OpenAI",
        "linkedin_mention": "@OpenAI",
        "angle": "platform delivery, multicloud infrastructure, evals, and agent deployment loops",
        "question": "Where do you see the operational bottleneck moving next: eval coverage, deployment, permissions, or feedback loops?",
        "official_source": "https://openai.com/careers/",
    },
    {
        "name": "Anthropic",
        "slug": "anthropic",
        "domain": "anthropic.com",
        "x_mention": "@AnthropicAI",
        "linkedin_mention": "@Anthropic",
        "angle": "long-horizon evals, RL infrastructure, model behavior measurement, and safe agent deployment",
        "question": "Which layer becomes the hardest to operationalize first: eval design, tool-use environments, or production feedback?",
        "official_source": "https://www.anthropic.com/careers",
    },
    {
        "name": "Scale AI",
        "slug": "scale-ai",
        "domain": "scale.com",
        "x_mention": "@scale_AI",
        "linkedin_mention": "@Scale AI",
        "angle": "enterprise ML delivery, expert feedback loops, data quality, and applied agent systems",
        "question": "Does the constraint look more like data quality, workflow integration, or evaluation coverage?",
        "official_source": "https://scale.com/careers",
    },
    {
        "name": "Cohere",
        "slug": "cohere",
        "domain": "cohere.com",
        "x_mention": "@cohere",
        "linkedin_mention": "@Cohere",
        "angle": "enterprise AI platforms, fine-tuning, retrieval, and multilingual deployment",
        "question": "Where should operators spend first: retrieval quality, fine-tuning data, or deployment observability?",
        "official_source": "https://cohere.com/careers",
    },
    {
        "name": "Mistral AI",
        "slug": "mistral-ai",
        "domain": "mistral.ai",
        "x_mention": "@MistralAI",
        "linkedin_mention": "@Mistral AI",
        "angle": "open model deployment, pre-training, applied ML, and enterprise rollout",
        "question": "Does the next bottleneck sit in model access, internal integration, or agent-facing docs?",
        "official_source": "https://mistral.ai/careers/",
    },
    {
        "name": "xAI",
        "slug": "xai",
        "domain": "x.ai",
        "x_mention": "@xai",
        "linkedin_mention": "@xAI",
        "angle": "multimodal understanding, model serving, product feedback loops, and consumer-scale AI",
        "question": "Which signal is more useful for builders: model capability, latency, or the feedback loop around the product?",
        "official_source": "https://x.ai/careers",
    },
    {
        "name": "Waymo",
        "slug": "waymo",
        "domain": "waymo.com",
        "x_mention": "@Waymo",
        "linkedin_mention": "@Waymo",
        "angle": "robotics evaluation, prediction systems, simulation, and safety-critical deployment",
        "question": "What is the cleaner proxy for readiness: model quality, scenario coverage, or operational monitoring?",
        "official_source": "https://waymo.com/careers/",
    },
    {
        "name": "Cerebras",
        "slug": "cerebras",
        "domain": "cerebras.ai",
        "x_mention": "@CerebrasSystems",
        "linkedin_mention": "@Cerebras Systems",
        "angle": "AI systems software, accelerator performance, deployment automation, and inference infrastructure",
        "question": "Does the compounding advantage come from hardware, software automation, or the developer surface around both?",
        "official_source": "https://www.cerebras.ai/careers",
    },
]


def http_json(url: str) -> JsonMap:
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def safe_http_json(url: str) -> Tuple[JsonMap, Optional[str]]:
    try:
        return http_json(url), None
    except Exception as exc:
        return {}, str(exc)


def pick_target(target_date: date) -> Target:
    return TARGETS[(target_date.toordinal() * 5) % len(TARGETS)]


def fmt_int(value: Any) -> str:
    if value is None:
        return "0"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


def fmt_money(value: Any) -> str:
    if not value:
        return "salary not published"
    try:
        return f"${int(value):,}"
    except (TypeError, ValueError):
        return "salary not published"


def clean_text(value: str) -> str:
    return (
        value.replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


def fingerprint(text: str) -> str:
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def source_links(target: Target) -> JsonMap:
    slug = target["slug"]
    domain = target["domain"]
    return {
        "adb_company": f"https://aidevboard.com/company/{slug}",
        "adb_jobs_api": f"{ADB_JOBS_URL}?company={urllib.parse.quote(slug)}&limit=100",
        "adb_stats_api": ADB_STATS_URL,
        "nhs_profile": f"https://nothumansearch.ai/site/{domain}",
        "official_source": target["official_source"],
    }


def build_target_research(target_date: date) -> JsonMap:
    target = pick_target(target_date)
    sources = source_links(target)
    stats, stats_error = safe_http_json(ADB_STATS_URL)
    jobs_payload, jobs_error = safe_http_json(sources["adb_jobs_api"])
    nhs_payload, nhs_error = safe_http_json(NHS_SITE_URL.format(domain=target["domain"]))

    companies = stats.get("companies", []) if isinstance(stats, dict) else []
    company_stat: JsonMap = {}
    for company in companies:
        if str(company.get("company", "")).lower() == target["name"].lower():
            company_stat = company
            break

    jobs = jobs_payload.get("jobs", []) if isinstance(jobs_payload, dict) else []
    total_roles = int(jobs_payload.get("total") or company_stat.get("roles") or len(jobs) or 0)
    avg_salary = company_stat.get("avg_salary")
    salary_midpoints = [
        int((job.get("salary_min", 0) + job.get("salary_max", 0)) / 2)
        for job in jobs
        if job.get("salary_min") and job.get("salary_max")
    ]
    if not avg_salary and salary_midpoints:
        avg_salary = int(statistics.mean(salary_midpoints))

    tags: Counter[str] = Counter()
    workplaces: Counter[str] = Counter()
    titles: List[str] = []
    for job in jobs:
        title = clean_text(str(job.get("title", "")).strip())
        if title:
            titles.append(title)
        for tag in job.get("tags") or []:
            tags[str(tag)] += 1
        workplace = str(job.get("workplace", "")).strip()
        if workplace:
            workplaces[workplace] += 1

    rank = None
    for index, company in enumerate(companies, start=1):
        if str(company.get("company", "")).lower() == target["name"].lower():
            rank = index
            break

    nhs_signals: List[str] = []
    if nhs_payload.get("has_llms_txt"):
        nhs_signals.append("llms.txt")
    if nhs_payload.get("has_openapi"):
        nhs_signals.append("OpenAPI")
    if nhs_payload.get("has_structured_api"):
        nhs_signals.append("structured API")
    if nhs_payload.get("has_ai_plugin"):
        nhs_signals.append("ai-plugin")
    if nhs_payload.get("has_mcp"):
        nhs_signals.append("MCP")

    source_errors = {
        "adb_stats_api": stats_error,
        "adb_jobs_api": jobs_error,
        "nhs_profile": nhs_error,
    }
    source_errors = {key: value for key, value in source_errors.items() if value}

    top_tags = [tag for tag, _count in tags.most_common(4)]
    top_titles = titles[:3]
    workplace_line = ", ".join(f"{name}: {count}" for name, count in workplaces.most_common(3))
    if not workplace_line:
        workplace_line = "workplace mix not published in current sample"

    paper_candidate = bool(total_roles >= 250 or (avg_salary and int(avg_salary) >= 300000))
    paper_reason = ""
    if total_roles >= 250:
        paper_reason = f"{target['name']} is a top-scale AI hiring signal with {fmt_int(total_roles)} indexed roles."
    elif avg_salary and int(avg_salary) >= 300000:
        paper_reason = f"{target['name']} has a published average AI salary signal above {fmt_money(avg_salary)}."

    return {
        "target": target,
        "sources": sources,
        "source_errors": source_errors,
        "rank": rank,
        "total_roles": total_roles,
        "avg_salary": avg_salary,
        "top_tags": top_tags,
        "top_titles": top_titles,
        "workplace_line": workplace_line,
        "nhs_score": nhs_payload.get("agentic_score"),
        "nhs_signals": nhs_signals,
        "paper_candidate": paper_candidate,
        "paper_reason": paper_reason,
    }


def targeted_x_copy(research: JsonMap) -> str:
    target = research["target"]
    sources = research["sources"]
    tag_text = ", ".join(research["top_tags"][:3]) if research["top_tags"] else "agent systems"
    rank_text = ""
    if research.get("rank"):
        rank_text = f" {target['name']} is #{research['rank']} by indexed role count in the current AI Dev Board sample."
    return (
        f"Looking at public AI hiring as a market signal: {target['x_mention']} has {fmt_int(research['total_roles'])} indexed AI/ML roles on AI Dev Board, "
        f"with current tags clustering around {tag_text}. Avg published salary: {fmt_money(research['avg_salary'])}.{rank_text}\n\n"
        f"The read is not just hiring volume. It points to {target['angle']}. {target['question']}\n\n"
        f"Data: {sources['adb_company']}"
    )


def targeted_linkedin_copy(research: JsonMap) -> str:
    target = research["target"]
    sources = research["sources"]
    tags = ", ".join(research["top_tags"][:4]) if research["top_tags"] else "agent systems"
    titles = "; ".join(research["top_titles"][:3]) if research["top_titles"] else "current public roles"
    nhs_line = ""
    if research.get("nhs_score") is not None:
        signal_text = ", ".join(research.get("nhs_signals") or ["public agent-facing signals tracked"])
        nhs_line = f"\n\nNHS follow-up lens: public agent-readiness profile shows {signal_text}. That is useful for checking what agents can inspect without a human browsing the site."
    return (
        f"Looking at {target['linkedin_mention']} through the public hiring data:\n\n"
        f"1. {fmt_int(research['total_roles'])} indexed AI/ML roles in AI Dev Board.\n"
        f"2. Current sample tags cluster around {tags}.\n"
        f"3. Sample roles include {titles}.\n"
        f"4. Avg published salary in the indexed sample: {fmt_money(research['avg_salary'])}.\n\n"
        f"The useful read is where the operational work is moving: {target['angle']}.\n\n"
        f"{target['name']} is a useful public lens on this area. {target['question']}"
        f"{nhs_line}\n\n"
        f"Data:\n{sources['adb_company']}\n{sources['nhs_profile']}"
    )


def render_targeted_research_post(research: JsonMap, post_time: str) -> str:
    target = research["target"]
    sources = research["sources"]
    top_tags = research["top_tags"] or ["AI systems"]
    top_titles = research["top_titles"] or ["current public roles"]
    rank_text = f"#{research['rank']} by indexed role count" if research.get("rank") else "tracked company"
    paper_line = "No longform trigger today."
    if research.get("paper_candidate"):
        paper_line = f"Paper trigger: {research['paper_reason']}"
    errors = research.get("source_errors") or {}
    error_lines = "\n".join(f"- {key}: {value}" for key, value in errors.items()) or "- None"
    return f"""### Morning Targeted Research Post

Post time: {post_time} America/Los_Angeles
Target: {target["name"]}
X mention: {target["x_mention"]}
LinkedIn tag hint: {target["linkedin_mention"]}
Research angle: {target["angle"]}
Observed signal: {fmt_int(research["total_roles"])} indexed roles, {rank_text}, {fmt_money(research["avg_salary"])} average published salary, top tags: {", ".join(top_tags[:3])}
Sample roles: {"; ".join(top_titles[:2])}
Workplace mix: {research["workplace_line"]}
Longform decision: {paper_line}

Documented sources:
- AI Dev Board company page: {sources["adb_company"]}
- AI Dev Board jobs API: {sources["adb_jobs_api"]}
- AI Dev Board stats API: {sources["adb_stats_api"]}
- Not Human Search profile: {sources["nhs_profile"]}
- Official source: {sources["official_source"]}

Source fetch errors:
{error_lines}

#### X

```text
{targeted_x_copy(research)}
```

#### LinkedIn

```text
{targeted_linkedin_copy(research)}
```
"""


def targeted_queue_item(
    target_date: date,
    research: JsonMap,
    existing_fingerprints: Set[str],
    post_time: str,
) -> JsonMap:
    target = research["target"]
    sources = research["sources"]
    x_copy = targeted_x_copy(research)
    linkedin_copy = targeted_linkedin_copy(research)
    x_fingerprint = fingerprint(x_copy)
    linkedin_fingerprint = fingerprint(linkedin_copy)
    fact_key = f"targeted-research:{target['slug']}:{research['total_roles']}:{','.join(research['top_tags'][:3])}"
    return {
        "id": f"daily-targeted-research-{target_date.isoformat()}-{target['slug']}",
        "kind": "targeted_research",
        "date": target_date.isoformat(),
        "slot": "morning",
        "post_time_local": post_time,
        "timezone": "America/Los_Angeles",
        "target": {
            "name": target["name"],
            "x_mention": target["x_mention"],
            "linkedin_mention": target["linkedin_mention"],
            "domain": target["domain"],
            "company_slug": target["slug"],
        },
        "fact_key": fact_key,
        "theme": f"{target['name']} public AI hiring signal",
        "format": "targeted documented research",
        "asset_brief": "Small source-backed stat card: role count, top tags, sample roles, operator question.",
        "route": sources["adb_company"],
        "research_sources": sources,
        "research_findings": {
            "indexed_roles": research["total_roles"],
            "rank": research.get("rank"),
            "avg_salary": research.get("avg_salary"),
            "top_tags": research.get("top_tags"),
            "sample_titles": research.get("top_titles"),
            "workplace_mix": research.get("workplace_line"),
            "nhs_score": research.get("nhs_score"),
            "nhs_signals": research.get("nhs_signals"),
            "source_errors": research.get("source_errors"),
            "paper_candidate": research.get("paper_candidate"),
            "paper_reason": research.get("paper_reason"),
        },
        "funnel": "AI Dev Board data, Not Human Search agent-readiness check, or 8bit research follow-up",
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
            "target company or influential person is named/tagged naturally",
            "documented sources are attached",
            "uses live ADB or NHS stats",
            "does not negatively call out the target",
            "includes a useful operator question or recommendation",
            "flags longform paper opportunity when the stat is large enough",
        ],
    }
