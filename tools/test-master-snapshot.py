"""Snapshot publication regressions using public API fixtures captured 2026-11-24."""
import contextlib
import copy
import importlib.util
import io
import json
import re
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location("master_snapshot", ROOT / "regenerate-master-snapshot.py")
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)
STATS = json.loads((ROOT / "fixtures/master-snapshot/adb-stats.json").read_text())
DIGEST = json.loads((ROOT / "fixtures/master-snapshot/nhs-digest.json").read_text())


class MasterSnapshotTests(unittest.TestCase):
    def render(self, stats=None, digest=None):
        return snapshot.build_markdown(
            copy.deepcopy(STATS) if stats is None else stats,
            copy.deepcopy(DIGEST) if digest is None else digest,
            "2026-11-24",
        )

    def run_main(self, stats, publisher=False, arguments=()):
        seen = []

        def fetch(url):
            seen.append(url)
            if url == snapshot.ADB_STATS_URL:
                return stats
            if url == snapshot.NHS_DIGEST_URL:
                return copy.deepcopy(DIGEST)
            raise AssertionError("Unexpected source fetch")

        with patch.object(snapshot, "http_get_json", side_effect=fetch), \
                patch.object(snapshot, "update_gist", return_value=publisher) as publish, \
                patch("sys.argv", ["snapshot", *arguments]), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = snapshot.main()
        self.assertEqual(seen, [snapshot.ADB_STATS_URL, snapshot.NHS_DIGEST_URL])
        return code, publish.call_count

    def test_captured_data_has_real_counts_and_scoped_observations(self):
        text = self.render()
        self.assertIn("| Active AI/ML engineering roles | **9,116** |", text)
        self.assertIn("| Hiring companies indexed | **440** |", text)
        self.assertIn("| Entries marked MCP-verified by NHS | **967** (15.0%) |", text)
        self.assertRegex(text, r"\| \d+ \| OpenAI \| 410 \|")
        self.assertIn("`agents` appears on 3,009 indexed roles", text)
        self.assertIn("Correction (2026-11-24)", text)
        self.assertNotIn("documentation-only", text)
        self.assertNotIn("Research premium", text)
        self.assertNotIn("Q2 2026 Live Snapshot", text)
        self.assertNotIn("auto-refreshed weekly", text)
        self.assertIn("utm_source=github-gist&utm_medium=referral&utm_campaign=master-snapshot", text)

    def test_tables_sort_counts_and_keep_unknown_workplace_labels(self):
        stats = copy.deepcopy(STATS)
        stats["companies"].reverse()
        stats["tags"].reverse()
        stats["workplace"].append({"type": "unspecified", "count": 3, "avg_salary": 0})
        text = self.render(stats)
        counts = [int(value.replace(",", "")) for value in
                  re.findall(r"^\| \d+ \| [^|]+ \| ([\d,]+) \|", text, re.MULTILINE)]
        self.assertEqual(len(counts), 10)
        self.assertTrue(all(left >= right for left, right in zip(counts, counts[1:])))
        self.assertEqual(counts[0], 410)
        self.assertIn("`agents` appears on 3,009 indexed roles", text)
        self.assertIn("| Unspecified | 3 | Not reported |", text)

    def test_missing_malformed_or_empty_sources_cannot_render(self):
        cases = [({}, copy.deepcopy(DIGEST)), ([], copy.deepcopy(DIGEST))]
        for key, value in [("total_jobs", 0), ("total_jobs", True), ("jobs_with_salary", 100000)]:
            stats = copy.deepcopy(STATS)
            stats["overview"][key] = value
            cases.append((stats, copy.deepcopy(DIGEST)))
        for key in ["tags", "companies", "workplace", "experience_levels"]:
            stats = copy.deepcopy(STATS)
            stats[key] = []
            cases.append((stats, copy.deepcopy(DIGEST)))
        stats = copy.deepcopy(STATS)
        del stats["companies"][0]["roles"]
        cases.append((stats, copy.deepcopy(DIGEST)))
        stats = copy.deepcopy(STATS)
        stats["salary"]["median"] = float("nan")
        cases.append((stats, copy.deepcopy(DIGEST)))
        for key, value in [("total_sites", 0), ("mcp_verified", -1), ("mcp_verified", 100000), ("generated_at", None)]:
            digest = copy.deepcopy(DIGEST)
            digest[key] = value
            cases.append((copy.deepcopy(STATS), digest))
        for stats, digest in cases:
            with self.subTest(stats_type=type(stats).__name__, digest=digest):
                with self.assertRaises(ValueError):
                    self.render(stats, digest)

    def test_verified_zero_mcp_count_is_not_treated_as_missing(self):
        digest = copy.deepcopy(DIGEST)
        digest["mcp_verified"] = 0
        self.assertIn("**0** (0.0%)", self.render(digest=digest))

    def test_missing_hiring_data_never_reaches_publisher(self):
        self.assertEqual(self.run_main({}), (2, 0))
        self.assertEqual(self.run_main([]), (2, 0))

    def test_dry_run_fetches_and_renders_without_publishing(self):
        self.assertEqual(self.run_main(copy.deepcopy(STATS), arguments=["--dry-run"]), (0, 0))

    def test_publication_failure_returns_failure(self):
        self.assertEqual(self.run_main(copy.deepcopy(STATS), publisher=False), (1, 1))

    def test_once_preserves_existing_publication_behavior(self):
        self.assertEqual(self.run_main(copy.deepcopy(STATS), publisher=True, arguments=["--once"]), (0, 1))

    def gist_document(self, content="old", owner="unitedideas", public=True):
        return {"owner": {"login": owner}, "public": public,
                "description": snapshot.GIST_DESCRIPTION,
                "files": {snapshot.GIST_MD_FILENAME: {"content": content}}}

    def publish_result(self, responses):
        replies = [subprocess.CompletedProcess([], code, json.dumps(body), "fixture error")
                   for code, body in responses]
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(snapshot.tempfile, "gettempdir", return_value=directory), \
                patch.object(snapshot.subprocess, "run", side_effect=replies) as run, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = snapshot.update_gist("new content\n")
        return result, run.call_count

    def test_wrong_owner_is_rejected_before_write(self):
        self.assertEqual(self.publish_result([(0, self.gist_document(owner="other"))]), (False, 1))

    def test_cli_failure_does_not_report_success(self):
        self.assertEqual(self.publish_result([(0, self.gist_document()), (1, {})]), (False, 2))

    def test_successful_cli_with_missing_readback_is_failure(self):
        self.assertEqual(self.publish_result([(0, self.gist_document()), (0, {}), (1, {})]), (False, 3))

    def test_successful_cli_with_wrong_content_is_failure(self):
        self.assertEqual(self.publish_result([(0, self.gist_document()), (0, {}),
                                             (0, self.gist_document(content="wrong"))]), (False, 3))

    def test_visibility_change_is_rejected(self):
        self.assertEqual(self.publish_result([(0, self.gist_document()), (0, {}),
                                             (0, self.gist_document(content="new content\n", public=False))]), (False, 3))

    def test_wrong_description_is_rejected(self):
        document = self.gist_document(content="new content\n")
        document["description"] = "previous description"
        self.assertEqual(self.publish_result([(0, self.gist_document()), (0, {}),
                                             (0, document)]), (False, 3))

    def test_success_requires_matching_public_content_and_description(self):
        self.assertEqual(self.publish_result([(0, self.gist_document()), (0, {}),
                                             (0, self.gist_document(content="new content\n"))]), (True, 3))


if __name__ == "__main__":
    unittest.main()
