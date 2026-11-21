"""Executed, deterministic acceptance-gate tests. Receipts here are synthetic, NOT real Work agents."""
import copy
import hashlib
import hmac
import importlib.util
import json
import tempfile
import os
from unittest.mock import patch
import unittest
from pathlib import Path

from inquisition.engine import GateError, Ledger, canonical, digest, read_json, normalize
from scope_fixture import complete as complete_scope

ROOT = Path(__file__).resolve().parents[1]
TEST_KEY = "fixture-only-never-a-production-trust-key"


def sign(payload):
    return {"payload": payload, "signature": hmac.new(
        TEST_KEY.encode(), canonical(payload).encode(), hashlib.sha256
    ).hexdigest()}


def receipt(role, subject, identity, verdict="PASS", checks=None, audit_digest=None):
    payload = {"role": role, "subject": subject, "invocation_id": "synthetic-" + identity,
               "context_id": "synthetic-context-" + identity,
               "tool_trace": "synthetic-tool-events/" + identity + ".json",
               "verdict": verdict, "evidence": "test-reports/" + identity + ".json"}
    if checks is not None:
        payload["checks"] = checks
    if audit_digest is not None:
        payload["audit_digest"] = audit_digest
    return sign(payload)


def checks():
    return {k: {"executed": True, "artifact": "test-reports/" + k + ".log"}
            for k in ("baseline", "candidate", "regression", "holdout")}


def manifest(event, candidate_id="candidate-1", tags=None, paths=None):
    return {"candidate_id": candidate_id, "repository": "denni1cd/adeptus_inquisition",
            "baseline_commit": event["packet"]["baseline"]["commit"],
            "candidate_commit": "c" * 40, "content_sha256": "d" * 64,
            "changed_paths": paths or ["fixtures/reusable_v1.py"],
            "impact_tags": tags or [], "hypothesis": "Normalize repeated whitespace",
            "baseline_checks": [{"case": "double-space", "passed": False}],
            "candidate_checks": [{"case": "double-space", "passed": True}],
            "regression_checks": ["previous successful one-space case"],
            "holdout_checks": ["previously unseen tab and newline case"],
            "proposer_invocation_id": "synthetic-proposer",
            "proposer_context_id": "synthetic-context-proposer",
            "criteria_hash": event["criteria_hash"]}


def module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


class ActualFixtureTests(unittest.TestCase):
    """Execute real reference code. Not evidence of independent AI delegation."""

    def test_baseline_candidate_and_unseen_holdout(self):
        base = module(ROOT / "fixtures/reusable_v0.py")
        candidate = module(ROOT / "fixtures/reusable_v1.py")
        # Observable baseline weakness: canonical equivalents remain different.
        self.assertNotEqual(base.normalize_issue(" Connection  timeout "),
                            base.normalize_issue("connection timeout"))
        for text in (" Connection  timeout ", "CONNECTION\tTIMEOUT",
                     "connection\n timeout"):
            self.assertEqual(candidate.normalize_issue(text), "connection timeout")
            self.assertEqual(normalize(text), "connection timeout")
        # Formerly successful behavior retained.
        self.assertEqual(candidate.normalize_issue("other issue"), "other issue")
        self.assertNotEqual(candidate.normalize_issue("other issue"),
                            candidate.normalize_issue("connection timeout"))

    def test_bad_candidate_regresses_other_issue(self):
        bad = module(ROOT / "fixtures/reusable_bad.py")
        self.assertEqual(bad.normalize_issue("connection timeout"), "connection timeout")
        # The superficially passing fix collapses distinct issue identities.
        self.assertEqual(bad.normalize_issue("another root"), "connection timeout")
        self.assertNotEqual(module(ROOT / "fixtures/reusable_v1.py").normalize_issue(
            "another root"), "connection timeout")


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.home = self.folder.name
        self.ledger = Ledger(self.home)
        self.failure = read_json(ROOT / "fixtures/failure.json")
        self.clean = read_json(ROOT / "fixtures/milestone.json")

    def test_1_clean_milestone_released_without_change(self):
        self.ledger.ingest(self.clean)
        state = self.ledger.close_milestone("evt-clean", read_json(
            ROOT / "fixtures/clean_inspection.json"))
        self.assertEqual(state, "NO_CHANGE_JUSTIFIED")
        self.assertEqual(self.ledger.data["candidates"], {})
        self.assertEqual(Ledger(self.home).event("evt-clean")["disposition"],
                         "NO_CHANGE_JUSTIFIED")

    def test_2_recoverable_attempt_requires_independent_receipt(self):
        self.ledger.ingest(self.failure)
        self.ledger.attempt("evt-failure", "ISS-001",
                            "Normalize all embedded whitespace consistently",
                            "actual-fixture-reproduction", "PENDING",
                            "synthetic-reformer", "synthetic-context-reformer")
        path = Path(self.home) / "recovery.json"
        path.write_text(json.dumps(receipt("evaluator", "evt-failure:ISS-001:1",
                                          "recovery-evaluator", checks=checks())))
        with self.assertRaises(GateError):
            self.ledger.resolve_recovery("evt-failure", "ISS-001", path, None)
        self.ledger.resolve_recovery("evt-failure", "ISS-001", path, TEST_KEY)
        self.assertEqual(self.ledger.event("evt-failure")["disposition"], "RECOVERED")

    def test_3_reusable_candidate_gate_with_synthetic_receipts(self):
        self.ledger.ingest(self.failure)
        item, audit = complete_scope(self.ledger, "evt-failure", manifest(
            self.ledger.event("evt-failure")))
        self.assertEqual(item["classification"], "MINOR")
        self.ledger.review("candidate-1", receipt("adversary", "candidate-1",
                                                  "adversary", audit_digest=audit), TEST_KEY)
        self.ledger.review("candidate-1", receipt("evaluator", "candidate-1",
                                                  "evaluator", checks=checks(), audit_digest=audit), TEST_KEY)
        self.assertEqual(self.ledger.decide("candidate-1"), "IMPROVEMENT_VALIDATED")

    def test_4_bad_improvement_rejected_by_failed_regression(self):
        self.ledger.ingest(self.failure)
        self.ledger.candidate("evt-failure", manifest(
            self.ledger.event("evt-failure")))
        self.ledger.review("candidate-1", receipt("adversary", "candidate-1",
                                                  "bad-adversary", "FAIL"), TEST_KEY)
        self.ledger.review("candidate-1", receipt("evaluator", "candidate-1",
                                                  "bad-evaluator", "FAIL",
                                                  checks=checks()), TEST_KEY)
        self.assertEqual(self.ledger.decide("candidate-1"), "IMPROVEMENT_REJECTED")
        with self.assertRaises(GateError):
            self.ledger.activate("candidate-1", None, TEST_KEY)

    def test_5_exactly_three_and_no_renaming_reset(self):
        self.ledger.ingest(self.failure)
        for i in range(3):
            item = self.ledger.attempt("evt-failure", "ISS-001",
                "Correct distinct underlying conversion step number " + str(i),
                "attempt-log-" + str(i), "FAILED")
            self.assertEqual(item["attempt"], i + 1)
        self.assertEqual(self.ledger.event("evt-failure")["disposition"], "ESCALATED")
        with self.assertRaises(GateError):
            self.ledger.attempt("evt-failure", "ISS-001", "Try a fourth new alternative",
                                "attempt-log-4")
        clone = copy.deepcopy(self.failure)
        clone["event_id"] = "evt-renamed"
        clone["issues"][0]["id"] = "RENAMED-DEFECT"
        clone["issues"][0]["root_key"] = "a-new-label"
        self.ledger.ingest(clone)
        self.assertEqual(self.ledger.event("evt-renamed")["issue_map"]["RENAMED-DEFECT"],
                         self.ledger.event("evt-failure")["issue_map"]["ISS-001"])
        with self.assertRaises(GateError):
            self.ledger.attempt("evt-renamed", "RENAMED-DEFECT",
                                "Attempt again after renaming same cause", "another-log")
        self.assertEqual(len(next(iter(self.ledger.data["roots"].values()))["attempts"]), 3)

    def test_6_major_pr_required_and_rollback_pin(self):
        self.ledger.ingest(self.failure)
        c, audit = complete_scope(self.ledger, "evt-failure", manifest(
            self.ledger.event("evt-failure"), tags=["agent_roles"]))
        self.assertEqual(c["classification"], "MAJOR")
        self.ledger.review("candidate-1", receipt("adversary", "candidate-1",
                                                  "major-adversary", audit_digest=audit), TEST_KEY)
        self.ledger.review("candidate-1", receipt("evaluator", "candidate-1",
                                                  "major-evaluator", checks=checks(), audit_digest=audit), TEST_KEY)
        with self.assertRaises(GateError):
            self.ledger.decide("candidate-1")
        self.ledger.decide("candidate-1",
                           "https://github.com/denni1cd/adeptus_inquisition/pull/1")
        self.assertTrue(self.ledger.activate("candidate-1").startswith("BLOCKED"))
        load = receipt("loader", "candidate-1", "load", checks=None, audit_digest=audit)
        load["payload"]["content_sha256"] = "d" * 64
        load["payload"]["loaded_commit"] = "c" * 40
        load = sign(load["payload"])
        self.assertEqual(self.ledger.activate("candidate-1", load, TEST_KEY),
                         "ACTIVE_PROVISIONAL")
        self.assertEqual(self.ledger.data["active"][
            "denni1cd/adeptus_inquisition"]["kind"], "VALIDATED_LOCAL")
        self.assertEqual(self.ledger.rollback("denni1cd/adeptus_inquisition")["kind"],
                         "APPROVED_BASELINE")

    def test_7_unsigned_or_same_context_cannot_pass(self):
        self.ledger.ingest(self.failure)
        self.ledger.candidate("evt-failure", manifest(self.ledger.event("evt-failure")))
        with self.assertRaises(GateError):
            self.ledger.decide("candidate-1")
        with self.assertRaises(GateError):
            self.ledger.review("candidate-1", {"payload": receipt(
                "adversary", "candidate-1", "x")["payload"]}, TEST_KEY)
        self.ledger.review("candidate-1", receipt("adversary", "candidate-1",
                                                  "same"), TEST_KEY)
        with self.assertRaises(GateError):
            self.ledger.review("candidate-1", receipt("evaluator", "candidate-1",
                                                      "same", checks=checks()), TEST_KEY)
        with self.assertRaises(GateError):
            self.ledger.decide("candidate-1")

    def test_8_protected_rule_change_requires_emperor(self):
        self.ledger.ingest(self.failure)
        candidate, audit = complete_scope(self.ledger, "evt-failure", manifest(
            self.ledger.event("evt-failure"), tags=["validation"],
            paths=["inquisition/engine.py"]))
        self.assertEqual(candidate["classification"], "PROTECTED")
        self.ledger.review("candidate-1", receipt("adversary", "candidate-1",
                                                  "protected-adv", audit_digest=audit), TEST_KEY)
        self.ledger.review("candidate-1", receipt("evaluator", "candidate-1",
                                                  "protected-eval", checks=checks(), audit_digest=audit), TEST_KEY)
        url = "https://github.com/denni1cd/adeptus_inquisition/pull/1"
        with self.assertRaises(GateError):
            self.ledger.decide("candidate-1", url)
        self.assertEqual(candidate["disposition"], "PENDING")
        approval = receipt("emperor-approval", "candidate-1", "emperor", audit_digest=audit)
        approval["payload"]["explicit"] = True
        approval = sign(approval["payload"])
        self.assertEqual(self.ledger.decide("candidate-1", url, approval, TEST_KEY), "IMPROVEMENT_VALIDATED")

    def test_immutable_packet_and_frozen_criteria(self):
        self.ledger.ingest(self.failure)
        altered = copy.deepcopy(self.failure)
        altered["contract"]["criteria"][0]["test"] = "weaker fake success"
        with self.assertRaises(GateError):
            self.ledger.ingest(altered)
        tampered = manifest(self.ledger.event("evt-failure"))
        tampered["criteria_hash"] = digest(["weakened"])
        with self.assertRaises(GateError):
            self.ledger.candidate("evt-failure", tampered)

    def test_futile_missing_key_and_restart_durability(self):
        self.ledger.ingest(self.failure)
        self.ledger.attempt("evt-failure", "ISS-001",
                            "Fix source-provided casing before lookup",
                            "case-log", "FAILED")
        restarted = Ledger(self.home)
        self.assertEqual(len(restarted.root_for_issue(
            "evt-failure", "ISS-001")["attempts"]), 1)
        with self.assertRaises(GateError):
            restarted.attempt("evt-failure", "ISS-001",
                              "Fix source-provided casing before lookup",
                              "repeated-case-log")

    def test_immediate_external_blocker_consumes_no_attempts(self):
        self.ledger.ingest(self.failure)
        state = self.ledger.suspend("evt-failure", "ISS-001", "BLOCKED",
                                    "Required external repository permission is missing",
                                    "tool-output/permission-denied.json")
        self.assertEqual(state, "BLOCKED")
        root = self.ledger.root_for_issue("evt-failure", "ISS-001")
        self.assertEqual(len(root["attempts"]), 0)
        self.assertEqual(root["status"], "BLOCKED")
        self.assertIn("next_action", self.ledger.event("evt-failure")["escalation"])

    def test_recovery_and_no_reusable_improvement_are_separate(self):
        self.ledger.ingest(self.failure)
        self.ledger.attempt("evt-failure", "ISS-001",
                            "Fix canonical key handling before issue lookup",
                            "run/repair.log", "PENDING",
                            "reformer-delegation", "reformer-private-context")
        path = Path(self.home) / "recovery-2.json"
        path.write_text(json.dumps(receipt("evaluator", "evt-failure:ISS-001:1",
                                          "second-evaluator", checks=checks())))
        self.ledger.resolve_recovery("evt-failure", "ISS-001", path, TEST_KEY)
        state = self.ledger.no_improvement("evt-failure",
                         "The defect was isolated application data, not a reusable skill",
                         "tests/heldout-and-regression-results.txt")
        self.assertEqual(state, "RECOVERED")
        event = Ledger(self.home).event("evt-failure")
        self.assertEqual(event["recovery_disposition"], "RECOVERED")
        self.assertEqual(event["improvement_disposition"], "NO_CHANGE_JUSTIFIED")

    def test_independent_roots_get_separate_budgets_and_reroute_preserves_identity(self):
        self.ledger.ingest(self.failure)
        separate = copy.deepcopy(self.failure)
        separate["event_id"] = "evt-independent"
        separate["issues"][0]["id"] = "ISS-NEW"
        separate["issues"][0]["root_cause"] = "corrupted checksum parser"
        separate["issues"][0]["root_key"] = "checksums"
        self.ledger.ingest(separate)
        self.assertEqual(len(self.ledger.data["roots"]), 2)
        self.ledger.attempt("evt-independent", "ISS-NEW",
                            "Validate checksum parser before loading state",
                            "logs/checksum-case.log", "FAILED")
        self.assertEqual(len(self.ledger.root_for_issue(
            "evt-failure", "ISS-001")["attempts"]), 0)
        rerouted = copy.deepcopy(self.failure)
        rerouted["event_id"] = "evt-rerouted"
        rerouted["issues"][0]["id"] = "ISS-REROUTED"
        rerouted["issues"][0]["scope"] = "another subsystem"
        self.ledger.ingest(rerouted)
        self.assertEqual(self.ledger.event("evt-rerouted")["issue_map"]["ISS-REROUTED"],
                         self.ledger.event("evt-failure")["issue_map"]["ISS-001"])

    def test_action_allowlist_rejects_unauthorized_repair_and_skill_change(self):
        self.ledger.ingest(self.clean)
        with self.assertRaises(GateError):
            self.ledger.attempt("evt-clean", "not-an-issue",
                                "Attempt an unauthorized implementation repair",
                                "logs/unauthorized.log", "FAILED")
        with self.assertRaises(GateError):
            self.ledger.candidate("evt-clean", manifest(
                self.ledger.event("evt-clean")))

    def test_legacy_positive_receipts_do_not_bypass_scope_audit(self):
        self.ledger.ingest(self.failure)
        self.ledger.candidate("evt-failure", manifest(self.ledger.event("evt-failure")))
        self.ledger.review("candidate-1", receipt("adversary", "candidate-1", "old-adv"), TEST_KEY)
        self.ledger.review("candidate-1", receipt("evaluator", "candidate-1", "old-eval", checks=checks()), TEST_KEY)
        with self.assertRaises(GateError):
            self.ledger.decide("candidate-1")

    def test_independent_operator_pins_authorize_exact_audited_payloads_without_hmac(self):
        self.ledger.ingest(self.failure)
        c, audit = complete_scope(self.ledger, "evt-failure", manifest(self.ledger.event("evt-failure")))
        adv = receipt("adversary", "candidate-1", "operator-adv", audit_digest=audit)["payload"]
        ev = receipt("evaluator", "candidate-1", "operator-eval", checks=checks(), audit_digest=audit)["payload"]
        load = receipt("loader", "candidate-1", "operator-load", audit_digest=audit)["payload"]
        load.update(content_sha256="d"*64, loaded_commit="c"*40)
        pins = Path(self.home) / "fixture-operator-pins.json"
        pins.write_text(json.dumps({"schema": "INQUISITION-OPERATOR-PINS-v1",
                                    "approved_payload_sha256": [digest(p) for p in (adv, ev, load)]}))
        with patch.dict(os.environ, {"INQUISITION_OPERATOR_TRUST_STORE": str(pins)}):
            self.ledger.review("candidate-1", {"payload": adv}, None)
            self.ledger.review("candidate-1", {"payload": ev}, None)
            self.assertEqual(self.ledger.decide("candidate-1"), "IMPROVEMENT_VALIDATED")
            with self.assertRaises(GateError):
                self.ledger.activate("candidate-1", {"payload": dict(load, loaded_commit="a"*40)}, None)
            self.assertEqual(self.ledger.activate("candidate-1", {"payload": load}, None), "ACTIVE_PROVISIONAL")


if __name__ == "__main__":
    unittest.main()
