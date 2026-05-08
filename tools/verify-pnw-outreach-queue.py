#!/usr/bin/env python3
"""Validate PNW SMB outreach target data and enrichment blockers."""

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKETING_DIR = ROOT / "marketing"
sys.path.insert(0, str(MARKETING_DIR))

from _outreach_guards import ROLE_BASED_LOCAL_PARTS, is_sendable_email

TARGETS_FILE = MARKETING_DIR / "pnw-smb-targets.csv"
SENT_FILE = MARKETING_DIR / "pnw-outreach-sent.json"
SUPPRESSIONS_FILE = MARKETING_DIR / "suppressions.json"
ENRICHMENT_FILE = MARKETING_DIR / "pnw-enrichment-queue.json"

EXPECTED_FIELDS = [
    "company_name",
    "city",
    "state",
    "industry",
    "headcount_range",
    "decision_maker_name",
    "decision_maker_role",
    "email",
    "linkedin_url",
    "website",
    "fit_note",
]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def load_json(path, default):
    if not path.exists():
        return default
    with path.open() as f:
        return json.load(f)


def is_placeholder(value):
    return value.strip().lower() == "needs linkedin outreach"


def role_based(email):
    local = email.split("@", 1)[0].strip().lower()
    return local in ROLE_BASED_LOCAL_PARTS


def main():
    errors = []
    with TARGETS_FILE.open(newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != EXPECTED_FIELDS:
            errors.append(f"unexpected csv headers: {reader.fieldnames}")
        rows = list(reader)

    sent = {
        item.get("email", "").strip().lower()
        for item in load_json(SENT_FILE, [])
        if item.get("email")
    }
    suppressed = {
        item.get("email", "").strip().lower()
        for item in load_json(SUPPRESSIONS_FILE, {}).get("emails", [])
        if item.get("email")
    }
    enrichment = load_json(ENRICHMENT_FILE, {})
    blocked = {
        (item.get("company", "").strip(), item.get("current_email", "").strip().lower())
        for item in enrichment.get("blocked_records", [])
    }

    pending_sendable = []
    unsent_role_based = []
    placeholders = []

    for line_no, row in enumerate(rows, start=2):
        if None in row:
            errors.append(f"line {line_no}: extra csv columns: {row[None]}")
        company = row.get("company_name", "").strip()
        email = row.get("email", "").strip()
        if not company:
            errors.append(f"line {line_no}: missing company_name")
        if not email:
            errors.append(f"line {line_no}: missing email placeholder or address for {company}")
            continue
        if is_placeholder(email):
            placeholders.append(company)
            continue
        if not EMAIL_RE.match(email):
            errors.append(f"line {line_no}: malformed email field for {company}: {email!r}")
            continue
        normalized = email.lower()
        if role_based(email) and normalized not in sent:
            unsent_role_based.append((company, normalized))
            if (company, normalized) not in blocked:
                errors.append(f"line {line_no}: unsent role-based address missing enrichment blocker: {company} <{email}>")
        if is_sendable_email(email) and normalized not in sent and normalized not in suppressed:
            pending_sendable.append((company, normalized))

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    print(json.dumps({
        "targets": len(rows),
        "pending_sendable": len(pending_sendable),
        "unsent_role_based_blocked": len(unsent_role_based),
        "linkedin_or_unenriched": len(placeholders),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
