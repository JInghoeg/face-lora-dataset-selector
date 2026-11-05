"""Regression checks for the single production-model DirectML target probe.

Runs without a GPU; real DirectML acceptance still requires the RTX 5080.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "benchmarks"))
import ediffiqa_candidate_probe as probe


class FinalProbeSmoke(unittest.TestCase):
    def test_only_sha_pinned_production_candidate_is_scheduled(self):
        self.assertEqual(probe.CANDIDATES, (probe.PRODUCTION_CANDIDATE,))
        self.assertEqual(probe.PRODUCTION_CANDIDATE[0], "upstream_current")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            calls = []

            def fake_run(result_dir, candidate, provider):
                calls.append((result_dir, candidate, provider))
                return {
                    "candidate": candidate,
                    "provider_requested": provider,
                    "model_sha256": probe.PRODUCTION_SHA256,
                    "status": "pass",
                    "session_providers": ["DmlExecutionProvider"],
                }

            with (
                mock.patch.object(probe, "result_root", return_value=root),
                mock.patch.object(probe, "candidate_root", return_value=root),
                mock.patch.object(probe, "run_bounded", side_effect=fake_run),
            ):
                path, report = probe.run_parent()

            self.assertEqual(calls, [(root, "upstream_current", "directml")])
            self.assertEqual(report["winner"], "upstream_current")
            self.assertEqual(len(report["probes"]), 1)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), report)

    def test_cpu_recovery_or_wrong_model_never_count_as_gpu_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for row in (
                {"candidate": "upstream_current", "status": "pass",
                 "model_sha256": probe.PRODUCTION_SHA256,
                 "session_providers": ["CPUExecutionProvider"]},
                {"candidate": "upstream_current", "status": "pass",
                 "model_sha256": "wrong",
                 "session_providers": ["DmlExecutionProvider"]},
                {"candidate": "upstream_current", "status": "timeout",
                 "model_sha256": probe.PRODUCTION_SHA256,
                 "session_providers": ["DmlExecutionProvider"]},
            ):
                with (
                    mock.patch.object(probe, "result_root", return_value=root),
                    mock.patch.object(probe, "candidate_root", return_value=root),
                    mock.patch.object(probe, "run_bounded", return_value=row),
                ):
                    _, report = probe.run_parent()
                self.assertIsNone(report["winner"])
                self.assertEqual(report["all_directml_passes"], [])

    def test_wrong_model_hash_is_rejected_before_session_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            models = root / "ediffiqa-candidates"
            models.mkdir()
            (models / probe.PRODUCTION_CANDIDATE[1]).write_bytes(b"wrong model")
            args = argparse.Namespace(
                candidate="upstream_current", provider="directml",
                output=str(root / "result.json"), progress=str(root / "progress.jsonl"),
            )
            with (
                mock.patch.object(probe, "candidate_root", return_value=models),
                mock.patch.object(probe.ort, "InferenceSession") as session,
            ):
                exit_code = probe.child(args)
            self.assertEqual(exit_code, 2)
            session.assert_not_called()
            data = json.loads((root / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "error")
            self.assertIn("SHA-256 mismatch", data["error"]["message"])


if __name__ == "__main__":
    unittest.main()
