#!/usr/bin/env python3
"""
8bitconcepts — Cold Outreach Email Sender

Sends personalized cold emails to CTO/CEO targets via Resend API
from hello@8bitconcepts.com (Resend-verified domain).

Usage:
    python3 marketing/outreach.py send        # send all pending targets
    python3 marketing/outreach.py dry-run     # print emails without sending
    python3 marketing/outreach.py status      # show sent/pending counts

Targets: marketing/outreach-targets.json
Sent log: marketing/outreach-sent.json

Each target has a "hook" field mapping to one of the research papers, and the
email body uses the matching template below. Hook names match research slugs.
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
TARGETS_FILE = SCRIPT_DIR / "outreach-targets.json"
SENT_FILE = SCRIPT_DIR / "outreach-sent.json"
RESEND_API_URL = "https://api.resend.com/emails"
FROM_EMAIL = "Shane at 8bitconcepts <hello@8bitconcepts.com>"


# Hook → (subject, body). Each body includes {contact}, {company}, and a
# research URL. The subject line is the hook's core claim, not a pitch.
HOOKS = {
    "integration-tax": {
        "subject": "the hidden 80% of AI cost at {company}",
        "body": """Hi {contact},

Quick note from 8bitconcepts — we do independent research on why enterprise AI programs stall.

The pattern we see most often at {company}'s stage: teams budget the model API cost carefully (sometimes obsessively) and get blindsided by the other 80% — data pipelines, integration, evaluation, and maintenance. Our rough heuristic: multiply your model cost estimate by 5x for standard integrations, 8x for complex enterprise ones.

Full breakdown: https://8bitconcepts.com/research/the-integration-tax.html

No pitch, no ask — I'm sharing this because it's the piece that gets the most reach-outs from VPs and CTOs at companies your size.

If it lands, we do a 30-min AI org diagnostic for $500 (written 24-hour turnaround): https://8bitconcepts.com/diagnostic.html

Shane
8bitconcepts | hello@8bitconcepts.com
""",
    },
    "org-chart-problem": {
        "subject": "where AI reports in {company}'s org chart",
        "body": """Hi {contact},

Quick note from 8bitconcepts — we do independent research on why enterprise AI programs stall.

The under-discussed predictor of AI outcomes we keep seeing: where AI sits in the org chart. Companies that pull AI out from under IT/Engineering and give it a P&L owner compound faster than companies that treat it as a tools layer. The reason is mostly organizational authority, not technical capability.

Wrote up the pattern here: https://8bitconcepts.com/research/the-org-chart-problem.html

No pitch — if it's useful, great. If {company} already has this figured out, I'd be curious to hear how you structured it.

Shane
8bitconcepts | hello@8bitconcepts.com
""",
    },
    "measurement-problem": {
        "subject": "the AI metric that actually predicts ROI at {company}",
        "body": """Hi {contact},

Quick note from 8bitconcepts — we do independent research on why enterprise AI programs stall.

Most orgs measure AI the wrong way: they count usage or cost avoidance and then wonder why the CFO can't see the value. The metric we've found that actually predicts ROI is "irreversible decisions per quarter" — how many decisions the AI system made that a human would have had to unwind if the AI were wrong. If the answer is "lots and no one noticed," that's the number to optimize.

Full framework: https://8bitconcepts.com/research/the-measurement-problem.html

No pitch — sending because engineering leaders at companies like {company} tend to find this frame useful when the exec layer starts asking for AI ROI proof.

Shane
8bitconcepts | hello@8bitconcepts.com
""",
    },
    "six-percent": {
        "subject": "why 94% of AI programs don't compound",
        "body": """Hi {contact},

Quick note from 8bitconcepts — we do independent research on why enterprise AI programs stall.

McKinsey put out a stat recently: 88% of companies use AI, 6% see real returns. Our read on the gap isn't the tech — it's whether the org treats AI as a compounding capability (standards, reusable skills, evaluation discipline) or a point solution (pilots, demos, one-off prompt chains).

The full breakdown of what separates the 6%: https://8bitconcepts.com/research/the-six-percent.html

No ask — just sharing because {company}'s stage is exactly where this split starts to show up on the P&L.

Shane
8bitconcepts | hello@8bitconcepts.com
""",
    },
    # Media pitch — for journalists. Different framing: leads with a data point,
    # offers as a story angle, explicitly invites follow-up interview.
    "media-integration-tax": {
        "subject": "data: AI projects are running 5-8x over budget. Here's where the cost actually goes.",
        "body": """Hi {contact},

Pitching a data piece for {company} — might be relevant to your beat.

We published research on why enterprise AI programs are consistently running 5–8x over initial budget. The pattern across real client engagements: model API cost is 10–20% of actual AI cost. The remaining 80% is data pipelines (20–30%), integration (15–25%), evaluation (10–20%), and maintenance (15–25% annually).

Concrete case in the piece: an $80K AI project that burned $74K by month four, still not in production. Model costs: $12K. The rest went to everything CFOs don't budget for.

Full research with breakdown, heuristics, and methodology: https://8bitconcepts.com/research/the-integration-tax.html

Happy to share the underlying data or do a 20-min interview if useful.

Shane Cheek
8bitconcepts — enterprise AI strategy research
hello@8bitconcepts.com
""",
    },
    "media-six-percent": {
        "subject": "McKinsey says 88% use AI, 6% see returns — what the 6% actually do differently",
        "body": """Hi {contact},

Pitching a story angle for {company}.

The McKinsey "88% use AI, 6% see returns" stat is everywhere right now. We dug into the 6% and the gap isn't what most coverage is saying — it's not model sophistication. It's organizational: the 6% treat AI as compounding capability (reusable skills, evaluation discipline, systematic standards). The 94% treat it as a sequence of point solutions.

Full analysis with case studies across Shopify, Duolingo, and late-stage B2B SaaS: https://8bitconcepts.com/research/the-six-percent.html

Happy to talk through the data or share underlying interview notes if useful for a piece.

Shane Cheek
8bitconcepts — enterprise AI strategy research
hello@8bitconcepts.com
""",
    },
    # Founder hook — tactical framing for YC-stage / early-stage founders.
    # Leads with survival math, not McKinsey's enterprise lens.
    "founder-integration-tax": {
        "subject": "for {company}: the AI cost trap enterprise buyers will push on in 6 months",
        "body": """Hi {contact},

Quick note — found {company} via YC.

Sharing a piece of research you'll almost certainly get pushed on by enterprise prospects in the next 6 months: the real cost breakdown of AI projects.

Model API cost is 10–20% of actual AI spend. Data pipelines 20–30%, integration 15–25%, evaluation 10–20%, maintenance 15–25% annually. When your enterprise buyer does their TCO analysis, this is the math they'll use — and if your pitch doesn't match, they'll wonder what you're hiding.

Full breakdown: https://8bitconcepts.com/research/the-integration-tax.html

Also written as a quick rule you can repeat in sales calls: 5x the model cost for standard deals, 8x for complex.

No ask — just thought {company}'s stage is exactly when this starts to come up in deals.

Shane
8bitconcepts | hello@8bitconcepts.com
""",
    },
    "founder-six-percent": {
        "subject": "{company}: why most AI startups never get to 'AI that compounds'",
        "body": """Hi {contact},

Quick note — found {company} via YC.

Sharing research I think is directly useful to you: 88% of companies use AI, 6% see real returns. The gap isn't tech sophistication — it's whether the org treats AI as a compounding capability (reusable skills, evaluation discipline, systematic standards) or as a series of point solutions.

For a startup, the key practical bit: the 6% put the discipline in place before they hit scale. The 94% plan to "figure it out later" and then have to rebuild their whole ML ops layer at Series B.

Full piece: https://8bitconcepts.com/research/the-six-percent.html

No ask — happy to talk through the framework if useful when you're making architecture calls.

Shane
8bitconcepts | hello@8bitconcepts.com
""",
    },
}


def load_targets():
    if not TARGETS_FILE.exists():
        return []
    with open(TARGETS_FILE) as f:
        return json.load(f)


def load_sent():
    if not SENT_FILE.exists():
        return []
    with open(SENT_FILE) as f:
        return json.load(f)


def save_sent(entries):
    with open(SENT_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def get_resend_key():
    key = os.environ.get("RESEND_API_KEY")
    if key:
        return key
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", "foundry", "-s", "resend-api-key", "-w"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        print("ERROR: Resend API key not found (env RESEND_API_KEY or Keychain foundry/resend-api-key)", file=sys.stderr)
        sys.exit(1)


def personalize(target):
    hook = target.get("hook", "integration-tax")
    tmpl = HOOKS.get(hook)
    if not tmpl:
        raise ValueError(f"unknown hook '{hook}' on target {target.get('company')}")
    subject = tmpl["subject"].format(company=target["company"])
    body = tmpl["body"].format(
        contact=target["contact_name"].split()[0],  # first name only
        company=target["company"],
    )
    return subject, body


def send_via_resend(api_key, to_email, subject, body):
    payload = json.dumps({
        "from": FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "text": body,
    }).encode()
    req = urllib.request.Request(
        RESEND_API_URL, data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Python urllib default UA triggers Cloudflare 1010 block
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


def cmd_send(dry_run=False):
    targets = load_targets()
    sent = load_sent()
    sent_emails = {e["email"].lower() for e in sent}
    pending = [t for t in targets if t["email"].lower() not in sent_emails]
    if not pending:
        print("No pending targets.")
        return
    print(f"{'DRY RUN: ' if dry_run else ''}{len(pending)} pending, sending...")
    api_key = None if dry_run else get_resend_key()
    for t in pending:
        subject, body = personalize(t)
        print(f"\n{'--'*30}\nTO: {t['contact_name']} <{t['email']}> ({t['company']})")
        print(f"SUBJECT: {subject}")
        print(f"--\n{body}")
        if dry_run:
            continue
        ok, info = send_via_resend(api_key, t["email"], subject, body)
        entry = {
            "company": t["company"],
            "contact_name": t["contact_name"],
            "email": t["email"],
            "hook": t.get("hook"),
            "subject": subject,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "resend_id": info if ok else None,
            "error": None if ok else info,
        }
        sent.append(entry)
        save_sent(sent)
        status = "SENT" if ok else "FAILED"
        print(f"  {status}: {info}")


def cmd_status():
    targets = load_targets()
    sent = load_sent()
    sent_emails = {e["email"].lower() for e in sent}
    pending = [t for t in targets if t["email"].lower() not in sent_emails]
    sent_ok = sum(1 for e in sent if not e.get("error"))
    sent_fail = len(sent) - sent_ok
    print(f"Targets:  {len(targets)}")
    print(f"Sent OK:  {sent_ok}")
    print(f"Failed:   {sent_fail}")
    print(f"Pending:  {len(pending)}")
    for t in pending:
        print(f"  - {t['contact_name']} @ {t['company']} <{t['email']}>  hook={t.get('hook')}")


FOLLOWUP_TEMPLATE = """\
Hi {contact},

Quick follow-up on my note from earlier. I wanted to make sure you saw the research on enterprise AI — it's the piece that gets the most reach-outs from VPs and CTOs at companies your size.

{hook_line}

Full piece if you have a spare 5 minutes: {url}

No ask — if the timing is off or the topic's not relevant, happy to drop it and clear your inbox.

Shane
8bitconcepts | hello@8bitconcepts.com
"""

HOOK_FOLLOWUP_LINE = {
    "integration-tax": "The short version: model API cost is only 10–20% of what enterprise AI actually costs. The 80% that eats budgets is data pipelines, integration, evaluation, maintenance.",
    "org-chart-problem": "The short version: where AI reports in your org chart predicts outcomes more than what model you're using. Most teams don't pull AI out from under IT until they've already stalled.",
    "measurement-problem": "The short version: the AI metric that predicts ROI is 'irreversible decisions the AI made per quarter.' Usage counts and cost avoidance don't correlate with actual value.",
    "six-percent": "The short version: McKinsey says 6% of companies see real returns from AI. The 6% treat AI as compounding capability, not point solutions.",
    "media-integration-tax": "The short version: AI projects consistently run 5-8x over initial budgets; the cost distribution I sent is a reusable data point.",
    "media-six-percent": "The short version: the 6% story isn't about tech sophistication — it's organizational discipline, and that's the untold angle in most coverage.",
    "founder-integration-tax": "The short version: your enterprise buyers will push on the TCO math in ~6 months. 5x the model cost for standard deals, 8x for complex.",
    "founder-six-percent": "The short version: the startups that make it to 'AI that compounds' put the discipline in place pre-scale. Retrofitting at Series B is expensive.",
}

HOOK_URL = {
    "integration-tax": "https://8bitconcepts.com/research/the-integration-tax.html",
    "org-chart-problem": "https://8bitconcepts.com/research/the-org-chart-problem.html",
    "measurement-problem": "https://8bitconcepts.com/research/the-measurement-problem.html",
    "six-percent": "https://8bitconcepts.com/research/the-six-percent.html",
    "media-integration-tax": "https://8bitconcepts.com/research/the-integration-tax.html",
    "media-six-percent": "https://8bitconcepts.com/research/the-six-percent.html",
    "founder-integration-tax": "https://8bitconcepts.com/research/the-integration-tax.html",
    "founder-six-percent": "https://8bitconcepts.com/research/the-six-percent.html",
}


def cmd_followup(after_days, dry_run=False):
    """Send follow-up to targets whose initial was delivered >= N days ago and no followup yet."""
    from datetime import datetime, timezone, timedelta
    sent = load_sent()
    # Build delivered-initial set
    cutoff = datetime.now(timezone.utc) - timedelta(days=after_days)
    initials = [e for e in sent if e.get("type", "initial") == "initial" and not e.get("error")]
    followed_up = {e["email"].lower() for e in sent if e.get("type") == "follow-up"}
    eligible = []
    for e in initials:
        if e["email"].lower() in followed_up:
            continue
        try:
            sent_at = datetime.fromisoformat(e["sent_at"].replace("Z", "+00:00"))
        except Exception:
            continue
        if sent_at > cutoff:
            continue
        eligible.append(e)
    if not eligible:
        print(f"No follow-ups due (after_days={after_days}).")
        return
    print(f"{len(eligible)} follow-ups due")
    api_key = None if dry_run else get_resend_key()
    for e in eligible:
        hook = e.get("hook", "integration-tax")
        if hook not in HOOK_FOLLOWUP_LINE:
            print(f"  SKIP unknown hook {hook} on {e.get('email')}")
            continue
        # Extract first name
        first = (e.get("contact_name") or "").split()[0] if e.get("contact_name") else "there"
        subject = "Re: " + (e.get("subject") or "8bitconcepts research")
        body = FOLLOWUP_TEMPLATE.format(
            contact=first,
            hook_line=HOOK_FOLLOWUP_LINE[hook],
            url=HOOK_URL[hook],
        )
        print(f"\n-- {e['contact_name']} <{e['email']}> --\n{subject}\n{body}")
        if dry_run:
            continue
        ok, info = send_via_resend(api_key, e["email"], subject, body)
        sent.append({
            "type": "follow-up",
            "company": e["company"],
            "contact_name": e["contact_name"],
            "email": e["email"],
            "hook": hook,
            "subject": subject,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "resend_id": info if ok else None,
            "error": None if ok else info,
            "original_resend_id": e.get("resend_id"),
        })
        save_sent(sent)
        status = "SENT" if ok else "FAILED"
        print(f"  {status}: {info}")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("send")
    sub.add_parser("dry-run")
    sub.add_parser("status")
    f = sub.add_parser("follow-up")
    f.add_argument("--after-days", type=int, default=4)
    f.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.cmd == "send":
        cmd_send(dry_run=False)
    elif args.cmd == "dry-run":
        cmd_send(dry_run=True)
    elif args.cmd == "status":
        cmd_status()
    elif args.cmd == "follow-up":
        cmd_followup(args.after_days, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
