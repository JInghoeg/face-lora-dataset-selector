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
                    "session_providers": ["DmlExecutionProvider", "CPUExecutionProvider"],
                    "gpu_compute_verified": True,
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
                 "session_providers": ["CPUExecutionProvider"], "gpu_compute_verified": True},
                {"candidate": "upstream_current", "status": "pass",
                 "model_sha256": "wrong",
                 "session_providers": ["DmlExecutionProvider"], "gpu_compute_verified": True},
                {"candidate": "upstream_current", "status": "timeout",
                 "model_sha256": probe.PRODUCTION_SHA256,
                 "session_providers": ["DmlExecutionProvider"], "gpu_compute_verified": True},
                {"candidate": "upstream_current", "status": "pass",
                 "model_sha256": probe.PRODUCTION_SHA256,
                 "session_providers": ["DmlExecutionProvider", "CPUExecutionProvider"],
                 "gpu_compute_verified": False},
                {"candidate": "upstream_current", "status": "pass",
                 "model_sha256": probe.PRODUCTION_SHA256,
                 "session_providers": ["DmlExecutionProvider", "CPUExecutionProvider"]},
            ):
                with (
                    mock.patch.object(probe, "result_root", return_value=root),
                    mock.patch.object(probe, "candidate_root", return_value=root),
                    mock.patch.object(probe, "run_bounded", return_value=row),
                ):
                    _, report = probe.run_parent()
                self.assertIsNone(report["winner"])
                self.assertEqual(report["all_directml_passes"], [])

    def test_profile_accepts_real_gpu_math_with_cpu_shape_helper(self):
        events = [
            {"cat": "Node", "name": "Expand_8_kernel_time",
             "args": {"provider": "CPUExecutionProvider", "op_name": "Expand"}},
            {"cat": "Node", "name": "Conv_9_kernel_time",
             "args": {"provider": "DmlExecutionProvider", "op_name": "Conv"}},
            {"cat": "Node", "name": "Gemm_10_kernel_time",
             "args": {"provider": "DmlExecutionProvider", "op_name": "Gemm"}},
            {"cat": "Session", "name": "session_initialization", "args": {}},
        ]
        result = probe.summarize_execution_profile(events)
        self.assertTrue(result["gpu_compute_verified"])
        self.assertEqual(result["dml_compute_kernel_events"], 2)
        self.assertEqual(result["operators_by_provider"]["CPUExecutionProvider"]["Expand"], 1)
        self.assertEqual(result["cpu_non_helper_ops"], [])

    def test_cpu_math_or_provider_only_never_proves_gpu(self):
        cases = (
            [{"cat": "Node", "name": "Conv_kernel_time",
              "args": {"provider": "CPUExecutionProvider", "op_name": "Conv"}}],
            [{"cat": "Node", "name": "Expand_kernel_time",
              "args": {"provider": "CPUExecutionProvider", "op_name": "Expand"}}],
            [{"cat": "Session", "name": "model_run",
              "args": {"provider": "DmlExecutionProvider"}}],
            [{"cat": "Node", "name": "Conv_kernel_time",
              "args": {"provider": "DmlExecutionProvider", "op_name": "Conv"}},
             {"cat": "Node", "name": "Gemm_kernel_time",
              "args": {"provider": "CPUExecutionProvider", "op_name": "Gemm"}}],
        )
        for events in cases:
            self.assertFalse(probe.summarize_execution_profile(events)["gpu_compute_verified"])

    def test_profile_enabled_for_real_dml_proof(self):
        options = probe.session_options(strict_dml=True, profile_prefix="G:/qa/ort")
        self.assertTrue(options.enable_profiling)
        self.assertEqual(options.profile_file_prefix, "G:/qa/ort")

    def test_child_finishes_real_profile_path_without_duplicate_keyword(self):
        """Run the real child pipeline with mocked ORT; cover the exact RTX failure."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            model = root / probe.PRODUCTION_CANDIDATE[1]
            model.write_bytes(b"fixture-official-model")
            expected_sha = probe.hashlib.sha256(model.read_bytes()).hexdigest()
            trace = root / "profile.json"
            trace.write_text(json.dumps([
                {"cat": "Node", "name": "Expand_kernel_time",
                 "args": {"provider": "CPUExecutionProvider", "op_name": "Expand"}},
                {"cat": "Node", "name": "Conv_kernel_time",
                 "args": {"provider": "DmlExecutionProvider", "op_name": "Conv"}},
            ]), encoding="utf-8")
            args = argparse.Namespace(
                candidate="upstream_current", provider="directml",
                output=str(root / "result.json"), progress=str(root / "events.jsonl"),
            )
            class Input:
                name = "input"
                shape = [1, 3, 112, 112]

            class FakeSession:
                def __init__(self):
                    self.calls = 0
                def get_inputs(self):
                    return [Input()]
                def get_providers(self):
                    return ["DmlExecutionProvider", "CPUExecutionProvider"]
                def run(self, _outputs, _feed):
                    self.calls += 1
                    return [probe.np.array([[0.45]], dtype=probe.np.float32)]
                def end_profiling(self):
                    return str(trace)

            session = FakeSession()
            with (
                mock.patch.object(probe, "candidate_root", return_value=root),
                mock.patch.object(probe, "PRODUCTION_SHA256", expected_sha),
                mock.patch.object(probe.ort, "InferenceSession", return_value=session) as ctor,
            ):
                code = probe.child(args)
            self.assertEqual(code, 0)
            self.assertEqual(session.calls, 3)
            self.assertFalse(ctor.call_args.kwargs["enable_fallback"])
            data = json.loads(Path(args.output).read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "pass")
            self.assertTrue(data["gpu_compute_verified"])
            self.assertEqual(data["profile_summary"]["dml_compute_kernel_events"], 1)
            progress = [json.loads(s) for s in Path(args.progress).read_text(encoding="utf-8").splitlines()]
            saved = [e for e in progress if e["event"] == "profile_saved"]
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0]["profile_path"], str(trace))

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
