"""Tests for optional tools, not independent agent or workflow acceptance."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from inquisition.evaluation.atif_adapter import adapt, export, EvidenceError
from inquisition.evaluation.vally_backend import grade, preflight_spec

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "fixtures/adeptus_run_sample.json"


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads(SAMPLE.read_text(encoding="utf-8"))

    def test_object_arguments_preserved(self):
        trace, provenance = adapt(self.record)
        self.assertEqual(trace["steps"][1]["tool_calls"][0]["arguments"],
                         self.record["events"][1]["tool_calls"][0]["arguments"])
        self.assertEqual(provenance["completeness"], "PARTIAL")

    def test_raw_string_preserved_as_object(self):
        raw = 'python -c "print(123)"'
        self.record["events"][1]["tool_calls"][0]["arguments"] = raw
        trace, _ = adapt(self.record)
        self.assertEqual(trace["steps"][1]["tool_calls"][0]["arguments"], {"raw_arguments": raw})

    def test_missing_or_invalid_arguments_rejected(self):
        del self.record["events"][1]["tool_calls"][0]["arguments"]
        with self.assertRaises(EvidenceError):
            adapt(self.record)
        self.record["events"][1]["tool_calls"][0]["arguments"] = 1
        with self.assertRaises(EvidenceError):
            adapt(self.record)

    def test_capture_requires_boolean(self):
        self.record["capture"]["agent_steps"] = 1
        with self.assertRaises(EvidenceError):
            adapt(self.record)

    def test_unmatched_results_rejected(self):
        self.record["events"][1]["tool_results"][0]["source_call_id"] = "unmatched"
        with self.assertRaises(EvidenceError):
            adapt(self.record)

    def test_missing_results_visible(self):
        self.record["events"][1]["tool_results"] = []
        _, p = adapt(self.record)
        self.assertIn("unmatched_tool_results", p["missing_or_unproven"])

    def test_empty_events_not_fabricated(self):
        self.record["events"] = []
        trace, p = adapt(self.record)
        self.assertEqual([s["source"] for s in trace["steps"]], ["system"])
        self.assertEqual(p["completeness"], "PARTIAL")

    def test_export_cannot_overwrite_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "source.json"
            p.write_bytes(SAMPLE.read_bytes())
            with self.assertRaises(EvidenceError):
                export(p, p, Path(d) / "manifest.json")
            self.assertEqual(p.read_bytes(), SAMPLE.read_bytes())


class BackendTests(unittest.TestCase):
    def test_curated_profile(self):
        self.assertEqual(preflight_spec(ROOT / "evals/process/eval.yaml"),
                         ["exit-success", "max-repeat"])

    def test_reject_model_judge(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "profile.yaml"
            p.write_text("graders:\n  - type: prompt\n", encoding="utf-8")
            with self.assertRaises(EvidenceError):
                preflight_spec(p)

    @patch("inquisition.evaluation.vally_backend.subprocess.run")
    @patch("inquisition.evaluation.vally_backend.shutil.which", return_value="vally")
    def test_offline_grade_not_authorization(self, which, run):
        run.return_value.returncode = 0
        run.return_value.stdout = b'{"passed":false}\n'
        with tempfile.TemporaryDirectory() as d:
            atif = Path(d) / "run.json"
            atif.write_text(json.dumps(adapt(json.loads(SAMPLE.read_text()))[0]))
            result = grade(atif, ROOT / "evals/process/eval.yaml", Path(d) / "grade.jsonl",
                           "recorded-branch-run")
            self.assertEqual(result["state"], "GRADED_NOT_AUTHORIZED")
            self.assertEqual(run.call_args.args[0][1], "grade")
            self.assertEqual(run.call_args.kwargs["env"]["VALLY_TELEMETRY_OPTOUT"], "1")

    @patch("inquisition.evaluation.vally_backend.shutil.which", return_value="vally")
    def test_grade_cannot_overwrite_input(self, which):
        with tempfile.TemporaryDirectory() as d:
            atif = Path(d) / "run.json"
            atif.write_text(json.dumps(adapt(json.loads(SAMPLE.read_text()))[0]))
            with self.assertRaises(EvidenceError):
                grade(atif, ROOT / "evals/process/eval.yaml", atif, "recorded-branch-run")


if __name__ == "__main__":
    unittest.main()
