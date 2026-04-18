#!/usr/bin/env python3
"""
8bitconcepts — 4-Day Editorial Follow-Up Sender (CSV-driven)

Reads outreach/distribution_log.csv for rows with channel "email-pitch" (or a
plain email address in column "to" — older pre-channel rows) that were sent
>= 4 days ago, checks Resend /emails/<id> for delivery status, and sends a
brief Re:-style follow-up to any recipient that hasn't been followed up yet.

Follow-up policy:
  - delivered but NOT opened  -> follow up (editor never saw first)
  - opened but no reply       -> follow up (editor saw, needs nudge)
  - clicked                   -> follow up (highest-intent nudge)
  - bounced / failed          -> log, skip, never follow up
  - sent (no event yet)       -> defer one cycle (Resend event may still land)
  - no resend id / api error  -> skip this cycle, retry tomorrow

Body: 2-3 sentences referencing the original subject + a fresh-data hook
(pulled from 8bitconcepts.com/research.json at run time, falling back to
cached defaults if offline) + one CTA.

State:
  outreach/followup_log.csv  — one row per follow-up send, preventing
                                duplicates. Schema:
                                sent_at,original_send_id,to,subject,followup_id,status

Environment:
  RESEND_API_KEY     (overrides keychain lookup)
  FOUNDRY_TEST_MODE  (anything truthy -> treat dry-run regardless of CLI)

--------------------------------------------------------------------------
Edge cases handled
--------------------------------------------------------------------------
  * Resend API is down / returns 5xx / times out:
      Record a transient error in the run log, exit 0. No follow-ups sent
      this cycle. Tomorrow's run retries. We never spam on partial state.

  * Email was opened but recipient replied outside the pipeline (off-band
    reply to Shane's personal inbox):
      We have no way to know from Resend alone. Two escape hatches:
        1. --skip-emails addr1,addr2,... on the CLI
        2. Manually append a row to outreach/followup_log.csv with status
           "manual-reply-skip". The de-dup scan treats any row in that file
           as "already followed up" and skips.

  * Duplicate prevention:
      Before sending, we look up {to, original_send_id} in followup_log.csv.
      If present -> skip. The log is append-only; never mutate past rows.

  * Mixed CSV schemas:
      Distribution log has 5- and 6-column rows, some with plain email in
      "to" (old) and some with "email-pitch" channel (new). Our row
      classifier normalizes both into a single shape and ignores everything
      that isn't an email (github-pr, public-gist, indexnow, etc.).

  * Partial resend IDs:
      The 2026-04-16 batch wrote 8-char IDs (e.g. "4e9b34ae"). Resend
      requires the full UUID for lookup. We skip rows whose send_id doesn't
      match the UUID shape and report the count at the end.

  * Rate limiting:
      Resend free tier = 2 req/sec. We sleep 600ms between every API call
      (status check + send). --limit N caps total follow-ups per run for
      safety on the first live cycle.

  * Runtime safety:
      Any unhandled exception is logged to stderr with a [FATAL] tag and
      the process exits 1. Launchd captures stderr in followup-stderr.log
      but sends no mail (no Discord spam on transient issues).
--------------------------------------------------------------------------
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
DIST_LOG = ROOT / "outreach" / "distribution_log.csv"
FOLLOWUP_LOG = ROOT / "outreach" / "followup_log.csv"
RESEND_EMAIL_URL = "https://api.resend.com/emails"
FROM_EMAIL = "Shane at 8bitconcepts <hello@8bitconcepts.com>"
REPLY_TO = "hello@8bitconcepts.com"
RESEARCH_JSON_URL = "https://8bitconcepts.com/research.json"
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)

# Keywords in a pitch subject -> which paper the follow-up refers back to.
# Order matters: more specific matches first.
SUBJECT_TOPIC_MAP = [
    ("hallucination", "hallucination-budget"),
    ("agentic", "agentic-accountability-gap"),
    ("accountability gap", "agentic-accountability-gap"),
    ("agent-tag", "agentic-accountability-gap"),
    ("agents-tag", "agentic-accountability-gap"),
    ("governance", "agentic-accountability-gap"),
    ("hiring-snapshot", "q2-2026-ai-hiring-snapshot"),
    ("hiring snapshot", "q2-2026-ai-hiring-snapshot"),
    ("entry-level", "q2-2026-entry-level-ai-gap"),
    ("junior", "q2-2026-entry-level-ai-gap"),
    ("entry level", "q2-2026-entry-level-ai-gap"),
    ("bootcamp", "q2-2026-entry-level-ai-gap"),
    ("compensation", "q2-2026-ai-compensation-by-skill"),
    ("comp-", "q2-2026-ai-compensation-by-skill"),
    ("by skill", "q2-2026-ai-compensation-by-skill"),
    ("salary", "q2-2026-ai-compensation-by-skill"),
    ("remote", "q2-2026-remote-vs-onsite-ai-hiring"),
    ("onsite", "q2-2026-remote-vs-onsite-ai-hiring"),
    ("hybrid", "q2-2026-remote-vs-onsite-ai-hiring"),
    ("mcp", "q2-2026-mcp-ecosystem-health"),
    ("six percent", "the-six-percent"),
    ("94%", "the-six-percent"),
    ("6%", "the-six-percent"),
    ("no material returns", "the-six-percent"),
    ("integration tax", "the-integration-tax"),
    ("cost trap", "the-integration-tax"),
    ("org chart", "the-org-chart-problem"),
    ("measurement", "the-measurement-problem"),
    ("mandate", "the-mandate-trap"),
    ("guardrails", "the-guardrails-gap"),
    ("handoff", "shift-handoff-intelligence"),
    ("beyond the prompt", "beyond-the-prompt"),
]

# Fallback offers indexed by slug — one-liner fresh hook + URL slug.
# Overridden at run time by the live research.json summary when available.
FALLBACK_HOOK = {
    "q2-2026-ai-hiring-snapshot": (
        "latest cut: 8,618 AI/ML roles across 513 companies, $213k median, "
        "599 new this week"
    ),
    "q2-2026-entry-level-ai-gap": (
        "latest cut: ~7% of AI/ML roles open to juniors — tightest "
        "junior-to-senior ratio in tech"
    ),
    "q2-2026-ai-compensation-by-skill": (
        "latest cut: research roles pay a $42k premium over generative-AI "
        "roles across 3,402 salary-disclosed listings"
    ),
    "q2-2026-remote-vs-onsite-ai-hiring": (
        "latest cut: hybrid roles pay a ~$35k premium over remote+onsite; "
        "55% of AI engineering still fully onsite"
    ),
    "q2-2026-mcp-ecosystem-health": (
        "latest cut: 5,578 agent-ready sites indexed, only 10.3% pass a "
        "live JSON-RPC handshake"
    ),
    "hallucination-budget": (
        "the quantitative framework for acceptable AI failure rates in "
        "production"
    ),
    "agentic-accountability-gap": (
        "governance frameworks built for generative AI don't transfer to "
        "autonomous agents"
    ),
    "the-six-percent": (
        "McKinsey's 6%-see-returns gap isn't tech sophistication — it's "
        "organizational discipline"
    ),
    "the-integration-tax": (
        "model API cost is only 10-20% of real AI spend; the 80% that eats "
        "budgets is pipelines, integration, eval, maintenance"
    ),
    "the-org-chart-problem": (
        "where AI reports in the org chart predicts outcomes more than "
        "which model you're running"
    ),
    "the-measurement-problem": (
        "the AI metric that actually correlates with ROI: irreversible "
        "decisions per quarter"
    ),
    "the-mandate-trap": (
        "top-down AI mandates vs. bottom-up adoption — which actually "
        "drives measurable results"
    ),
    "the-guardrails-gap": (
        "why enterprise AI safety frameworks fail the moment agents act "
        "autonomously"
    ),
    "shift-handoff-intelligence": (
        "maintaining context across human-agent handoffs in production"
    ),
    "beyond-the-prompt": (
        "moving past prompt engineering to systematic integration patterns"
    ),
}

DEFAULT_HOOK = (
    "we've got fresh live-data cuts out this week if any of them are more "
    "on-brief for you"
)


# ---------- helpers ----------

def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {msg}")


def get_resend_key() -> str:
    key = os.environ.get("RESEND_API_KEY")
    if key:
        return key.strip()
    try:
        r = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-a",
                "foundry",
                "-s",
                "resend-api-key",
                "-w",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return r.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        log(f"[FATAL] Resend API key not reachable: {e}")
        sys.exit(1)


def http_get_json(url: str, api_key: Optional[str] = None, timeout: int = 15) -> dict:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "curl/8.7.1")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def fetch_live_hooks() -> dict:
    """Pull research.json summaries → slug -> refreshed one-liner hook.
    Falls back silently on any network error."""
    hooks = dict(FALLBACK_HOOK)
    try:
        data = http_get_json(RESEARCH_JSON_URL, timeout=10)
    except Exception as e:
        log(f"live hook refresh failed ({e}); using fallback hooks")
        return hooks
    for p in data.get("papers", []):
        slug = p.get("slug")
        summary = (p.get("summary") or "").strip()
        if not slug or not summary:
            continue
        # First sentence only, trimmed.
        first = re.split(r"(?<=[.])\s", summary, maxsplit=1)[0]
        if len(first) > 220:
            first = first[:217].rstrip() + "..."
        hooks[slug] = first
    return hooks


def pick_topic(subject: str) -> Optional[str]:
    s = subject.lower()
    for needle, slug in SUBJECT_TOPIC_MAP:
        if needle in s:
            return slug
    return None


def load_followup_log() -> set[tuple[str, str]]:
    """(to_lower, original_send_id) pairs we've already followed up on."""
    done: set[tuple[str, str]] = set()
    if not FOLLOWUP_LOG.exists():
        return done
    with FOLLOWUP_LOG.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            to = (row.get("to") or "").strip().lower()
            orig = (row.get("original_send_id") or "").strip()
            if to and orig:
                done.add((to, orig))
    return done


def append_followup_log(row: dict) -> None:
    FOLLOWUP_LOG.parent.mkdir(parents=True, exist_ok=True)
    is_new = not FOLLOWUP_LOG.exists()
    fieldnames = [
        "sent_at",
        "original_send_id",
        "to",
        "subject",
        "followup_id",
        "status",
    ]
    with FOLLOWUP_LOG.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if is_new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in fieldnames})


def parse_dist_row(row: list[str]) -> Optional[dict]:
    """Normalize a distribution_log.csv row into a common shape, or None
    if it's not an email pitch we should consider.

    Returns:
      {date, to, subject, send_id, status}
    """
    if len(row) < 4:
        return None
    date_s = row[0].strip()
    col2 = row[1].strip()
    col3 = row[2].strip() if len(row) > 2 else ""
    col4 = row[3].strip() if len(row) > 3 else ""

    # Skip header
    if date_s.lower() == "date":
        return None

    to = ""
    subject = ""
    send_id = ""

    if col2.lower() == "email-pitch":
        # 2026-04-17,email-pitch,<email>,resend:<uuid>,<status>
        to = col3
        send_id = col4
        subject = row[4].strip() if len(row) > 4 else ""
    elif col2.lower() == "email-newsletter":
        # Newsletter pitches count — editorial nudge also applies.
        to = col3
        send_id = col4
        subject = row[4].strip() if len(row) > 4 else ""
    elif "@" in col2 and "." in col2:
        # Old schema: 2026-04-15,<email>,<subject>,<send_id>,<status>
        to = col2
        subject = col3
        send_id = col4
    else:
        return None  # github-pr, public-gist, indexnow, etc.

    # Strip "resend:" prefix if present
    if send_id.startswith("resend:"):
        send_id = send_id[len("resend:"):]

    if not to or "@" not in to:
        return None

    return {
        "date": date_s,
        "to": to,
        "subject": subject,
        "send_id": send_id,
    }


def parse_iso_date(s: str) -> Optional[datetime]:
    s = s.strip()
    # Try full ISO8601 with Z or offset
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        dt = None
    if dt is None:
        # Try plain YYYY-MM-DD → assume UTC midnight
        try:
            dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    # Guarantee tz-aware (treat naive as UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def get_resend_status(
    api_key: str, email_id: str
) -> tuple[Optional[str], Optional[str]]:
    """Return (last_event, err). last_event examples: delivered, opened,
    clicked, bounced, complained, sent. err is a short tag on API failure."""
    try:
        data = http_get_json(
            f"{RESEND_EMAIL_URL}/{email_id}", api_key=api_key, timeout=15
        )
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, "not-found"
        return None, f"http-{e.code}"
    except urllib.error.URLError as e:
        return None, f"url-{e.reason}"
    except Exception as e:
        return None, f"exc-{type(e).__name__}"
    return (data.get("last_event") or "").lower() or None, None


def build_followup(subject: str, topic_slug: Optional[str], hooks: dict) -> tuple[str, str]:
    fresh = hooks.get(topic_slug, DEFAULT_HOOK) if topic_slug else DEFAULT_HOOK
    if topic_slug and topic_slug in FALLBACK_HOOK:
        # We have a known paper — build a tight referral URL.
        url = f"https://8bitconcepts.com/research/{topic_slug}.html"
        cta_cut = "the raw numbers" if "latest cut" in fresh else "the short write-up"
    else:
        url = "https://8bitconcepts.com/research/"
        cta_cut = "the index page"
    re_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    body = (
        f"Quick bump on my note from earlier this week.\n\n"
        f"Since sending, {fresh}. Link if useful: {url}\n\n"
        f"Happy to send over {cta_cut} or a tighter editorial angle if "
        f"either would fit — otherwise no need to reply, I'll leave it here.\n\n"
        f"Shane\n"
        f"8bitconcepts | hello@8bitconcepts.com\n"
    )
    return re_subject, body


def send_resend(api_key: str, to: str, subject: str, body: str) -> tuple[bool, str]:
    payload = json.dumps(
        {
            "from": FROM_EMAIL,
            "to": [to],
            "reply_to": REPLY_TO,
            "subject": subject,
            "text": body,
        }
    ).encode()
    req = urllib.request.Request(RESEND_EMAIL_URL, data=payload, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "curl/8.7.1")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
            return True, data.get("id", "")
    except urllib.error.HTTPError as e:
        return False, f"http-{e.code}:{e.read().decode()[:160]}"
    except Exception as e:
        return False, f"exc-{type(e).__name__}:{e}"


# ---------- main ----------

def run(
    after_days: int,
    dry_run: bool,
    limit: Optional[int],
    skip_emails: set[str],
) -> int:
    if not DIST_LOG.exists():
        log(f"no distribution log at {DIST_LOG}; nothing to do")
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=after_days)
    already_done = load_followup_log()

    # Gather candidates from the distribution log
    candidates: list[dict] = []
    skipped_partial_id = 0
    with DIST_LOG.open(newline="") as f:
        reader = csv.reader(f)
        for raw in reader:
            norm = parse_dist_row(raw)
            if not norm:
                continue
            dt = parse_iso_date(norm["date"])
            if not dt:
                continue
            if dt > cutoff:
                continue  # too recent
            if not norm["send_id"]:
                continue
            if not UUID_RE.match(norm["send_id"]):
                skipped_partial_id += 1
                continue
            if norm["to"].lower() in skip_emails:
                continue
            if (norm["to"].lower(), norm["send_id"]) in already_done:
                continue
            candidates.append(norm)

    log(
        f"candidates={len(candidates)} cutoff_days={after_days} "
        f"skipped_partial_id={skipped_partial_id} "
        f"already_followed_up={len(already_done)}"
    )
    if not candidates:
        log("no eligible follow-ups this cycle")
        return 0

    api_key = get_resend_key()
    hooks = fetch_live_hooks()

    # Classify each candidate via Resend
    eligible: list[dict] = []
    api_fail_count = 0
    for c in candidates:
        time.sleep(0.6)  # Resend rate limit cushion
        status, err = get_resend_status(api_key, c["send_id"])
        if err:
            api_fail_count += 1
            log(f"  api-fail {c['to']} ({c['send_id'][:8]}): {err}")
            continue
        status = status or "sent"
        if status in {"bounced", "complained", "failed"}:
            log(f"  skip {c['to']}: status={status}")
            continue
        if status == "sent":
            # Resend hasn't recorded a delivery event yet. Defer a cycle.
            log(f"  defer {c['to']}: status=sent (event pending)")
            continue
        # delivered / opened / clicked  -> follow up
        c["last_event"] = status
        eligible.append(c)

    log(f"eligible after Resend probe: {len(eligible)} (api_failures={api_fail_count})")

    if limit is not None:
        eligible = eligible[:limit]
        log(f"capped to limit={limit}")

    sent_count = 0
    fail_count = 0
    for c in eligible:
        topic = pick_topic(c["subject"])
        subj, body = build_followup(c["subject"], topic, hooks)
        if dry_run:
            print("\n" + "=" * 72)
            print(f"[DRY] TO: {c['to']}")
            print(f"[DRY] ORIGINAL_ID: {c['send_id']}")
            print(f"[DRY] EVENT: {c['last_event']}")
            print(f"[DRY] TOPIC: {topic or '(default)'}")
            print(f"[DRY] SUBJECT: {subj}")
            print("-" * 72)
            print(body)
            continue

        time.sleep(0.6)
        ok, info = send_resend(api_key, c["to"], subj, body)
        now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if ok:
            sent_count += 1
            append_followup_log(
                {
                    "sent_at": now_iso,
                    "original_send_id": c["send_id"],
                    "to": c["to"],
                    "subject": subj,
                    "followup_id": info,
                    "status": f"sent-{c['last_event']}",
                }
            )
            log(f"  SENT {c['to']} -> {info} (orig last_event={c['last_event']})")
        else:
            fail_count += 1
            append_followup_log(
                {
                    "sent_at": now_iso,
                    "original_send_id": c["send_id"],
                    "to": c["to"],
                    "subject": subj,
                    "followup_id": "",
                    "status": f"error:{info[:80]}",
                }
            )
            log(f"  FAIL {c['to']}: {info[:160]}")

    log(
        f"done: sent={sent_count} failed={fail_count} "
        f"dry_run={dry_run} api_fail={api_fail_count}"
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__ or "")
    p.add_argument("--after-days", type=int, default=4)
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print follow-ups that WOULD send; make no state changes.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Safety cap: send at most N follow-ups this run.",
    )
    p.add_argument(
        "--skip-emails",
        type=str,
        default="",
        help="Comma-separated list of emails to exclude (e.g. manual replies).",
    )
    args = p.parse_args()

    if os.environ.get("FOUNDRY_TEST_MODE"):
        args.dry_run = True

    skip = {
        e.strip().lower()
        for e in (args.skip_emails or "").split(",")
        if e.strip()
    }
    try:
        return run(
            after_days=args.after_days,
            dry_run=args.dry_run,
            limit=args.limit,
            skip_emails=skip,
        )
    except KeyboardInterrupt:
        log("interrupted")
        return 130
    except Exception as e:
        log(f"[FATAL] unhandled: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
