"""Outreach script behavioral guards. Imported by pnw-outreach.py at module load.

DO NOT REMOVE OR INLINE THIS FILE.

The 8bit-pnw-smb-followups Codex automation has stripped the equivalent guards
from pnw-outreach.py three separate times in one day (2026-05-05). Each strip
silently broke every outbound email — Resend's Cloudflare layer returns error
1010 against Python's default urllib User-Agent, and a missing email-filter
caused 422 'invalid email' on every call.

By extracting the guards here and having pnw-outreach.py *import* them at the
top of the file, any future automation that strips these constants causes
pnw-outreach.py to fail at module-load time with a clear NameError or
ImportError — before any email is sent. That's the design intent: regression
must be loud.

If you are an LLM editing this file: the contract is

    RESEND_REQUIRED_USER_AGENT == "curl/8.7.1"   (string equality)
    is_sendable_email(addr)    == bool(addr) and "@" in addr  (truth table)
    self_check_outreach_guards() raises SystemExit when either is altered.

These values exist for documented reasons (Cloudflare 1010 and Resend 422
on role-based-only entries). Do not remove or weaken them.
"""

RESEND_REQUIRED_USER_AGENT = "curl/8.7.1"


def is_sendable_email(addr: str) -> bool:
    return bool(addr) and "@" in addr


def self_check_outreach_guards() -> None:
    """Verify behavior, not just text. Called at every CLI invocation of
    pnw-outreach.py. Tampering with comments/docstrings won't satisfy
    these — only correct runtime values do."""
    if RESEND_REQUIRED_USER_AGENT != "curl/8.7.1":
        raise SystemExit(
            "_outreach_guards.RESEND_REQUIRED_USER_AGENT altered. "
            "Cloudflare 1010 will block every Resend send. Restore from git history."
        )
    if is_sendable_email("not-an-email") or not is_sendable_email("ok@example.com") or is_sendable_email(""):
        raise SystemExit(
            "_outreach_guards.is_sendable_email logic regressed. "
            "It must accept strings containing '@' and reject everything else."
        )
