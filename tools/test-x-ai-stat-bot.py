#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent / "x-ai-stat-bot.py"
spec = importlib.util.spec_from_file_location("x_ai_stat_bot", MODULE_PATH)
bot = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bot
assert spec.loader
spec.loader.exec_module(bot)


class XAIStatBotTests(unittest.TestCase):
    def test_canonical_fact_ignores_case_and_commas(self) -> None:
        a = bot.canonical_fact("7,040 agent-ready sites were indexed.")
        b = bot.canonical_fact("7040 AGENT-ready sites were indexed.")
        self.assertEqual(a, b)

    def test_default_x_account_is_8bitconcepts(self) -> None:
        self.assertEqual(bot.DEFAULT_ACCOUNT, "@8bitconcepts")
        self.assertEqual(bot.MIN_MINUTES, 29)
        self.assertEqual(bot.MAX_MINUTES, 114)

    def test_static_copy_is_short_and_shane_style(self) -> None:
        banned = ("new paper", "great question", "hope this helps", "thought leadership")
        for candidate in bot.STATIC_FACTS:
            copy = bot.render_copy(candidate)
            self.assertLessEqual(bot.x_weighted_length(copy), bot.MAX_POST_CHARS, candidate.fact_id)
            self.assertFalse(any(term in copy.lower() for term in banned), candidate.fact_id)

    def test_fact_key_blocks_same_fact_with_rewording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bot.LEDGER_PATH = Path(tmp) / "ledger.json"
            bot.OUTBOX_PATH = Path(tmp) / "outbox.json"
            bot.STATE_PATH = Path(tmp) / "state.json"
            candidate = bot.STATIC_FACTS[0]
            copy = bot.render_copy(candidate)
            first = bot.reserve(candidate, copy, "draft")
            self.assertEqual(first["status"], "drafted")
            with self.assertRaises(RuntimeError):
                bot.reserve(candidate, copy + "\n", "draft")

    def test_social_post_ledger_fingerprints_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bot.LEDGER_PATH = Path(tmp) / "ledger.json"
            bot.SOCIAL_LEDGER_PATH = Path(tmp) / "social.json"
            fp = bot.copy_fingerprint("same copy")
            bot.SOCIAL_LEDGER_PATH.write_text(
                json.dumps({"items": [{"status": "posted", "fingerprint": fp}]}),
                encoding="utf-8",
            )
            self.assertIn(fp, bot.blocked_fingerprints(bot.load_ledger()))

    def test_write_state_records_next_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bot.STATE_PATH = Path(tmp) / "state.json"
            bot.write_state(mode="draft", account="@8bitconcepts", random_minutes=63, next_run_at="2026-04-28T07:00:10+00:00")
            state = json.loads(bot.STATE_PATH.read_text(encoding="utf-8"))
            self.assertEqual(state["account"], "@8bitconcepts")
            self.assertEqual(state["random_minutes"], 63)
            self.assertEqual(state["next_run_at"], "2026-04-28T07:00:10+00:00")

    def test_quiet_hours_push_next_run_to_5am_pacific(self) -> None:
        now = datetime(2026, 4, 28, 5, 58, tzinfo=timezone.utc)  # 22:58 Pacific on Apr 27.
        next_run = bot.next_run_after_random_delay(now, 85)
        local = next_run.astimezone(bot.LOCAL_TZ)
        self.assertEqual(local.hour, 5)
        self.assertEqual(local.minute, 0)

    def test_quiet_hours_block_immediate_restart(self) -> None:
        now = datetime(2026, 4, 28, 7, 30, tzinfo=timezone.utc)  # 00:30 Pacific.
        quiet_end = bot.quiet_until(now)
        self.assertIsNotNone(quiet_end)
        local = quiet_end.astimezone(bot.LOCAL_TZ)
        self.assertEqual(local.hour, 5)
        self.assertEqual(local.minute, 0)


if __name__ == "__main__":
    unittest.main()
