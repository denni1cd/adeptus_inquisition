"""Acceptance checks for the optional, offline Vally bridge."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from inquisition.evaluation.atif_adapter import EvidenceError, adapt, export
from inquisition.evaluation.comparison import compare
from inquisition.evaluation.vally_backend import grade, preflight_spec


ROOT = Path(__file__).resolve().parents[1]


def trial(case_id, variant, value, holdout=False, accepted=True):
    return {
        "case_id": case_id, "holdout": holdout, "vally_grade_ref": variant + "/" + case_id,
        "checks": {
            "original_acceptance": {"passed": accepted, "evidence_ref": variant + "/ac"},
            "regressions_clear": {"passed": True, "evidence_ref": variant + "/reg"},
            "independent_review": {"passed": True, "evidence_ref": variant + "/review"},
        },
        "metrics": {"repair_cycles": {"value": value, "complete": True,
                                      "evidence_ref": variant + "/cycles"}},
    }


def plan():
    return {
        "schema_version": "INQUISITION-COMPARISON-v1",
        "branch": "necroneerium",
        "baseline_commit": "base123",
        "candidate_commit": "candidate456",
        "criteria_hash": "criteria789",
        "metric_directions": {"repair_cycles": "lower"},
        "baseline": [trial("known", "base", 3), trial("hidden", "base", 4, True)],
        "candidate": [trial("known", "new", 2), trial("hidden", "new", 2, True)],
    }


class AtifTests(unittest.TestCase):
    def setUp(self):
        self.run = json.loads((ROOT / "fixtures/adeptus_run_sample.json").read_text())

    def test_export_preserves_observed_tool_result_and_provenance(self):
        atif, provenance = adapt(self.run)
        self.assertEqual(atif["schema_version"], "ATIF-v1.6")
        self.assertEqual(atif["steps"][1]["tool_calls"][0]["tool_call_id"], "call-1")
        self.assertEqual(atif["steps"][1]["observation"]["results"][0]["source_call_id"], "call-1")
        self.assertEqual(provenance["provenance"][1]["source_ref"], "fixtures/test-input/agent-and-tool")
        self.assertEqual(provenance["completeness"], "PARTIAL")
        self.assertIn("subagent_events", provenance["missing_or_unproven"])
        self.assertIsNone(provenance["attestation"])

    def test_missing_source_ref_rejected(self):
        self.run["events"][1].pop("source_ref")
        with self.assertRaises(EvidenceError):
            adapt(self.run)

    def test_tool_result_without_matching_call_rejected(self):
        self.run["events"][1]["tool_results"][0]["source_call_id"] = "forged-id"
        with self.assertRaises(EvidenceError):
            adapt(self.run)

    def test_duplicate_tool_call_ids_rejected(self):
        self.run["events"][1]["tool_calls"].append(copy.deepcopy(
            self.run["events"][1]["tool_calls"][0]))
        with self.assertRaises(EvidenceError):
            adapt(self.run)

    def test_missing_events_cannot_be_misrepresented_as_agent_work(self):
        self.run["events"] = []
        atif, provenance = adapt(self.run)
        self.assertEqual(atif["steps"][0]["source"], "system")
        self.assertEqual(provenance["provenance"], [])
        self.assertEqual(provenance["completeness"], "PARTIAL")

    def test_export_writes_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "input.json"
            src.write_text(json.dumps(self.run))
            manifest = export(src, Path(tmp) / "output.json", Path(tmp) / "prov.json")
            self.assertEqual(manifest["run_id"], self.run["run_id"])
            self.assertEqual(json.loads((Path(tmp) / "output.json").read_text())
                             ["schema_version"], "ATIF-v1.6")

    def test_reject_same_file_for_atif_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "input.json"
            src.write_text(json.dumps(self.run))
            with self.assertRaises(EvidenceError):
                export(src, Path(tmp) / "output.json", Path(tmp) / "output.json")


class ComparisonTests(unittest.TestCase):
    def test_measured_gain_pending_independent_approval(self):
        result = compare(plan())
        self.assertEqual(result["status"], "SUPPORTED_FOR_INDEPENDENT_REVIEW")
        self.assertFalse(result["approval"])
        self.assertEqual(result["paired_cases"], 2)

    def test_candidate_regression_rejected(self):
        data = plan()
        data["candidate"][1]["checks"]["regressions_clear"]["passed"] = False
        result = compare(data)
        self.assertEqual(result["status"], "REJECT_CANDIDATE")
        self.assertFalse(result["approval"])

    def test_quality_can_improve_without_lowered_criteria(self):
        data = plan()
        data["baseline"][0]["checks"]["original_acceptance"]["passed"] = False
        self.assertIn("known", compare(data)["repaired_cases"])

    def test_no_gain_is_not_recommended(self):
        data = plan()
        for a, b in zip(data["baseline"], data["candidate"]):
            b["metrics"] = copy.deepcopy(a["metrics"])
        self.assertEqual(compare(data)["status"], "NO_IMPROVEMENT_DEMONSTRATED")

    def test_worsening_metric_requires_tradeoff_review(self):
        data = plan()
        data["candidate"][1]["metrics"]["repair_cycles"]["value"] = 12
        self.assertEqual(compare(data)["status"], "TRADEOFF_REQUIRES_REVIEW")

    def test_missing_metric_is_not_zero(self):
        data = plan()
        data["candidate"][1]["metrics"]["repair_cycles"]["complete"] = False
        with self.assertRaises(EvidenceError):
            compare(data)

    def test_unmatched_cases_block_comparison(self):
        data = plan()
        data["candidate"][0]["case_id"] = "replacement"
        with self.assertRaises(EvidenceError):
            compare(data)

    def test_holdout_is_mandatory(self):
        data = plan()
        for row in data["baseline"] + data["candidate"]:
            row["holdout"] = False
        with self.assertRaises(EvidenceError):
            compare(data)

    def test_missing_quality_evidence_blocks(self):
        data = plan()
        data["candidate"][0]["checks"]["independent_review"]["evidence_ref"] = ""
        with self.assertRaises(EvidenceError):
            compare(data)


class BackendTests(unittest.TestCase):
    def test_curated_profiles_have_only_deterministic_graders(self):
        for branch in ("necroneerium", "strategerium", "factorium"):
            self.assertTrue(preflight_spec(ROOT / "evals" / branch / "eval.yaml"))

    def test_no_llm_judges_or_paid_backend_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "eval.yaml"
            path.write_text("graders:\n  - type: prompt\n")
            with self.assertRaises(EvidenceError):
                preflight_spec(path)
            path.write_text("graders:\n  - type: exit-success\ndefaults:\n  executor: copilot-sdk\n")
            with self.assertRaises(EvidenceError):
                preflight_spec(path)

    @patch("inquisition.evaluation.vally_backend.subprocess.run")
    @patch("inquisition.evaluation.vally_backend.shutil.which", return_value="/fake/vally")
    def test_real_grade_command_is_offline_and_exit_zero_not_approval(self, which, run):
        run.return_value = Mock(returncode=0, stderr=b"",
                                stdout=b'{"type":"trial-result","passed":false}\n')
        with tempfile.TemporaryDirectory() as tmp:
            atif = Path(tmp) / "input.json"
            atif.write_text(json.dumps(adapt(json.loads(
                (ROOT / "fixtures/adeptus_run_sample.json").read_text()))[0]))
            report = grade(atif, ROOT / "evals/necroneerium/eval.yaml",
                           Path(tmp) / "grade.jsonl", "recorded-branch-run")
            self.assertEqual(report["state"], "GRADED_NOT_AUTHORIZED")
            self.assertIn("grade", run.call_args.args[0])
            self.assertNotIn("eval", run.call_args.args[0])
            self.assertNotIn("--require-pass", run.call_args.args[0])
            self.assertTrue((Path(tmp) / "grade.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
