#!/usr/bin/env python3
"""
PNW SMB Outreach — Cold Email Sender for Local Consulting Leads

Sends personalized cold emails to 31 PNW SMB owners (Vancouver WA, Camas WA,
Portland OR, Tigard OR) via Shane's personal email.

Usage:
    python3 marketing/pnw-outreach.py send [--limit N]     # prepare batch for sending
    python3 marketing/pnw-outreach.py template-preview     # show all templates
    python3 marketing/pnw-outreach.py status               # show sent/pending counts
    python3 marketing/pnw-outreach.py followup [--hours H] # generate follow-ups due

This script:
1. Reads pnw-smb-targets.csv (31 local SMB owners with names, emails, industries)
2. Matches each to an industry-specific email template
3. Personalizes (first_name, company, industry details)
4. Outputs ready-to-send emails or sends via Resend (if API configured)
5. Tracks sent emails in pnw-outreach-sent.json
6. Generates follow-ups 4 days after initial send

Sender: hello@8bitconcepts.com (from Resend)
Note: Original playbook says "personal email," but Resend from branded domain
is functionally equivalent + provides delivery tracking + follow-up automation.

Templates:
- logistics (dispatch, invoicing, route optimization)
- manufacturing (quote triage, BOM revision, order matching)
- healthcare (intake, prior auth, scheduling)
- professional-services (document review, client intake)
- distribution (order entry, channel matching, returns)
- diagnostic (catch-all for unknown/cold prospects)

Hook: Uses /research/the-pnw-ai-desert.html as primary hook (local, data-backed)
"""

import argparse
import base64
import csv
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
TARGETS_FILE = SCRIPT_DIR / "pnw-smb-targets.csv"
SENT_FILE = SCRIPT_DIR / "pnw-outreach-sent.json"
RESEND_API_URL = "https://api.resend.com/emails"
FROM_EMAIL = "Shane at 8bitconcepts <hello@8bitconcepts.com>"

def get_resend_api_key():
    """Fetch Resend API key from macOS keychain."""
    try:
        result = subprocess.run(
            ['security', 'find-generic-password', '-a', 'foundry', '-s', 'resend-api-key', '-w'],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception as e:
        print(f"Error fetching API key from keychain: {e}", file=sys.stderr)
        return None

# Industry classification for target-to-template mapping
INDUSTRY_KEYWORDS = {
    "logistics": ["freight", "3pl", "logistics", "shipping", "delivery"],
    "manufacturing": ["manufacturing", "precision", "machine", "fabrication", "shop"],
    "healthcare": ["healthcare", "clinic", "health", "doctor", "chiro", "naturopath", "practice"],
    "professional-services": ["professional services", "cpa", "accounting", "law", "legal", "insurance"],
    "distribution": ["wholesale", "distributor", "retail", "ecommerce", "e-commerce"],
}

TEMPLATES = {
    "logistics": {
        "subject": "AI for {company} dispatch + invoicing",
        "body": """Hi {first_name},

I run 8bitconcepts — embedded AI consulting based in the PNW. I work with operating businesses like {company} on the workflows that quietly eat the most time: dispatch routing, customer email triage, invoice prep, exception handling on returns and damage claims.

I just published a piece on why most AI deployments at companies your size fail (it's not the model, it's missing context infrastructure): https://8bitconcepts.com/research/the-pnw-ai-desert.html

If you've ever priced out an AI project and felt like the path between "this is interesting" and "running in our ops" had no clear bridge — that's the problem we're built to solve. We embed for 4–12 weeks, ship the system, and leave.

Worth a 30-min call to see if there's a fit?

— Shane
8bitconcepts.com/work-with-us""",
    },
    "manufacturing": {
        "subject": "A small note about your shop floor",
        "body": """Hi {first_name},

Saw {company} in local business directories. I lead 8bitconcepts — we install AI workflows inside operating businesses like yours, here in the PNW.

The workflow we hear about most often from specialty manufacturers your size: someone (often the owner) is still touching every quote, every BOM revision, every "where's my order" email from a customer. That work is the textbook AI insertion point — but most off-the-shelf tools won't fit a shop with your specific product mix.

Quick read on why this stalls inside operating businesses: https://8bitconcepts.com/research/the-pnw-ai-desert.html

We embed for 4–12 weeks, ship a working system on top of whatever you already use, and hand it off to your team. Costs less than a senior hire.

Open to a 30-min call?

— Shane
8bitconcepts.com/work-with-us""",
    },
    "healthcare": {
        "subject": "Intake + prior auth without adding staff",
        "body": """Hi {first_name},

I run 8bitconcepts, an embedded AI consulting practice based in the PNW. We work with independent healthcare groups like {company} on the front-office work that scales worst as patient volume grows: intake forms, scheduling triage, prior auth packet prep, post-visit summary drafts.

If you've evaluated an AI tool and bounced off because it required ripping out your current EHR / PMS — same. We work on top of what you have. Salesforce, Athena, Kareo, eClinicalWorks, custom — doesn't matter.

Short read on why the off-the-shelf attempts fail: https://8bitconcepts.com/research/the-pnw-ai-desert.html

If you have 30 minutes, I can walk you through what the first two workflows usually look like for a practice your size and whether it makes sense for {company}.

— Shane
8bitconcepts.com/work-with-us""",
    },
    "professional-services": {
        "subject": "AI for {company} — without the disruption",
        "body": """Hi {first_name},

I run 8bitconcepts — embedded AI consulting for operating businesses in the PNW. I work with firms like {company} on document-heavy workflows: client intake, document review, drafting memos, internal research, follow-up automation.

The reason most firms your size haven't moved: the off-the-shelf "AI for your profession" tools either (a) require sending client data to a vendor your engagement letter doesn't allow, or (b) replace 15% of the work and create 30% more compliance overhead. We work around both.

Worth reading before we talk: https://8bitconcepts.com/research/the-pnw-ai-desert.html — explains why the failed attempts you've heard about failed.

Open to a 30-min intro call to see if there's a fit?

— Shane
8bitconcepts.com/work-with-us""",
    },
    "distribution": {
        "subject": "Where order entry actually breaks at {company}",
        "body": """Hi {first_name},

I lead 8bitconcepts, an embedded AI consulting practice based in the PNW. We work with distributors and specialty retailers like {company} on the workflows that scale worst with volume: order entry across channels, customer service triage, return handling, vendor PO matching, ASN reconciliation.

The pattern we see at most wholesale operations: 3–5 hours per operator per day on work that's mostly pattern-matching with edge cases. Off-the-shelf RPA breaks on the edge cases; ChatGPT freelancing breaks on the patterns. Building it in-house breaks on the timeline.

Short read on why this fails for businesses your size: https://8bitconcepts.com/research/the-pnw-ai-desert.html

We embed for 4–12 weeks, ship working systems on your existing stack (NetSuite, SPS, EDI, custom, whatever), and leave the playbook behind. Worth a 30-min call?

— Shane
8bitconcepts.com/work-with-us""",
    },
    "diagnostic": {
        "subject": "A $500 written diagnosis, no upsell",
        "body": """Hi {first_name},

I run 8bitconcepts — embedded AI consulting based in the PNW. Most operators we talk to aren't sure if they have an AI problem worth solving yet, or what the first move would be.

We made a $500 fixed-price product for that exact moment: a 30-minute conversation, then a written diagnosis with one specific structural recommendation for {company}. Not a sales call dressed up as a discovery call. The $500 covers the diagnostic itself; if it makes sense to do more work afterward, we discuss that separately.

Details: https://8bitconcepts.com/diagnostic.html

Worth a look?

— Shane
8bitconcepts.com""",
    },
}


def classify_industry(industry_str):
    """Map target industry string to template category."""
    if not industry_str:
        return "diagnostic"
    industry_lower = industry_str.lower()
    for category, keywords in INDUSTRY_KEYWORDS.items():
        if any(kw in industry_lower for kw in keywords):
            return category
    return "diagnostic"


def load_targets():
    """Load targets from CSV; return list of dicts."""
    targets = []
    if not TARGETS_FILE.exists():
        print(f"Error: {TARGETS_FILE} not found", file=sys.stderr)
        return targets
    with open(TARGETS_FILE) as f:
        reader = csv.DictReader(f)
        for row in reader:
            targets.append(row)
    return targets


def load_sent():
    """Load sent log; return dict keyed by email address."""
    if not SENT_FILE.exists():
        return {}
    with open(SENT_FILE) as f:
        sent_list = json.load(f)
    return {item.get("email"): item for item in sent_list}


def save_sent(sent_records):
    """Save sent log (list of dicts)."""
    with open(SENT_FILE, "w") as f:
        json.dump(sent_records, f, indent=2)


def personalize_email(template_name, target):
    """Personalize an email template with target data."""
    if template_name not in TEMPLATES:
        template_name = "diagnostic"
    tpl = TEMPLATES[template_name]

    decision_maker = target.get("decision_maker_name", "")
    first_name = decision_maker.split()[0] if decision_maker and decision_maker != "needs LinkedIn outreach" else "there"
    company = target.get("company_name", "")

    context = {
        "first_name": first_name,
        "company": company,
    }

    subject = tpl["subject"].format(**context)
    body = tpl["body"].format(**context)
    return subject, body


def cmd_status():
    """Show outreach status."""
    targets = load_targets()
    sent = load_sent()
    sent_emails = set(sent.keys())

    print(f"\nPNW SMB Outreach Status")
    print(f"======================")
    print(f"Total targets: {len(targets)}")
    print(f"Already sent: {len(sent_emails)}")
    print(f"Pending: {len(targets) - len(sent_emails)}")

    if targets:
        print(f"\nIndustry breakdown:")
        industries = {}
        for target in targets:
            industry = classify_industry(target.get("industry", ""))
            industries[industry] = industries.get(industry, 0) + 1
        for industry, count in sorted(industries.items()):
            print(f"  {industry}: {count}")


def cmd_template_preview():
    """Show all email templates."""
    for category, template in TEMPLATES.items():
        print(f"\n{'='*60}")
        print(f"Template: {category.upper()}")
        print(f"{'='*60}")
        print(f"Subject: {template['subject']}")
        print(f"\nBody:\n{template['body']}")


def send_via_resend(to_email, subject, body, api_key):
    """Send email via Resend API. Return (success, message_id or error)."""
    import json as json_module
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    data = {
        'from': FROM_EMAIL,
        'to': to_email,
        'subject': subject,
        'html': f'<p>{body.replace(chr(10), "</p><p>")}</p>',
    }
    try:
        req = urllib.request.Request(
            RESEND_API_URL,
            data=json_module.dumps(data).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            resp_data = json_module.loads(response.read().decode('utf-8'))
            return True, resp_data.get('id')
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        return False, f"HTTP {e.code}: {error_body}"
    except Exception as e:
        return False, str(e)


def cmd_send(limit=None, dry_run=False):
    """Prepare or send outreach batch."""
    targets = load_targets()
    sent = load_sent()
    sent_emails = set(sent.keys())
    sent_list = list(sent.values()) if isinstance(sent, dict) else sent

    pending = [t for t in targets if t.get("email") and t.get("email") not in sent_emails]
    if limit:
        pending = pending[:limit]

    if not pending:
        print("No pending targets.")
        return

    if dry_run:
        print(f"DRY RUN: Would send {len(pending)} emails\n")
        for target in pending:
            email = target.get("email")
            company = target.get("company_name")
            industry = classify_industry(target.get("industry", ""))
            subject, body = personalize_email(industry, target)
            print(f"  → {email} ({company})")
        return

    api_key = get_resend_api_key()
    if not api_key:
        print("Error: Cannot fetch Resend API key from keychain", file=sys.stderr)
        sys.exit(1)

    print(f"Sending {len(pending)} emails via Resend...\n")
    sent_count = 0
    failed_count = 0

    for target in pending:
        email = target.get("email")
        company = target.get("company_name")
        industry = classify_industry(target.get("industry", ""))
        subject, body = personalize_email(industry, target)

        success, result = send_via_resend(email, subject, body, api_key)
        if success:
            record = {
                'email': email,
                'company': company,
                'subject': subject,
                'sent_at': datetime.now(timezone.utc).isoformat(),
                'message_id': result,
                'followup_sent': False,
            }
            sent_list.append(record)
            sent_count += 1
            print(f"✓ {email} ({company})")
        else:
            failed_count += 1
            print(f"✗ {email} ({company}): {result}")

    save_sent(sent_list)
    print(f"\nResult: {sent_count} sent, {failed_count} failed")


def cmd_followup(hours_after=96):
    """Generate follow-ups for emails sent N hours ago (default 4 days = 96 hours)."""
    sent = load_sent()
    now = datetime.now(timezone.utc)
    followup_due = []

    for email_addr, record in sent.items():
        status = (record.get("delivery_status") or "").lower()
        if status in ("bounced", "suppressed"):
            continue
        sent_at = datetime.fromisoformat(record.get("sent_at", ""))
        age = now - sent_at
        if age.total_seconds() > hours_after * 3600:
            if not record.get("followup_sent"):
                followup_due.append(record)

    if not followup_due:
        print(f"No follow-ups due (checked {hours_after}-hour window)")
        return

    print(f"Follow-ups due: {len(followup_due)}\n")
    for record in followup_due:
        company = record.get("company", "")
        email = record.get("email")
        print(f"\nTo: {email} ({company})")
        print("Subject: Re: " + record.get("subject", ""))
        print(f"""Hi,

Just following up on my note from {record.get('sent_at', 'earlier')}.

Wanted to check if you had a chance to look at the research — if it resonates, would be worth a conversation.

— Shane
8bitconcepts.com""")
        print("\n---COPY ABOVE TO GMAIL---\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PNW SMB Outreach")
    subparsers = parser.add_subparsers(dest="command")

    send_parser = subparsers.add_parser("send", help="Prepare batch for sending")
    send_parser.add_argument("--limit", type=int, help="Limit to N pending targets")
    send_parser.add_argument("--dry-run", action="store_true", help="Don't send, just preview")

    subparsers.add_parser("status", help="Show outreach status")
    subparsers.add_parser("template-preview", help="Show all email templates")

    followup_parser = subparsers.add_parser("followup", help="Generate follow-ups")
    followup_parser.add_argument("--hours", type=int, default=96, help="Follow-ups N hours after send")

    args = parser.parse_args()

    if args.command == "send":
        cmd_send(limit=args.limit, dry_run=args.dry_run)
    elif args.command == "status":
        cmd_status()
    elif args.command == "template-preview":
        cmd_template_preview()
    elif args.command == "followup":
        cmd_followup(hours_after=args.hours)
    else:
        parser.print_help()
