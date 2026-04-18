#!/usr/bin/env python3
"""
8bitconcepts PNW SMB cold-email sender.
Reads pnw-smb-targets.csv, maps industries to email templates, sends via Resend API.

Usage:
    ./send-smb-outreach.py --dry-run    # Preview all sends
    ./send-smb-outreach.py --fire       # Actually send emails
"""

import csv
import subprocess
import json
import sys
from datetime import datetime
from pathlib import Path

# Template mappings: industry category -> template file + subject
INDUSTRY_TEMPLATES = {
    "Logistics & 3PL": {
        "template": "logis",
        "subject": "AI for {company} dispatch + invoicing",
    },
    "Precision Manufacturing": {
        "template": "mfg",
        "subject": "A small note about your shop floor",
    },
    "Healthcare Practice": {
        "template": "health",
        "subject": "Intake + prior auth without adding staff",
    },
    "Professional Services (Accounting)": {
        "template": "prosvc",
        "subject": "AI for {company} — without the disruption",
    },
    "Professional Services (Law)": {
        "template": "prosvc",
        "subject": "AI for {company} — without the disruption",
    },
    "Professional Services (Insurance)": {
        "template": "prosvc",
        "subject": "AI for {company} — without the disruption",
    },
    "Professional Services (Financial Advisory)": {
        "template": "prosvc",
        "subject": "AI for {company} — without the disruption",
    },
    "Specialty Trades (HVAC)": {
        "template": "trades",
        "subject": "A small note about your shop floor",
    },
    "Specialty Trades (Electrical)": {
        "template": "trades",
        "subject": "A small note about your shop floor",
    },
    "Specialty Trades (Fire Protection)": {
        "template": "trades",
        "subject": "A small note about your shop floor",
    },
    "Specialty Trades (Construction)": {
        "template": "trades",
        "subject": "A small note about your shop floor",
    },
    "Creative / Marketing Agency": {
        "template": "logis",  # Fallback to logistics template (distributor-like)
        "subject": "AI for {company} — without the disruption",
    },
    "Food & Beverage Producer": {
        "template": "logis",  # Fallback
        "subject": "Where order entry actually breaks at {company}",
    },
}

# Template bodies (simplified for dry-run; in production, read from pnw-cold-email-templates.md)
TEMPLATE_BODIES = {
    "logis": """I run 8bitconcepts — embedded AI consulting based in the PNW. I work with operating businesses like {company} on the workflows that quietly eat the most time: dispatch routing, customer email triage, invoice prep, exception handling.

I just published a piece on why most AI deployments at companies your size fail: https://8bitconcepts.com/research/the-pnw-ai-desert.html

If you've ever priced out an AI project and felt like the path between "this is interesting" and "running in our ops" had no clear bridge — that's the problem we're built to solve. We embed for 4–12 weeks, ship the system, and leave.

Worth a 30-min call to see if there's a fit?

— Shane
8bitconcepts.com/work-with-us""",

    "mfg": """Saw {company} listed. I lead 8bitconcepts — we install AI workflows inside operating businesses like yours, here in the PNW.

The workflow we hear about most often from specialty manufacturers your size: someone (often the owner) is still touching every quote, every BOM revision, every "where's my order" email. That work is the textbook AI insertion point.

Quick read on why this stalls: https://8bitconcepts.com/research/the-pnw-ai-desert.html

We embed for 4–12 weeks, ship a working system on top of whatever you already use, and hand it off to your team. Costs less than a senior hire.

Open to a 30-min call?

— Shane
8bitconcepts.com/work-with-us""",

    "health": """I run 8bitconcepts, an embedded AI consulting practice based in the PNW. We work with independent healthcare groups like {company} on the front-office work that scales worst: intake forms, scheduling triage, prior auth packet prep, post-visit summary drafts.

If you've evaluated an AI tool and bounced off because it required ripping out your current EHR/PMS — same. We work on top of what you have.

Short read on why the off-the-shelf attempts fail: https://8bitconcepts.com/research/the-pnw-ai-desert.html

If you have 30 minutes, I can walk you through what the first two workflows usually look like for a practice your size.

— Shane
8bitconcepts.com/work-with-us""",

    "prosvc": """I run 8bitconcepts — embedded AI consulting for operating businesses in the PNW. I work with firms like {company} on document-heavy workflows: client intake, document review, drafting memos, internal research, follow-up automation.

The reason most firms your size haven't moved: the off-the-shelf tools either (a) require sending client data to a vendor your engagement letter doesn't allow, or (b) replace 15% of the work and create 30% more overhead.

Worth reading: https://8bitconcepts.com/research/the-pnw-ai-desert.html — explains why the failed attempts you've heard about failed.

Open to a 30-min intro call to see if there's a fit?

— Shane
8bitconcepts.com/work-with-us""",

    "trades": """Saw {company} on the directory. I lead 8bitconcepts — we install AI workflows inside operating businesses like yours, here in the PNW.

The workflow we hear about most from shops your size: dispatch, scheduling, quote follow-ups, maintenance reminders — all still manual. That work is the textbook AI insertion point.

Quick read on why this stalls inside operating businesses: https://8bitconcepts.com/research/the-pnw-ai-desert.html

We embed for 4–12 weeks, ship a working system, and leave. Costs less than a senior hire.

Open to a 30-min call?

— Shane
8bitconcepts.com/work-with-us""",
}

def get_first_name(full_name):
    """Extract first name from decision_maker_name."""
    if not full_name or full_name.startswith("needs"):
        return None
    parts = full_name.split()
    return parts[0] if parts else None

def get_resend_api_key():
    """Fetch Resend API key from macOS Keychain."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", "foundry", "-s", "resend-api-key", "-w"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        print("ERROR: Could not fetch Resend API key from Keychain.", file=sys.stderr)
        sys.exit(1)

def send_email_via_resend(from_addr, to_addr, subject, html_body):
    """Send email via Resend API."""
    api_key = get_resend_api_key()

    cmd = [
        "curl", "-s", "-X", "POST",
        "https://api.resend.com/emails",
        "-H", f"Authorization: Bearer {api_key}",
        "-H", "Content-Type: application/json",
        "-d", json.dumps({
            "from": from_addr,
            "to": to_addr,
            "subject": subject,
            "html": html_body.replace("\n", "<br>\n")
        })
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        resp = json.loads(result.stdout)
        return resp.get("id"), resp.get("error")
    except json.JSONDecodeError:
        return None, result.stdout

def main():
    dry_run = "--dry-run" in sys.argv
    fire = "--fire" in sys.argv

    if not (dry_run or fire):
        print("Usage: ./send-smb-outreach.py --dry-run|--fire")
        sys.exit(1)

    csv_path = Path(__file__).parent / "pnw-smb-targets.csv"
    log_path = Path(__file__).parent / "outreach-log.jsonl"

    email_sends = []
    linkedin_leads = []
    skipped = []

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            company = row["company_name"].strip()
            industry = row["industry"].strip()
            email = row["email"].strip() if row["email"].strip() else None
            first_name = get_first_name(row["decision_maker_name"].strip())

            if not email or email.startswith("needs"):
                linkedin_leads.append({
                    "company": company,
                    "industry": industry,
                    "linkedin": row["linkedin_url"].strip(),
                    "fit": row["fit_note"].strip(),
                })
                continue

            if not first_name:
                skipped.append(company)
                continue

            template_key = INDUSTRY_TEMPLATES.get(industry, {}).get("template", "logis")
            subject_tmpl = INDUSTRY_TEMPLATES.get(industry, {}).get("subject", "A note about {company}")
            body_tmpl = TEMPLATE_BODIES.get(template_key, TEMPLATE_BODIES["logis"])

            subject = subject_tmpl.format(company=company)
            body = body_tmpl.format(company=company)

            email_sends.append({
                "to": email,
                "company": company,
                "first_name": first_name,
                "industry": industry,
                "subject": subject,
                "body": body,
            })

    # Dry-run output
    if dry_run:
        print(f"\n{'='*80}")
        print(f"DRY RUN: {len(email_sends)} emails ready to send")
        print(f"{'='*80}\n")

        for i, send in enumerate(email_sends, 1):
            print(f"[{i}] To: {send['to']}")
            print(f"    Company: {send['company']} ({send['industry']})")
            print(f"    Subject: {send['subject']}")
            print(f"    Body preview: {send['body'][:100]}...\n")

        print(f"\n{'='*80}")
        print(f"{len(linkedin_leads)} leads need LinkedIn outreach (no email on file):")
        for lead in linkedin_leads[:5]:
            print(f"  - {lead['company']} ({lead['industry']}): {lead['linkedin']}")
        if len(linkedin_leads) > 5:
            print(f"  ... and {len(linkedin_leads) - 5} more")

        print(f"\nSkipped (no first name): {len(skipped)}")
        print(f"\nTo send for real: ./send-smb-outreach.py --fire")

    # Fire
    if fire:
        print(f"\nSending {len(email_sends)} emails...\n")
        success = 0
        failed = 0

        for send in email_sends:
            email_id, error = send_email_via_resend(
                "shane-cheek@8bitconcepts.com",
                send["to"],
                send["subject"],
                send["body"]
            )

            if email_id:
                print(f"✓ {send['to']} ({send['company']})")
                success += 1
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "to": send["to"],
                    "company": send["company"],
                    "industry": send["industry"],
                    "email_id": email_id,
                    "status": "sent"
                }
            else:
                print(f"✗ {send['to']} ({send['company']}): {error}")
                failed += 1
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "to": send["to"],
                    "company": send["company"],
                    "error": error,
                    "status": "failed"
                }

            # Append to log
            with open(log_path, "a") as log_f:
                log_f.write(json.dumps(log_entry) + "\n")

        print(f"\n{'='*80}")
        print(f"Complete: {success} sent, {failed} failed")
        print(f"Log: {log_path}")
        print(f"\nFollow-ups auto-fire 4 days after each send (launchd job).")
        print(f"LinkedIn outreach ({len(linkedin_leads)} targets) manual.")

if __name__ == "__main__":
    main()
