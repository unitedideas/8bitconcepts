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
    is_sendable_email(addr)    == a non-role, syntactically usable email.
    self_check_outreach_guards() raises SystemExit when either is altered.

These values exist for documented reasons: Cloudflare 1010, Resend 422 on
placeholder entries, and the observed bounce/suppression risk of role-based
SMB outreach addresses. Do not remove or weaken them.
"""

RESEND_REQUIRED_USER_AGENT = "curl/8.7.1"
ROLE_BASED_LOCAL_PARTS = {
    "admin",
    "ask",
    "careers",
    "contact",
    "feedback",
    "hello",
    "help",
    "hi",
    "hiring",
    "hr",
    "info",
    "jobs",
    "no-reply",
    "office",
    "people",
    "recruiter",
    "recruiting",
    "sales",
    "support",
    "ta",
    "talent",
    "team",
}


def is_sendable_email(addr: str) -> bool:
    if not addr or "@" not in addr:
        return False
    local_part = addr.split("@", 1)[0].strip().lower()
    return bool(local_part) and local_part not in ROLE_BASED_LOCAL_PARTS


def self_check_outreach_guards() -> None:
    """Verify behavior, not just text. Called at every CLI invocation of
    pnw-outreach.py. Tampering with comments/docstrings won't satisfy
    these — only correct runtime values do."""
    if RESEND_REQUIRED_USER_AGENT != "curl/8.7.1":
        raise SystemExit(
            "_outreach_guards.RESEND_REQUIRED_USER_AGENT altered. "
            "Cloudflare 1010 will block every Resend send. Restore from git history."
        )
    if (
        is_sendable_email("not-an-email")
        or not is_sendable_email("ok@example.com")
        or is_sendable_email("info@example.com")
        or is_sendable_email("hello@example.com")
        or is_sendable_email("sales@example.com")
        or is_sendable_email("")
    ):
        raise SystemExit(
            "_outreach_guards.is_sendable_email logic regressed. "
            "It must accept non-role emails and reject placeholders plus role-based local parts."
        )
