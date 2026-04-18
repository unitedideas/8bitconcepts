#!/usr/bin/env python3
"""
8bitconcepts PNW SMB cold-outreach sender.
Fires pre-templated emails to the 31-target list.

USAGE:
  ./send-smb-outreach.py --sender-email shane@example.com --batch 1 --dry-run
  ./send-smb-outreach.py --sender-email shane@example.com --batch 1

Sender decision (Shane makes this once):
  Option A: fresh domain outreach@8bitconcepts.com (2-week warmup, ~$15/yr)
  Option B: personal email shane@..., ~10/day cap

Once sender is decided, replace --sender-email with the chosen address.
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict

def load_targets(csv_path: str) -> List[Dict]:
    targets = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('company_name'):
                targets.append(row)
    return targets

def get_first_name(full_name: str) -> str:
    if not full_name or full_name == 'needs LinkedIn outreach':
        return ''
    return full_name.split()[0]

def assign_template(industry: str) -> str:
    """Map industry to email template."""
    if any(x in industry for x in ['Logistics', '3PL']):
        return 'template_1_logistics'
    elif any(x in industry for x in ['Manufacturing', 'Machining', 'Fabrication']):
        return 'template_2_manufacturing'
    elif any(x in industry for x in ['Healthcare', 'Medical', 'Chiropractic']):
        return 'template_3_healthcare'
    elif any(x in industry for x in ['Law', 'Accounting', 'Insurance']):
        return 'template_4_professional'
    elif any(x in industry for x in ['Wholesale', 'Food', 'Agency', 'Creative']):
        return 'template_5_distribution'
    else:
        return 'template_6_cooler'

def get_email_body(template: str, first_name: str, company: str) -> tuple[str, str]:
    """Return (subject, body) for the template."""

    if template == 'template_1_logistics':
        subject = f"AI for {company} dispatch + invoicing"
        body = f"""Hi {first_name},

I run 8bitconcepts — embedded AI consulting based in the PNW. I work with operating businesses like {company} on the workflows that quietly eat the most time: dispatch routing, customer email triage, invoice prep, exception handling on returns and damage claims.

I just published a piece on why most AI deployments at companies your size fail (it's not the model, it's missing context infrastructure): https://8bitconcepts.com/research/the-pnw-ai-desert.html

If you've ever priced out an AI project and felt like the path between "this is interesting" and "running in our ops" had no clear bridge — that's the problem we're built to solve. We embed for 4–12 weeks, ship the system, and leave.

Worth a 30-min call to see if there's a fit?

— Shane
8bitconcepts.com/work-with-us"""

    elif template == 'template_2_manufacturing':
        subject = "A small note about your shop floor"
        body = f"""Hi {first_name},

Saw {company} noted in the PNW business community. I lead 8bitconcepts — we install AI workflows inside operating businesses like yours, here in the PNW.

The workflow we hear about most often from specialty manufacturers your size: someone (often the owner) is still touching every quote, every BOM revision, every "where's my order" email from a customer. That work is the textbook AI insertion point — but most off-the-shelf tools won't fit a shop with your specific product mix.

Quick read on why this stalls inside operating businesses: https://8bitconcepts.com/research/the-pnw-ai-desert.html

We embed for 4–12 weeks, ship a working system on top of whatever you already use, and hand it off to your team. Costs less than a senior hire.

Open to a 30-min call?

— Shane
8bitconcepts.com/work-with-us"""

    elif template == 'template_3_healthcare':
        subject = "Intake + prior auth without adding staff"
        body = f"""Hi {first_name},

I run 8bitconcepts, an embedded AI consulting practice based in the PNW. We work with independent healthcare groups like {company} on the front-office work that scales worst as patient volume grows: intake forms, scheduling triage, prior auth packet prep, post-visit summary drafts.

If you've evaluated an AI tool and bounced off because it required ripping out your current EHR / PMS — same. We work on top of what you have. Salesforce, Athena, Kareo, eClinicalWorks, custom — doesn't matter.

Short read on why the off-the-shelf attempts fail: https://8bitconcepts.com/research/the-pnw-ai-desert.html

If you have 30 minutes, I can walk you through what the first two workflows usually look like for a practice your size and whether it makes sense for {company}.

— Shane
8bitconcepts.com/work-with-us"""

    elif template == 'template_4_professional':
        subject = "AI for {company} — without the disruption"
        body = f"""Hi {first_name},

I run 8bitconcepts — embedded AI consulting for operating businesses in the PNW. I work with firms like {company} on document-heavy workflows: client intake, document review, drafting memos and demand letters, internal research, follow-up automation.

The reason most firms your size haven't moved: the off-the-shelf "AI for your field" tools either (a) require sending client data to a vendor your engagement letter doesn't allow, or (b) replace 15% of the work and create 30% more compliance overhead. We work around both.

Worth reading before we talk: https://8bitconcepts.com/research/the-pnw-ai-desert.html — explains why the failed attempts you've heard about failed.

Open to a 30-min intro call to see if there's a fit?

— Shane
8bitconcepts.com/work-with-us"""

    elif template == 'template_5_distribution':
        subject = f"Where order entry actually breaks at {company}"
        body = f"""Hi {first_name},

I lead 8bitconcepts, an embedded AI consulting practice based in the PNW. We work with distributors and specialty retailers like {company} on the workflows that scale worst with volume: order entry across channels, customer service triage, return handling, vendor PO matching, ASN reconciliation.

The pattern we see at most wholesale operations: 3–5 hours per operator per day on work that's mostly pattern-matching with edge cases. Off-the-shelf RPA breaks on the edge cases; ChatGPT freelancing breaks on the patterns. Building it in-house breaks on the timeline.

Short read on why this fails for businesses your size: https://8bitconcepts.com/research/the-pnw-ai-desert.html

We embed for 4–12 weeks, ship working systems on your existing stack (NetSuite, SPS, EDI, custom, whatever), and leave the playbook behind. Worth a 30-min call?

— Shane
8bitconcepts.com/work-with-us"""

    else:  # template_6_cooler
        subject = "A $500 written diagnosis, no upsell"
        body = f"""Hi {first_name},

I run 8bitconcepts — embedded AI consulting based in the PNW. Most operators we talk to aren't sure if they have an AI problem worth solving yet, or what the first move would be.

We made a $500 fixed-price product for that exact moment: a 30-minute conversation, then a written diagnosis with one specific structural recommendation for {company}. Not a sales call dressed up as a discovery call. The $500 covers the diagnostic itself; if it makes sense to do more work afterward, we discuss that separately.

Details: https://8bitconcepts.com/diagnostic.html

Worth a look?

— Shane
8bitconcepts.com"""

    return subject, body

def render_batch(targets: List[Dict], batch_number: int = 1, batch_size: int = 10) -> List[Dict]:
    """Render emails for a batch of targets."""
    start_idx = (batch_number - 1) * batch_size
    end_idx = start_idx + batch_size

    batch_targets = [t for t in targets if t.get('email') and t['email'] != 'needs LinkedIn outreach']
    batch = batch_targets[start_idx:end_idx]

    rendered = []
    for i, target in enumerate(batch, 1):
        first_name = get_first_name(target['decision_maker_name'])
        template = assign_template(target.get('industry', ''))
        subject, body = get_email_body(template, first_name, target['company_name'])

        rendered.append({
            'sequence': i,
            'company': target['company_name'],
            'recipient_name': target['decision_maker_name'],
            'recipient_email': target['email'],
            'industry': target['industry'],
            'template': template,
            'subject': subject,
            'body': body,
            'city': target['city'],
            'state': target['state'],
        })

    return rendered

def main():
    parser = argparse.ArgumentParser(description='8bitconcepts PNW SMB outreach sender')
    parser.add_argument('--sender-email', required=True, help='From email address (once decided)')
    parser.add_argument('--batch', type=int, default=1, help='Batch number (1-based)')
    parser.add_argument('--batch-size', type=int, default=10, help='Emails per batch')
    parser.add_argument('--dry-run', action='store_true', help='Preview without sending')
    parser.add_argument('--format', choices=['json', 'text'], default='text', help='Output format')

    args = parser.parse_args()

    # Load targets
    csv_path = Path(__file__).parent.parent / 'marketing' / 'pnw-smb-targets.csv'
    targets = load_targets(str(csv_path))

    # Render batch
    batch = render_batch(targets, args.batch, args.batch_size)

    if not batch:
        print(f"No targets for batch {args.batch}")
        sys.exit(1)

    if args.format == 'json':
        print(json.dumps(batch, indent=2))
    else:
        print(f"=== BATCH {args.batch} — {len(batch)} emails ===")
        print(f"Sender: {args.sender_email}")
        if args.dry_run:
            print("MODE: DRY RUN (preview only)\n")

        for email in batch:
            print(f"\n[{email['sequence']}] To: {email['recipient_name']} <{email['recipient_email']}>")
            print(f"    Company: {email['company']} ({email['city']}, {email['state']})")
            print(f"    Industry: {email['industry']}")
            print(f"    Template: {email['template']}")
            print(f"    Subject: {email['subject']}")
            print(f"    Body preview: {email['body'][:100]}...")

        if args.dry_run:
            print(f"\n✓ Preview complete. Ready to send {len(batch)} emails.")
            print(f"  Run without --dry-run to send.")
        else:
            print(f"\n✓ Would send {len(batch)} emails via {args.sender_email}")
            print(f"  SMTP integration not yet implemented — see send_via_resend() below")

if __name__ == '__main__':
    main()
