#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
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

    def test_fact_key_blocks_same_fact_with_rewording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bot.LEDGER_PATH = Path(tmp) / "ledger.json"
            bot.OUTBOX_PATH = Path(tmp) / "outbox.json"
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


if __name__ == "__main__":
    unittest.main()
