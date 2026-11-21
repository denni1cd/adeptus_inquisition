"""Deterministic tests for V1.2. No fixture constitutes real agent evidence."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from inquisition.engine import Ledger, GateError, digest, verify_receipt, read_json
from inquisition.evaluation import audits
from inquisition.evaluation.scoped import scope, validate_proposal, validate_plan, compare_scoped
from inquisition.evaluation.atif_adapter import EvidenceError
from scope_fixture import plan, trials, packet, proposal, first_stages, complete

ROOT = Path(__file__).resolve().parents[1]


class GeneralizationTests(unittest.TestCase):
    def compare(self, p, rows, directive=None):
        return compare_scoped(p, directive, "b"*40, "c"*40, rows)

    def test_default_general_and_explicit_scope(self):
        self.assertEqual(scope(), {"kind": "GENERAL"})
        with self.assertRaises(EvidenceError):
            scope({"kind": "TASK"})
        p = proposal()
        p.update(scope={"kind": "DOMAIN", "target": "concurrency"}, placement="conditional",
                 scope_rationale="only this domain has evidence")
        self.assertEqual(validate_proposal(None, p)["kind"], "DOMAIN")
        with self.assertRaises(EvidenceError):
            validate_proposal({"kind": "TASK", "target": "stockroom"}, p)
        p["placement"] = "core"
        with self.assertRaises(EvidenceError):
            validate_proposal(None, p)

    def test_repeated_single_task_is_not_generalization(self):
        p = plan()
        p["cases"][1]["task_sha256"] = p["cases"][0]["task_sha256"]
        with self.assertRaises(EvidenceError):
            validate_plan(p, scope())

    def test_missing_holdout_and_homogeneous_families_are_blocked(self):
        p = plan()
        p["cases"] = p["cases"][:-1]
        with self.assertRaises(EvidenceError):
            validate_plan(p, scope())
        p = plan()
        for c in p["cases"]:
            c["family"] = "database"
        with self.assertRaises(EvidenceError):
            validate_plan(p, scope())

    def test_individual_unrelated_regression_cannot_be_averaged_away(self):
        p = plan()
        rows = trials(p)
        target = next(x for x in rows if x["case_id"] == "game" and x["arm"] == "candidate")
        target["metrics"]["quality"]["value"] = 99
        r = self.compare(p, rows)
        self.assertEqual(r["status"], "REJECT_CANDIDATE")
        self.assertFalse(r["approval"])

    def test_efficiency_does_not_excuse_false_pass(self):
        p = plan()
        rows = trials(p)
        rows[-1]["checks"]["no_false_pass"]["passed"] = False
        self.assertEqual(self.compare(p, rows)["status"], "REJECT_CANDIDATE")

    def test_test_contract_discrepancy_blocks_both_arms(self):
        p = plan()
        rows = trials(p)
        rows[0]["contract_alignment_verified"] = False
        with self.assertRaises(EvidenceError):
            self.compare(p, rows)

    def test_frozen_requirements_and_environment(self):
        p = plan()
        rows = trials(p)
        rows[0]["criteria_sha256"] = "a"*64
        with self.assertRaises(EvidenceError):
            self.compare(p, rows)
        rows = trials(p)
        rows[0]["environment_sha256"] = "a"*64
        with self.assertRaises(EvidenceError):
            self.compare(p, rows)

    def test_missing_trials_or_duplicate_runs(self):
        p = plan()
        rows = trials(p)
        with self.assertRaises(EvidenceError):
            self.compare(p, rows[:-1])
        rows[0]["run_sha256"] = rows[1]["run_sha256"]
        with self.assertRaises(EvidenceError):
            self.compare(p, rows)

    def test_local_signal_only_is_not_reusable(self):
        p = plan()
        rows = trials(p)
        for row in rows:
            if row["case_id"] != "original" or row["repetition"] == 2:
                row["metrics"]["repair_cycles"]["value"] = 3
        self.assertEqual(self.compare(p, rows)["status"], "NO_IMPROVEMENT_DEMONSTRATED")

    def test_general_requires_predeclared_benefit_across_task_families(self):
        p = plan()
        rows = trials(p)
        for row in rows:
            if row["case_id"] not in ("original", "transfer"):
                row["metrics"]["repair_cycles"]["value"] = 3
        self.assertEqual(self.compare(p, rows)["status"], "NO_IMPROVEMENT_DEMONSTRATED")
        p["primary_outcome"] = "quality"
        self.assertEqual(self.compare(p, trials(p))["status"], "NO_IMPROVEMENT_DEMONSTRATED")

    def test_reproduced_signal_and_efficiency_tradeoff(self):
        p = plan()
        rows = trials(p)
        r = self.compare(p, rows)
        self.assertEqual(r["status"], "SUPPORTED_FOR_INDEPENDENT_REVIEW")
        self.assertEqual(r["distinct_tasks"], 5)
        self.assertEqual(r["paired_trials"], 10)
        next(x for x in rows if x["case_id"] == "game" and x["arm"] == "candidate")["metrics"]["repair_cycles"]["value"] = 4
        self.assertEqual(self.compare(p, rows)["status"], "TRADEOFF_REQUIRES_REVIEW")

    def test_conditional_guidance_must_not_leak_outside_scope(self):
        p = plan()
        d = {"kind": "DOMAIN", "target": "concurrency"}
        for c in p["cases"]:
            c["in_scope"] = c["category"] in {"origin", "transfer", "holdout"}
        rows = trials(p)
        for row in rows:
            c = next(c for c in p["cases"] if c["case_id"] == row["case_id"])
            row["conditional_guidance_applied"] = row["arm"] == "candidate" and c["in_scope"]
            row["conditional_evidence_ref"] = "synthetic loading proof"
        self.assertEqual(self.compare(p, rows, d)["status"], "SUPPORTED_FOR_INDEPENDENT_REVIEW")
        next(x for x in rows if x["case_id"] == "game" and x["arm"] == "candidate")["conditional_guidance_applied"] = True
        with self.assertRaises(EvidenceError):
            self.compare(p, rows, d)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.ledger = Ledger(self.folder.name)
        self.ledger.ingest(read_json(ROOT / "fixtures/failure.json"))

    def begin(self):
        audits.start(self.ledger, "evt-failure", "campaign",
                     [{"invocation_id": "writer", "context_id": "writer-context"}])

    def test_audit_cannot_reuse_context_or_skip_checkpoint(self):
        self.begin()
        p = packet(self.ledger, "diagnosis", {"finding_ref": "f", "finding_sha256": digest("f")})
        p["context_id"] = "writer-context"
        with self.assertRaises(GateError):
            audits.record(self.ledger, "campaign", p)
        p["context_id"] = "fresh"
        audits.record(self.ledger, "campaign", p)
        q = packet(self.ledger, "generalization", {"proposal": proposal(), "proposal_sha256": digest(proposal())})
        q["context_id"] = "fresh"
        with self.assertRaises(GateError):
            audits.record(self.ledger, "campaign", q)
        self.assertFalse(audits.get(self.ledger, "campaign")["authorization"])

    def test_late_material_author_cannot_self_audit(self):
        self.begin()
        p = packet(self.ledger, "diagnosis", {"finding_ref": "f", "finding_sha256": digest("f")})
        p["basis"]["authors"] = [{"invocation_id": p["invocation_id"], "context_id": "new-context"}]
        with self.assertRaises(GateError):
            audits.record(self.ledger, "campaign", p)

    def test_open_objection_no_pass_revise_then_invalidate(self):
        first_stages(self.ledger)
        p = packet(self.ledger, "diagnosis", {"finding_ref": "f2", "finding_sha256": digest("f2")}, 1)
        p["objections"] = ["unsupported"]
        with self.assertRaises(GateError):
            audits.record(self.ledger, "campaign", p)
        p["verdict"] = "REVISE"
        c = audits.record(self.ledger, "campaign", p)
        self.assertEqual(set(c["current"]), {"diagnosis"})
        self.assertEqual(c["revisions"]["diagnosis"], 1)
        self.assertEqual(audits.get(Ledger(self.folder.name), "campaign")["history"][-1]["verdict"], "REVISE")

    def test_revision_budget_and_no_vote_shopping(self):
        self.begin()
        for i in range(4):
            p = packet(self.ledger, "diagnosis",
                       {"finding_ref": f"f{i}", "finding_sha256": digest(f"f{i}")}, i,
                       "REVISE", ["unsupported hypothesis"])
            audits.record(self.ledger, "campaign", p)
        self.assertEqual(audits.get(self.ledger, "campaign")["status"], "ESCALATED")
        with self.assertRaises(GateError):
            audits.record(self.ledger, "campaign", p)
        with self.assertRaises(GateError):
            audits.start(self.ledger, "evt-failure", "new", [{"invocation_id": "i", "context_id": "j"}])

    def test_exact_repeat_is_refused(self):
        self.begin()
        p = packet(self.ledger, "diagnosis", {"finding_ref": "f", "finding_sha256": digest("f")})
        audits.record(self.ledger, "campaign", p)
        q = packet(self.ledger, "diagnosis", {"finding_ref": "f", "finding_sha256": digest("f")}, 1)
        with self.assertRaises(GateError):
            audits.record(self.ledger, "campaign", q)

    def test_operator_pins_exact_payload_without_hmac(self):
        p = {"role": "adversary", "subject": "synthetic", "invocation_id": "independent",
             "context_id": "ctx", "tool_trace": "trace", "verdict": "PASS", "evidence": "report"}
        path = Path(self.folder.name) / "synthetic-operator-pins.json"
        path.write_text(json.dumps({"schema": "INQUISITION-OPERATOR-PINS-v1",
                                    "approved_payload_sha256": [digest(p)]}))
        with patch.dict(os.environ, {"INQUISITION_OPERATOR_TRUST_STORE": str(path)}):
            self.assertEqual(verify_receipt({"payload": p}, None), p)
            bad = dict(p, verdict="FAIL")
            with self.assertRaises(GateError):
                verify_receipt({"payload": bad}, None)
        with patch.dict(os.environ, {"INQUISITION_OPERATOR_TRUST_STORE": ""}):
            with self.assertRaises(GateError):
                verify_receipt({"payload": p}, None)
