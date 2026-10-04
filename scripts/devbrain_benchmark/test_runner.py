from __future__ import annotations

import json
import os
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner


class BenchmarkRunnerTests(unittest.TestCase):
    def test_catalog_is_fixed_and_bounded(self) -> None:
        scenarios = runner.load_scenarios()
        self.assertEqual(tuple(scenarios), runner.SCENARIO_ORDER)
        self.assertEqual(len(scenarios), 3)
        self.assertEqual(runner.MAX_PILOT_RUNS, 4)
        self.assertEqual(runner.MAX_TOTAL_RUNS, 12)

    def test_validate_is_offline_and_requires_exact_model(self) -> None:
        result = runner.validate_catalog(runner.verify_repo_root())
        self.assertEqual(result["model_runs_started"], 0)
        self.assertEqual(result["model_required"], "gpt-6-luna")
        with self.assertRaises(runner.BenchmarkError):
            runner.require_exact_model("another-model")

    def test_output_path_must_stay_under_scratch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".scratch" / "devbrain_benchmark").mkdir(parents=True)
            path = runner.require_safe_output(root, ".scratch/devbrain_benchmark/run.json")
            self.assertTrue(path.is_relative_to(root.resolve()))
            with self.assertRaises(runner.BenchmarkError):
                runner.require_safe_output(root, ".scratch/devbrain_benchmark/../../outside.json")
            with self.assertRaises(runner.BenchmarkError):
                runner.require_safe_output(root, "scripts/devbrain_benchmark/run.json")

    def test_anchor_path_rejects_traversal_and_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            outside_file = Path(outside) / "outside.py"
            outside_file.write_text("secret = True\n", encoding="utf-8")
            (root / "backend").mkdir()
            (root / "backend" / "safe.py").write_text("value = 1\n", encoding="utf-8")
            self.assertEqual(runner.safe_repo_path(root, "backend/safe.py"), (root / "backend" / "safe.py").resolve())
            with self.assertRaises(runner.BenchmarkError):
                runner.safe_repo_path(root, "backend/../secret.py")
            link = root / "backend" / "escape.py"
            try:
                link.symlink_to(Path(outside) / "outside.py")
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")
            with self.assertRaises(runner.BenchmarkError):
                runner.safe_repo_path(root, "backend/escape.py")

    def test_jsonl_counters_are_taken_only_from_completed_usage(self) -> None:
        payload = [
            {"type": "thread.started", "thread_id": "session-a"},
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "{\"phase\":\"capture\"}"},
            },
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 20},
            },
        ]
        output = "\n".join(json.dumps(item) for item in payload)
        session_id, usage, response, calls = runner.parse_jsonl_events(output)
        self.assertEqual(session_id, "session-a")
        self.assertEqual(usage, {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 20})
        self.assertEqual(response, {"phase": "capture"})
        self.assertEqual(calls, 0)

    def test_missing_counter_is_unavailable_not_zero(self) -> None:
        output = json.dumps({"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 20}})
        _, usage, _, _ = runner.parse_jsonl_events(output)
        self.assertIsNone(usage)
        record = runner.run_record("api_ws_origin", "legacy_manual", "capture", None, {"usage": None}, source_fingerprint="a" * 64)
        self.assertIsNone(record["input_tokens"])
        self.assertEqual(record["usage_status"], "USAGE_UNAVAILABLE")

    def test_helper_calls_count_completed_events_once(self) -> None:
        command_item = {"type": "command_execution", "command": ".\\scripts\\run_devbrain_memory.ps1 -Action Capture"}
        events = [
            {"type": "item.started", "item": command_item},
            {"type": "item.completed", "item": command_item},
        ]
        _, _, _, helper_calls = runner.parse_jsonl_events("\n".join(json.dumps(item) for item in events))
        self.assertEqual(helper_calls, 1)

    def test_response_scoring_checks_owner_fact_next_step_and_validation(self) -> None:
        scenario = runner.load_scenarios()["api_ws_origin"]
        response = {
            "phase": "recall",
            "task_id": "task-1",
            "goal": scenario["goal"],
            "owner": "frontend/src/api/runtime.ts and frontend/src/api/ws.ts",
            "next_step": runner.NEXT_STEP,
            "checks_run": runner.CHECKS_RUN,
            "checks_not_run": runner.CHECKS_NOT_RUN,
            "answer": "VITE_API_BASE_URL selects API base, /api/v1 is used, buildWsUrl derives WebSocket path.",
            "evidence_paths": scenario["source_paths"],
            "safety_failures": [],
        }
        validated = runner.validate_response(response, phase="recall", task_id="task-1")
        assertions = runner.score_response(validated, scenario, scenario["source_paths"])
        self.assertTrue(all(assertions.values()))
        response["evidence_paths"] = ["C:/Users/other/secret.py", *scenario["source_paths"]]
        assertions = runner.score_response(response, scenario, scenario["source_paths"])
        self.assertFalse(assertions["evidence_paths_valid"])

    def test_fresh_recall_prompts_have_only_task_id_and_retrieval_action(self) -> None:
        for scenario in runner.load_scenarios().values():
            for variant in ("legacy_manual", "automatic_helper"):
                prompt = runner.recall_prompt(scenario, variant, "00000000-0000-4000-8000-000000000001")
                self.assertIn("00000000-0000-4000-8000-000000000001", prompt)
                self.assertNotIn(scenario["goal"], prompt)
                self.assertNotIn(scenario["query"], prompt)

    def test_capture_prompt_passes_safe_query_topics_and_summary_limit(self) -> None:
        scenario = runner.load_scenarios()["api_ws_origin"]
        prompt = runner.capture_prompt(scenario, "automatic_helper", "task-id")
        self.assertIn(scenario["query"], prompt)
        self.assertIn(", ".join(scenario["topics"]), prompt)
        self.assertIn("under 1,200 characters", prompt)

    def test_model_run_actions_are_native_windows_only(self) -> None:
        with patch.object(runner.os, "name", "posix"):
            with self.assertRaisesRegex(runner.BenchmarkError, "native Windows"):
                runner.run_pilot(None, runner.EXPECTED_MODEL, None)
            with self.assertRaisesRegex(runner.BenchmarkError, "native Windows"):
                runner.expand_pilot(None, runner.EXPECTED_MODEL, "unused")
                for term in scenario["expected_answer_terms"]:
                    self.assertNotIn(term.casefold(), prompt.casefold())

    def test_prompt_source_preflight_rejects_obvious_sensitive_values_without_echoing_them(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.ts"
            path.write_text('const contact = "person@example.org";\n', encoding="utf-8")
            with self.assertRaisesRegex(runner.BenchmarkError, "preflight"):
                runner.verify_source_is_safe_for_prompt(path)

    def test_cli_failure_classification_is_bounded_and_safe(self) -> None:
        self.assertEqual(runner.classify_failure("Model not available for this account"), "model_unavailable")
        self.assertEqual(runner.classify_failure("sandbox permission denied"), "sandbox_blocked")
        self.assertEqual(runner.classify_failure(""), "cli_failed")

    def test_cycle_totals_include_capture_and_recall(self) -> None:
        runs = []
        for variant, input_tokens in (("legacy_manual", 100), ("automatic_helper", 70)):
            for phase in ("capture", "recall"):
                runs.append({
                    "scenario_id": "api_ws_origin",
                    "variant": variant,
                    "phase": phase,
                    "status": "completed",
                    "usage_status": "AVAILABLE",
                    "input_tokens": input_tokens,
                    "cached_input_tokens": 10,
                    "output_tokens": 8,
                    "elapsed_ms": 200,
                })
        total = runner.scenario_totals(runs, "api_ws_origin", "automatic_helper")
        self.assertEqual(total, {"input_tokens": 140, "cached_input_tokens": 20, "output_tokens": 16, "elapsed_ms": 400})

    @unittest.skipUnless(os.name == "nt", "PowerShell memory-helper integration is Windows-only")
    def test_scratch_variants_are_isolated_and_helper_recalls_a_fresh_capture(self) -> None:
        root = runner.verify_repo_root()
        scenario = runner.load_scenarios()["api_ws_origin"]
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            legacy, _ = runner.create_scratch_repo(root, base / "legacy", scenario, "legacy_manual")
            automatic, _ = runner.create_scratch_repo(root, base / "automatic", scenario, "automatic_helper")
            legacy_common = runner.git(legacy, "rev-parse", "--path-format=absolute", "--git-common-dir")
            automatic_common = runner.git(automatic, "rev-parse", "--path-format=absolute", "--git-common-dir")
            self.assertNotEqual(legacy_common, automatic_common)
            self.assertEqual(
                runner.source_snapshot_fingerprint(legacy, scenario["source_paths"]),
                runner.source_snapshot_fingerprint(automatic, scenario["source_paths"]),
            )

            ps = runner.powershell_executable()
            begin = subprocess.run(
                [ps, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(automatic / "scripts/run_devbrain_memory.ps1"),
                 "-Action", "Begin", "-Query", "synthetic benchmark memory-store integration", "-Topics", "benchmark"],
                cwd=automatic, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, check=False,
            )
            self.assertEqual(begin.returncode, 0, begin.stderr)
            begun = json.loads(begin.stdout)
            task_id = begun["task_id"]
            payload = {
                "task_id": task_id,
                "expected_revision": 1,
                "checkpoint": {
                    "goal": "synthetic benchmark memory-store integration",
                    "status": "in_progress",
                    "completed": ["read source anchor"],
                    "next_step": "continue after fresh recall",
                    "validation_reported": ["helper integration test only"],
                },
                "knowledge": [{
                    "schema_version": 1,
                    "id": "benchmark-integration-fact",
                    "key": "benchmark-isolated-local-fact",
                    "kind": "fact",
                    "topic": "benchmark memory store",
                    "summary": "The synthetic integration test can capture and recall one source-backed fact.",
                    "tags": ["benchmark", "memory"],
                    "scope": "repo",
                    "source_type": "source",
                    "evidence_summary": "Synthetic isolated test repository and anchor.",
                    "anchors": [{"path": scenario["source_paths"][0]}],
                    "supersedes": [],
                }],
            }
            scratch = automatic / ".scratch"
            scratch.mkdir()
            payload_path = scratch / "capture.json"
            payload_path.write_text(json.dumps(payload), encoding="utf-8")
            captured = subprocess.run(
                [ps, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(automatic / "scripts/run_devbrain_memory.ps1"),
                 "-Action", "Capture", "-InputFile", str(payload_path)],
                cwd=automatic, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, check=False,
            )
            payload_path.unlink()
            self.assertEqual(captured.returncode, 0, captured.stderr)
            recalled = subprocess.run(
                [ps, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(automatic / "scripts/run_devbrain_memory.ps1"),
                 "-Action", "Recall", "-TaskId", task_id],
                cwd=automatic, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, check=False,
            )
            self.assertEqual(recalled.returncode, 0, recalled.stderr)
            packet = json.loads(recalled.stdout)
            self.assertEqual(packet["status"], "OK")
            self.assertEqual(packet["revision"], 2)
            self.assertEqual(packet["knowledge"][0]["provenance_state"], "sources_match")
            self.assertFalse((Path(legacy_common) / "devbrain-memory").exists())
            self.assertTrue((Path(automatic_common) / "devbrain-memory/v1/records").is_dir())


if __name__ == "__main__":
    unittest.main()
