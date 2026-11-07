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
                    "production_mixed_execution_accepted": True,
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
                 "session_providers": ["CPUExecutionProvider"], "gpu_compute_verified": True, "production_mixed_execution_accepted": True},
                {"candidate": "upstream_current", "status": "pass",
                 "model_sha256": "wrong",
                 "session_providers": ["DmlExecutionProvider"], "gpu_compute_verified": True, "production_mixed_execution_accepted": True},
                {"candidate": "upstream_current", "status": "timeout",
                 "model_sha256": probe.PRODUCTION_SHA256,
                 "session_providers": ["DmlExecutionProvider"], "gpu_compute_verified": True, "production_mixed_execution_accepted": True},
                {"candidate": "upstream_current", "status": "pass",
                 "model_sha256": probe.PRODUCTION_SHA256,
                 "session_providers": ["DmlExecutionProvider", "CPUExecutionProvider"],
                 "gpu_compute_verified": False, "production_mixed_execution_accepted": False},
                {"candidate": "upstream_current", "status": "pass",
                 "model_sha256": probe.PRODUCTION_SHA256,
                 "session_providers": ["DmlExecutionProvider", "CPUExecutionProvider"]},
                {"candidate": "upstream_current", "status": "pass",
                 "model_sha256": probe.PRODUCTION_SHA256,
                 "session_providers": ["DmlExecutionProvider", "CPUExecutionProvider"],
                 "gpu_compute_verified": True,
                 "production_mixed_execution_accepted": False},
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
        self.assertTrue(result["production_mixed_execution_accepted"])
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
            report = probe.summarize_execution_profile(events)
            self.assertFalse(report["production_mixed_execution_accepted"])
        for only_cpu in cases[:3]:
            self.assertFalse(probe.summarize_execution_profile(only_cpu)["gpu_compute_verified"])
        self.assertTrue(probe.summarize_execution_profile(cases[3])["gpu_compute_verified"])

    def test_real_rtx_profile_aggregate_mixed_dml_compute_is_accepted(self):
        # Reproduces counts in the uploaded 2026-11-06 recovered profile.
        # This is a regression fixture, not a measured performance benchmark.
        specs = [
            ("DmlExecutionProvider", "Conv", 147),
            ("DmlExecutionProvider", "Gemm", 9),
            ("DmlExecutionProvider", "Add", 36),
            ("DmlExecutionProvider", "Clip", 3),
            ("DmlExecutionProvider", "Div", 3),
            ("DmlExecutionProvider", "Expand", 3),
            ("DmlExecutionProvider", "Flatten", 3),
            ("DmlExecutionProvider", "MemcpyFromHost", 3),
            ("DmlExecutionProvider", "MemcpyToHost", 3),
            ("DmlExecutionProvider", "PRelu", 99),
            ("DmlExecutionProvider", "ReduceL2", 3),
            ("DmlExecutionProvider", "Shape", 3),
            ("CPUExecutionProvider", "Gelu", 3),
        ]
        events = [
            {"cat": "Node", "name": f"{op}_{i}_kernel_time",
             "args": {"provider": provider, "op_name": op}}
            for provider, op, count in specs for i in range(count)
        ]
        row = probe.summarize_execution_profile(events, expected_runs=3)
        self.assertEqual(row["provider_kernel_events"],
                         {"CPUExecutionProvider": 3, "DmlExecutionProvider": 315})
        self.assertEqual(row["dml_compute_kernel_events"], 156)
        self.assertEqual(row["cpu_non_helper_ops"], ["Gelu"])
        self.assertEqual(row["unexpected_cpu_compute_ops"], [])
        self.assertEqual(row["cpu_gelu_kernel_events"], 3)
        self.assertTrue(row["gpu_compute_verified"])
        self.assertTrue(row["production_mixed_execution_accepted"])
        self.assertTrue(row["cpu_nodes_executed"])
        self.assertFalse(row["performance_verified"])

        extra_cpu = {"cat": "Node", "name": "Gemm_cpu_kernel_time",
                     "args": {"provider": "CPUExecutionProvider", "op_name": "Gemm"}}
        self.assertTrue(probe.summarize_execution_profile(events + [extra_cpu])["gpu_compute_verified"])
        self.assertFalse(probe.summarize_execution_profile(events + [extra_cpu])["production_mixed_execution_accepted"])
        extra_gelu = {"cat": "Node", "name": "Gelu_extra_kernel_time",
                      "args": {"provider": "CPUExecutionProvider", "op_name": "Gelu"}}
        self.assertFalse(probe.summarize_execution_profile(events + [extra_gelu])["production_mixed_execution_accepted"])

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
                {"cat": "Node", "name": "Gemm_kernel_time",
                 "args": {"provider": "DmlExecutionProvider", "op_name": "Gemm"}},
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
            self.assertEqual(data["profile_summary"]["dml_compute_kernel_events"], 2)
            self.assertTrue(data["production_mixed_execution_accepted"])
            progress = [json.loads(s) for s in Path(args.progress).read_text(encoding="utf-8").splitlines()]
            saved = [e for e in progress if e["event"] == "profile_saved"]
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0]["profile_path"], str(trace))

    def test_benchmark_measures_same_model_cpu_and_dml_without_claiming_ci_gpu_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            model = root / probe.PRODUCTION_CANDIDATE[1]
            model.write_bytes(b"official-model-fixture")
            digest = probe.hashlib.sha256(model.read_bytes()).hexdigest()
            trace = root / "benchmark-profile.json"
            trace.write_text(json.dumps([
                {"cat": "Node", "name": "Conv_kernel_time",
                 "args": {"provider": "DmlExecutionProvider", "op_name": "Conv"}},
                {"cat": "Node", "name": "Gemm_kernel_time",
                 "args": {"provider": "DmlExecutionProvider", "op_name": "Gemm"}},
                {"cat": "Node", "name": "Gelu_kernel_time",
                 "args": {"provider": "CPUExecutionProvider", "op_name": "Gelu"}},
            ]), encoding="utf-8")
            calls = []

            class Input:
                name = "input"
                shape = [1, 3, 112, 112]

            class FakeSession:
                def __init__(self, provider, profiled):
                    self.provider = provider
                    self.profiled = profiled
                    self.run_count = 0

                def get_inputs(self):
                    return [Input()]

                def get_providers(self):
                    return (["DmlExecutionProvider", "CPUExecutionProvider"]
                            if self.provider == "directml" else ["CPUExecutionProvider"])

                def run(self, _outputs, feed):
                    self.run_count += 1
                    self.input_signature = float(probe.np.sum(feed["input"]))
                    return [probe.np.array([[0.45]], dtype=probe.np.float32)]

                def end_profiling(self):
                    return str(trace)

            def session_factory(_model, sess_options, providers, enable_fallback):
                self.assertFalse(enable_fallback)
                name = "directml" if "DmlExecutionProvider" in providers else "cpu"
                inst = FakeSession(name, sess_options.enable_profiling)
                calls.append(inst)
                return inst

            with (
                mock.patch.object(probe, "candidate_root", return_value=root),
                mock.patch.object(probe, "app_dir", return_value=root),
                mock.patch.object(probe, "PRODUCTION_SHA256", digest),
                mock.patch.object(probe.ort, "InferenceSession", side_effect=session_factory),
            ):
                code = probe.run_performance_benchmark()

            self.assertEqual(code, 0)
            report = json.loads((root / "qa-ediffiqa-performance.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "benchmarked_mixed_directml")
            self.assertTrue(report["target_gpu_verified"])  # mock evidence only, not physical proof
            self.assertTrue(report["performance_verified"])  # mock wall-time computation only
            self.assertEqual(report["model_sha256"], digest)
            self.assertEqual(report["timed_samples_per_provider"], 30)
            self.assertEqual(len(report["cpu"]["samples_ms"]), 30)
            self.assertEqual(len(report["directml"]["samples_ms"]), 30)
            self.assertEqual(report["max_abs_output_difference"], 0.0)
            self.assertGreater(report["cpu_to_directml_median_speedup"], 0)
            self.assertEqual(len(calls), 3)
            self.assertTrue(calls[0].profiled)
            self.assertFalse(calls[1].profiled)
            self.assertFalse(calls[2].profiled)
            self.assertEqual(calls[0].run_count, 1)
            self.assertEqual(calls[1].run_count, 35)
            self.assertEqual(calls[2].run_count, 35)

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
