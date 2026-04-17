#!/usr/bin/env python3
"""
8bitconcepts — Weekly Digest Sender

Runs Mondays at 10:00am PT (30 min after the regen cascade completes).

- Fetches subscribers from ADB admin API (filtered to tag=8bitconcepts-research)
- Pulls fresh stats from aidevboard.com/api/v1/stats + nothumansearch.ai/digest.json
- Composes a dark-slate/terracotta HTML + text email
- Sends via Resend from hello@8bitconcepts.com
- Logs successes + failures to tools/weekly-digest.log
- --dry-run prints the composed email + would-be recipient count, sends nothing

Secrets (macOS Keychain, account=foundry):
    resend-api-key
    aidevboard-admin-key
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from html import escape
from pathlib import Path

RESEND_API_URL = "https://api.resend.com/emails"
FROM_EMAIL = "8bitconcepts Research <hello@8bitconcepts.com>"
REPLY_TO = "hello@8bitconcepts.com"
SITE_URL = "https://8bitconcepts.com"
ADB_BASE = "https://aidevboard.com"
NHS_BASE = "https://nothumansearch.ai"
TAG = "8bitconcepts-research"

SCRIPT_DIR = Path(__file__).resolve().parent
LOG_PATH = SCRIPT_DIR / "weekly-digest.log"

# Featured papers for "New / updated this week" — 5 freshest research URLs.
# Paths are relative to SITE_URL/research/.
FEATURED_PAPERS = [
    ("q2-2026-ai-hiring-snapshot", "Q2 2026 — AI Hiring Snapshot"),
    ("q2-2026-mcp-ecosystem-health", "Q2 2026 — MCP Ecosystem Health"),
    ("q2-2026-ai-compensation-by-skill", "Q2 2026 — AI Compensation by Skill"),
    ("q2-2026-remote-vs-onsite-ai-hiring", "Q2 2026 — Remote vs Onsite AI Hiring"),
    ("q2-2026-entry-level-ai-gap", "Q2 2026 — Entry-Level AI Gap"),
]

HTTP_UA = "curl/8.7.1"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line)
    try:
        with LOG_PATH.open("a") as f:
            f.write(line + "\n")
    except OSError as e:
        print(f"WARN: could not write log: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Secrets + HTTP
# ---------------------------------------------------------------------------

def keychain_secret(service: str) -> str | None:
    """Read a secret from macOS Keychain. Returns None on miss."""
    try:
        result = subprocess.run(
            ["/usr/bin/security", "find-generic-password",
             "-a", "foundry", "-s", service, "-w"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.SubprocessError, OSError) as e:
        log(f"ERROR: keychain read for '{service}' failed: {e}")
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def http_get_json(url: str, headers: dict | None = None, timeout: int = 15):
    req = urllib.request.Request(
        url, headers={"User-Agent": HTTP_UA, **(headers or {})}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Data fetch
# ---------------------------------------------------------------------------

def fetch_subscribers(admin_key: str) -> list[dict]:
    """Fetch active subscribers tagged for 8bc research.

    ADB's admin endpoint currently ignores the tag query param, so we
    always filter client-side by the subscriber's `tags` array.
    """
    url = f"{ADB_BASE}/api/v1/admin/subscribers?tag={TAG}"
    try:
        raw = http_get_json(url, headers={"Authorization": f"Bearer {admin_key}"})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        log(f"ERROR: subscribers endpoint returned {e.code}: {body}")
        return []
    except Exception as e:  # network, json, etc.
        log(f"ERROR: subscribers fetch failed: {e}")
        return []

    if not isinstance(raw, list):
        log(f"ERROR: subscribers response is {type(raw).__name__}, expected list")
        return []

    filtered = []
    for s in raw:
        if not isinstance(s, dict):
            continue
        email = (s.get("email") or "").strip()
        if not email or "@" not in email:
            continue
        # Skip test fixtures
        low = email.lower()
        if low.startswith("test-") or low.endswith("@example.com"):
            continue
        tags = s.get("tags") or []
        if isinstance(tags, list) and TAG in tags:
            filtered.append(s)
    return filtered


def fetch_adb_stats() -> dict:
    try:
        data = http_get_json(f"{ADB_BASE}/api/v1/stats")
    except Exception as e:
        log(f"WARN: aidevboard stats fetch failed: {e}")
        return {}
    overview = data.get("overview", {}) if isinstance(data, dict) else {}
    salary = data.get("salary", {}) if isinstance(data, dict) else {}
    companies = data.get("companies", []) if isinstance(data, dict) else []
    return {
        "total_jobs": overview.get("total_jobs", 0),
        "total_companies": overview.get("total_companies", 0),
        "new_this_week": overview.get("new_this_week", 0),
        "avg_salary": salary.get("average", 0),
        "top_company": (companies[0] if companies else {}),
        "top_companies": companies[:5],
    }


def fetch_nhs_digest() -> dict:
    try:
        data = http_get_json(f"{NHS_BASE}/digest.json")
    except Exception as e:
        log(f"WARN: nothumansearch digest fetch failed: {e}")
        return {}
    if not isinstance(data, dict):
        return {}
    # total indexed: prefer explicit total; fall back to sum of categories
    total_indexed = data.get("total_sites") or data.get("llms_txt_count") or 0
    if not total_indexed and isinstance(data.get("categories"), list):
        total_indexed = sum(int(c.get("count", 0)) for c in data["categories"])
    return {
        "total_indexed": total_indexed,
        "mcp_verified": data.get("mcp_verified", 0),
        "llms_txt_count": data.get("llms_txt_count", 0),
        "new_mcp_servers": data.get("new_mcp_servers", []) or [],
        "top_category": (data.get("categories") or [{}])[0],
    }


# ---------------------------------------------------------------------------
# Email composition
# ---------------------------------------------------------------------------

def utm(url: str, campaign: str = "weekly-digest") -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}utm_source=newsletter&utm_medium=email&utm_campaign={campaign}"


def build_subject() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return f"This week across the Foundry — {today}"


def build_preheader() -> str:
    return "Fresh AI engineering research: hiring, MCP, comp, workplace, entry-level"


def _format_salary(v) -> str:
    try:
        n = int(v or 0)
    except (TypeError, ValueError):
        return "$0"
    return f"${n:,}"


def build_text(adb: dict, nhs: dict, subscriber: dict | None) -> str:
    sub_id = (subscriber or {}).get("id", "")
    unsub_url = f"{ADB_BASE}/unsubscribe/{sub_id}" if sub_id else f"{ADB_BASE}/unsubscribe"
    today = datetime.now().strftime("%B %d, %Y")

    top_co = adb.get("top_company") or {}
    top_co_name = top_co.get("company", "—")
    top_co_roles = top_co.get("roles", 0)
    top_co_salary = top_co.get("avg_salary")

    new_mcp = (nhs.get("new_mcp_servers") or [])[:3]

    lines = [
        f"This week across the Foundry — {today}",
        "",
        "Fresh AI engineering research: hiring, MCP, comp, workplace, entry-level.",
        "",
        "# Topline this week",
        f"- {adb.get('new_this_week', 0):,} new AI engineering roles added to aidevboard.com",
        f"- {adb.get('total_jobs', 0):,} active roles across {adb.get('total_companies', 0):,} companies",
        f"- Avg AI developer salary: {_format_salary(adb.get('avg_salary'))}/yr",
        f"- NHS index: {nhs.get('total_indexed', 0):,} agentic sites, {nhs.get('mcp_verified', 0):,} MCP-verified",
        "",
        "# New / updated this week",
    ]
    for slug, title in FEATURED_PAPERS:
        lines.append(f"- {title}: {SITE_URL}/research/{slug}.html")
    lines += [
        "",
        "# Hiring highlight",
        f"{top_co_name} is leading this week with {top_co_roles:,} open roles" +
        (f" (avg {_format_salary(top_co_salary)}/yr)." if top_co_salary else "."),
        "Full live index: https://aidevboard.com",
        "",
        "# MCP highlight",
    ]
    if new_mcp:
        m = new_mcp[0]
        name = m.get("name", m.get("domain", "a new MCP server"))
        desc = m.get("description", "")
        lines += [
            f"{nhs.get('mcp_verified', 0):,} MCP servers now verified on NHS.",
            f"Newest: {name} — {desc[:180]}",
            "Browse: https://nothumansearch.ai/category/ai-tools",
        ]
    else:
        lines += [
            f"{nhs.get('mcp_verified', 0):,} MCP servers now verified on NHS — up from ~500 a month ago.",
            "Browse: https://nothumansearch.ai/category/ai-tools",
        ]
    lines += [
        "",
        "—",
        "Forward this to a friend: https://8bitconcepts.com",
        f"Unsubscribe: {unsub_url}",
        "Subscribe: https://8bitconcepts.com (research feed)",
    ]
    return "\n".join(lines)


def build_html(adb: dict, nhs: dict, subscriber: dict | None) -> str:
    sub_id = (subscriber or {}).get("id", "")
    unsub_url = f"{ADB_BASE}/unsubscribe/{sub_id}" if sub_id else f"{ADB_BASE}/unsubscribe"
    today_h = datetime.now().strftime("%B %d, %Y")
    subject = build_subject()
    preheader = build_preheader()

    top_co = adb.get("top_company") or {}
    top_co_name = escape(top_co.get("company", "—"))
    top_co_roles = int(top_co.get("roles", 0) or 0)
    top_co_salary = top_co.get("avg_salary")
    top_salary_str = f" · avg {_format_salary(top_co_salary)}/yr" if top_co_salary else ""

    # Topline bullets
    bullets = [
        f'<strong style="color:#d97757">{adb.get("new_this_week", 0):,}</strong> new AI engineering roles added to <a href="{utm(ADB_BASE)}" style="color:#e0e0e0">aidevboard.com</a>',
        f'<strong style="color:#d97757">{adb.get("total_jobs", 0):,}</strong> active roles across <strong>{adb.get("total_companies", 0):,}</strong> companies',
        f'Avg AI developer salary: <strong style="color:#d97757">{_format_salary(adb.get("avg_salary"))}/yr</strong>',
        f'NHS index: <strong style="color:#d97757">{nhs.get("total_indexed", 0):,}</strong> agentic sites, <strong>{nhs.get("mcp_verified", 0):,}</strong> MCP-verified',
    ]
    bullets_html = "".join(
        f'<li style="margin:6px 0;color:#e0e0e0;font-size:15px;line-height:1.55;">{b}</li>'
        for b in bullets
    )

    # Papers list
    papers_html = ""
    for slug, title in FEATURED_PAPERS:
        href = utm(f"{SITE_URL}/research/{slug}.html")
        papers_html += (
            f'<li style="margin:8px 0;">'
            f'<a href="{href}" style="color:#d97757;font-size:15px;text-decoration:none;font-weight:600;">{escape(title)}</a>'
            f'</li>'
        )

    # MCP highlight
    new_mcp = (nhs.get("new_mcp_servers") or [])[:1]
    if new_mcp:
        m = new_mcp[0]
        name = escape(m.get("name", m.get("domain", "a new MCP server")))
        desc = escape((m.get("description") or "")[:220])
        mcp_block = (
            f'<p style="margin:8px 0;color:#e0e0e0;font-size:15px;line-height:1.55;">'
            f'<strong style="color:#d97757">{nhs.get("mcp_verified", 0):,}</strong> MCP servers now verified on '
            f'<a href="{utm(NHS_BASE)}" style="color:#e0e0e0">nothumansearch.ai</a>. '
            f'Newest: <strong>{name}</strong> — {desc}'
            f'</p>'
        )
    else:
        mcp_block = (
            f'<p style="margin:8px 0;color:#e0e0e0;font-size:15px;line-height:1.55;">'
            f'<strong style="color:#d97757">{nhs.get("mcp_verified", 0):,}</strong> MCP servers now verified on '
            f'<a href="{utm(NHS_BASE)}" style="color:#e0e0e0">nothumansearch.ai</a> — up from ~500 a month ago.'
            f'</p>'
        )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="color-scheme" content="dark light">
<title>{escape(subject)}</title>
</head>
<body style="margin:0;padding:0;background-color:#0d0d0e;font-family:-apple-system,BlinkMacSystemFont,'Inter',Segoe UI,Arial,sans-serif;color:#e0e0e0;">
<!-- Preheader (hidden in body but shown in inbox preview) -->
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{escape(preheader)}</div>
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0d0d0e;">
<tr><td align="center" style="padding:32px 16px;">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

<!-- Header -->
<tr><td style="padding:24px 0;text-align:center;border-bottom:2px solid #d97757;">
  <a href="{utm(SITE_URL)}" style="color:#ffffff;font-size:24px;font-weight:700;text-decoration:none;font-family:'IBM Plex Mono',monospace;">8bitconcepts</a>
  <br>
  <span style="color:#a0a0a0;font-size:13px;">Weekly research digest · {today_h}</span>
</td></tr>

<!-- Topline -->
<tr><td style="padding:24px 0 8px;">
  <div style="color:#d97757;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px;">Topline this week</div>
  <ul style="margin:0;padding-left:20px;">{bullets_html}</ul>
</td></tr>

<!-- Research papers -->
<tr><td style="padding:24px 0 8px;">
  <div style="color:#d97757;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px;">New / updated this week</div>
  <ul style="margin:0;padding-left:20px;list-style-type:none;">{papers_html}</ul>
</td></tr>

<!-- Hiring highlight -->
<tr><td style="padding:20px 16px;background-color:#1a1a1b;border-radius:8px;margin:16px 0;">
  <div style="color:#d97757;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px;">Hiring highlight</div>
  <p style="margin:6px 0;color:#e0e0e0;font-size:15px;line-height:1.55;">
    <strong>{top_co_name}</strong> is leading this week with
    <strong style="color:#d97757">{top_co_roles:,}</strong> open roles{top_salary_str}.
    <br>
    <a href="{utm(ADB_BASE)}" style="color:#d97757;font-size:14px;text-decoration:none;">Browse full live index →</a>
  </p>
</td></tr>

<!-- MCP highlight -->
<tr><td style="padding:20px 16px;background-color:#1a1a1b;border-radius:8px;margin:16px 0;">
  <div style="color:#d97757;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px;">MCP highlight</div>
  {mcp_block}
  <a href="{utm(NHS_BASE + '/category/ai-tools')}" style="color:#d97757;font-size:14px;text-decoration:none;">Browse verified MCP servers →</a>
</td></tr>

<!-- CTA -->
<tr><td style="padding:28px 0;text-align:center;">
  <a href="{utm(SITE_URL + '/research/')}" style="display:inline-block;background-color:#d97757;color:#0d0d0e;padding:14px 32px;border-radius:6px;font-size:15px;font-weight:700;text-decoration:none;">
    Read the latest research
  </a>
</td></tr>

<!-- Footer -->
<tr><td style="padding:24px 0;text-align:center;border-top:1px solid #1a1a1b;">
  <p style="margin:4px 0;color:#666;font-size:12px;line-height:1.5;">
    Sent by <a href="{utm(SITE_URL)}" style="color:#666;text-decoration:none;">8bitconcepts.com</a> · Foundry research imprint
  </p>
  <p style="margin:4px 0;color:#666;font-size:12px;line-height:1.5;">
    <a href="{utm(SITE_URL, 'weekly-digest-forward')}" style="color:#666;">Forward to a friend</a>
    &nbsp;·&nbsp;
    <a href="{utm(SITE_URL + '/#subscribe', 'weekly-digest-subscribe')}" style="color:#666;">Subscribe</a>
    &nbsp;·&nbsp;
    <a href="{unsub_url}" style="color:#666;">Unsubscribe</a>
  </p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

def send_via_resend(api_key: str, to_email: str, subject: str,
                    html: str, text: str) -> tuple[bool, str]:
    payload = json.dumps({
        "from": FROM_EMAIL,
        "to": [to_email],
        "reply_to": REPLY_TO,
        "subject": subject,
        "html": html,
        "text": text,
    }).encode("utf-8")
    req = urllib.request.Request(
        RESEND_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": HTTP_UA,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read())
            return True, body.get("id", "")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="8bitconcepts weekly digest sender")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print composed email + recipient count, send nothing")
    ap.add_argument("--limit", type=int, default=0,
                    help="Cap number of sends (0 = all). Debugging only.")
    args = ap.parse_args()

    log(f"weekly-digest start (dry_run={args.dry_run})")

    # Secrets
    admin_key = keychain_secret("aidevboard-admin-key")
    if not admin_key:
        log("ERROR: aidevboard-admin-key missing from keychain — cannot fetch subscribers. Exiting.")
        return 2
    resend_key = None if args.dry_run else keychain_secret("resend-api-key")
    if not args.dry_run and not resend_key:
        log("ERROR: resend-api-key missing from keychain — cannot send. Exiting.")
        return 2

    # Data
    subscribers = fetch_subscribers(admin_key)
    adb_stats = fetch_adb_stats()
    nhs_digest = fetch_nhs_digest()

    log(f"fetched {len(subscribers)} tagged subscribers, "
        f"adb_stats_keys={len(adb_stats)}, nhs_digest_keys={len(nhs_digest)}")

    # Dry-run output
    if args.dry_run:
        sample_sub = subscribers[0] if subscribers else {"id": "SAMPLE-ID", "email": "preview@example.com"}
        subject = build_subject()
        html = build_html(adb_stats, nhs_digest, sample_sub)
        text = build_text(adb_stats, nhs_digest, sample_sub)
        print("=" * 70)
        print(f"SUBJECT: {subject}")
        print(f"PREHEADER: {build_preheader()}")
        print(f"RECIPIENTS: {len(subscribers)}")
        print(f"ADB stats: new_this_week={adb_stats.get('new_this_week')}, "
              f"total_jobs={adb_stats.get('total_jobs')}, "
              f"total_companies={adb_stats.get('total_companies')}, "
              f"avg_salary={adb_stats.get('avg_salary')}")
        print(f"NHS digest: total_indexed={nhs_digest.get('total_indexed')}, "
              f"mcp_verified={nhs_digest.get('mcp_verified')}")
        print("=" * 70)
        print("--- TEXT ---")
        print(text)
        print("=" * 70)
        print("--- HTML (first 1500 chars) ---")
        print(html[:1500])
        print("... [truncated] ...")
        log(f"dry-run complete: would send to {len(subscribers)} recipient(s)")
        return 0

    # Real send
    if not subscribers:
        log(f"NOTICE: 0 subscribers tagged '{TAG}'. Skipping send. "
            f"This is the expected state for a fresh list — not an error.")
        return 0

    subject = build_subject()
    sent = 0
    failed = 0
    recipients = subscribers if args.limit <= 0 else subscribers[: args.limit]
    for i, sub in enumerate(recipients, 1):
        email = sub.get("email", "")
        if not email:
            continue
        html = build_html(adb_stats, nhs_digest, sub)
        text = build_text(adb_stats, nhs_digest, sub)
        ok, info = send_via_resend(resend_key, email, subject, html, text)
        if ok:
            sent += 1
            log(f"SENT [{i}/{len(recipients)}] {email} id={info}")
        else:
            failed += 1
            log(f"FAIL [{i}/{len(recipients)}] {email} — {info}")
        # Resend free tier: 2 req/sec. 500ms inter-send keeps us safely under.
        time.sleep(0.6)

    log(f"weekly-digest done: sent={sent}, failed={failed}, total={len(recipients)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
