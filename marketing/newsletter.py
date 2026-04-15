#!/usr/bin/env python3
"""
8bitconcepts — Weekly Research Digest Sender

Sends the weekly (or ad-hoc) digest to subscribers tagged
`8bitconcepts-research` in the shared aidevboard subscriber list.

Usage:
    python3 marketing/newsletter.py dry-run    # render to stdout only
    python3 marketing/newsletter.py send       # send to all tagged subscribers

Broadcast log: marketing/newsletter-sent.json

Requires:
  - macOS Keychain service `foundry/resend-api-key` (or env RESEND_API_KEY)
  - macOS Keychain service `foundry/aidevboard-admin-key` (for subscriber list)
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SENT_FILE = SCRIPT_DIR / "newsletter-sent.json"
RESEARCH_JSON = SCRIPT_DIR.parent / "research.json"
SUBSCRIBERS_URL = "https://aidevboard.com/api/v1/admin/subscribers"
RESEND_API_URL = "https://api.resend.com/emails"
FROM_EMAIL = "Shane at 8bitconcepts <hello@8bitconcepts.com>"
TAG = "8bitconcepts-research"


def keychain(service):
    result = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-a", "foundry", "-s", service, "-w"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def fetch_subscribers():
    key = os.environ.get("AIDEVBOARD_ADMIN_KEY") or keychain("aidevboard-admin-key")
    if not key:
        print("ERROR: aidevboard admin key not available", file=sys.stderr)
        sys.exit(1)
    req = urllib.request.Request(
        SUBSCRIBERS_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "User-Agent": "curl/8.7.1",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    subs = data if isinstance(data, list) else data.get("subscribers", [])
    return [s for s in subs if TAG in (s.get("tags") or [])]


def load_research():
    with open(RESEARCH_JSON) as f:
        return json.load(f).get("papers", [])


def compose_digest(papers, limit=3):
    """Compose the weekly digest HTML + text from the most recent N papers.
    Papers in research.json are publication-ordered; last is newest."""
    recent = list(reversed(papers))[:limit]
    lines_text = [
        "Two new papers on what's actually happening inside enterprise AI programs.",
        "",
    ]
    lines_html = [
        "<div style='font-family:system-ui,-apple-system,sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#111;'>",
        "<p style='font-size:15px;line-height:1.6;'>Two papers on what's actually happening inside enterprise AI programs.</p>",
    ]
    for p in recent:
        title = p["title"]
        summary = p["summary"]
        url = p["url"]
        lines_text.append(f"## {title}")
        lines_text.append(summary)
        lines_text.append(f"Read: {url}")
        lines_text.append("")
        lines_html.append(
            f"<div style='margin:24px 0;padding:16px;border-left:3px solid #d97757;background:#fafafa;'>"
            f"<h3 style='margin:0 0 8px 0;font-size:18px;'><a href='{url}' style='color:#111;text-decoration:none;'>{title}</a></h3>"
            f"<p style='margin:0 0 10px 0;font-size:14px;line-height:1.5;color:#333;'>{summary}</p>"
            f"<a href='{url}' style='font-size:14px;color:#d97757;text-decoration:none;font-weight:600;'>Read the paper →</a>"
            f"</div>"
        )
    lines_text.extend([
        "--",
        "Shane",
        "8bitconcepts.com | hello@8bitconcepts.com",
        "",
        "Unsubscribe: {unsub_url}",
    ])
    lines_html.extend([
        "<hr style='border:none;border-top:1px solid #eee;margin:32px 0;' />",
        "<p style='font-size:13px;color:#666;'>Shane — 8bitconcepts.com</p>",
        "<p style='font-size:12px;color:#999;'>Not interested? <a href='{unsub_url}' style='color:#999;'>Unsubscribe</a>.</p>",
        "</div>",
    ])
    return ("\n".join(lines_text), "\n".join(lines_html))


def send_via_resend(api_key, to_email, subject, text_body, html_body):
    payload = json.dumps({
        "from": FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "text": text_body,
        "html": html_body,
    }).encode()
    req = urllib.request.Request(
        RESEND_API_URL, data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "curl/8.7.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
            return True, data.get("id", "")
    except urllib.error.HTTPError as e:
        return False, f"{e.code}: {e.read().decode()[:200]}"
    except Exception as e:
        return False, str(e)


def load_sent():
    if SENT_FILE.exists():
        with open(SENT_FILE) as f:
            return json.load(f)
    return []


def save_sent(entries):
    with open(SENT_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def cmd_send(dry_run=False):
    papers = load_research()
    if not papers:
        print("No papers found in research.json", file=sys.stderr)
        sys.exit(1)
    subs = fetch_subscribers()
    print(f"{len(subs)} subscribers tagged '{TAG}'")
    if not subs:
        print("Nothing to send.")
        return
    text_tmpl, html_tmpl = compose_digest(papers)
    subject = "8bitconcepts: two new papers on enterprise AI"

    if dry_run:
        for s in subs[:3]:
            print(f"\n--- WOULD SEND to {s['email']} ---")
            print("Subject:", subject)
            print(text_tmpl.format(unsub_url=f"https://aidevboard.com/unsubscribe/{s['id']}"))
        return

    api_key = os.environ.get("RESEND_API_KEY") or keychain("resend-api-key")
    if not api_key:
        print("ERROR: Resend API key not available", file=sys.stderr)
        sys.exit(1)

    sent_log = load_sent()
    broadcast_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    broadcast_recipients = []
    for s in subs:
        unsub = f"https://aidevboard.com/unsubscribe/{s['id']}"
        text_body = text_tmpl.format(unsub_url=unsub)
        html_body = html_tmpl.format(unsub_url=unsub)
        ok, info = send_via_resend(api_key, s["email"], subject, text_body, html_body)
        broadcast_recipients.append({
            "email": s["email"],
            "resend_id": info if ok else None,
            "error": None if ok else info,
        })
        status = "SENT" if ok else "FAILED"
        print(f"  {status} {s['email']}: {info}")

    sent_log.append({
        "broadcast_id": broadcast_id,
        "subject": subject,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "recipient_count": len(subs),
        "success": sum(1 for r in broadcast_recipients if r["resend_id"]),
        "failed": sum(1 for r in broadcast_recipients if r["error"]),
        "recipients": broadcast_recipients,
    })
    save_sent(sent_log)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("send")
    sub.add_parser("dry-run")
    args = p.parse_args()

    if args.cmd == "send":
        cmd_send(dry_run=False)
    elif args.cmd == "dry-run":
        cmd_send(dry_run=True)


if __name__ == "__main__":
    main()
