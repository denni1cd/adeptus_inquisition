"""Deterministic Inquisition ledger and gates. Agents do the reasoning; this module enforces policy."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from pathlib import Path

STATES = {"RECOVERED", "IMPROVEMENT_VALIDATED", "IMPROVEMENT_REJECTED",
          "NO_CHANGE_JUSTIFIED", "BLOCKED", "ESCALATED"}
TRIGGERS = {"TERMINAL_FAILURE", "MAJOR_MILESTONE"}
MAJOR_TAGS = {"agent_roles", "architecture", "execution_authority", "validation",
              "recovery_policy", "approval_policy", "public_contract"}
PROTECTED_TAGS = {"inquisition_safeguards", "inquisition_evaluation",
                  "inquisition_approval"}
PROTECTED_PATHS = {"inquisition/engine.py", "skills/adeptus-inquisition/SKILL.md",
                   "schemas/event.schema.json", "schemas/receipt.schema.json"}
MAX_ATTEMPTS = 3


class GateError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def normalize(value):
    return re.sub(r"\s+", " ", str(value).strip().lower())


def require(condition, message):
    if not condition:
        raise GateError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp-" + str(os.getpid()))
    with temp.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


class Ledger:
    """Single-writer ledger. A Work invocation must not launch simultaneous writers."""

    def __init__(self, home):
        self.path = Path(home) / "ledger.json"
        self.data = read_json(self.path) if self.path.exists() else {
            "schema": 1, "events": {}, "roots": {}, "candidates": {},
            "active": {}, "audit": []
        }

    def save(self, action, detail):
        self.data["audit"].append({"index": len(self.data["audit"]) + 1,
                                   "action": action, "detail": detail})
        write_atomic(self.path, self.data)

    def event(self, event_id):
        require(event_id in self.data["events"], "unknown event")
        return self.data["events"][event_id]

    def root_for_issue(self, event_id, issue_id):
        event = self.event(event_id)
        require(issue_id in event["issue_map"], "unknown issue")
        return self.data["roots"][event["issue_map"][issue_id]]

    def ingest(self, package):
        mandatory = ["event_id", "trigger", "objective", "constraints", "contract",
                     "milestone", "branch", "artifacts", "reviews", "issues",
                     "authorization", "baseline"]
        require(all(k in package for k in mandatory), "incomplete event contract")
        require(package["trigger"] in TRIGGERS, "invalid trigger")
        require(isinstance(package["issues"], list), "issues must be a list")
        require(bool(package["objective"]), "original objective required")
        require(bool(package["contract"].get("criteria")), "fixed acceptance criteria required")
        require(package["contract"].get("approved") is True, "contract must be approved")
        require(bool(package["baseline"].get("commit")), "pinned baseline required")
        require(bool(package["branch"].get("version", {}).get("commit")), "branch version required")
        require(bool(package["authorization"].get("repositories")), "authorized repositories required")
        eid = package["event_id"]
        packet_hash = digest(package)
        if eid in self.data["events"]:
            require(self.data["events"][eid]["packet_hash"] == packet_hash,
                    "event ID collision or mutated evidence package")
            return self.data["events"][eid]
        issue_map = {}
        for issue in package["issues"]:
            require(all(issue.get(k) for k in ("id", "scope", "root_cause", "root_key")),
                    "issue requires id, scope, root_cause, and root_key")
            # Root fingerprint survives a renamed issue and persists across event packages.
            key = digest(normalize(issue["root_cause"]))[:24]
            root_id = "ROOT-" + key
            if root_id not in self.data["roots"]:
                self.data["roots"][root_id] = {
                    "fingerprint": key, "scope": issue["scope"],
                    "cause": issue["root_cause"], "aliases": [], "attempts": [],
                    "status": "OPEN", "source_keys": []
                }
            root = self.data["roots"][root_id]
            alias = eid + ":" + issue["id"]
            if alias not in root["aliases"]:
                root["aliases"].append(alias)
            if issue["root_key"] not in root["source_keys"]:
                root["source_keys"].append(issue["root_key"])
            require(issue["id"] not in issue_map, "duplicate issue ID")
            issue_map[issue["id"]] = root_id
        record = {
            "packet_hash": packet_hash, "packet": package, "issue_map": issue_map,
            "criteria_hash": digest(package["contract"]["criteria"]),
            "disposition": "PAUSED", "findings": [], "candidate_ids": []
        }
        self.data["events"][eid] = record
        self.save("ingest", {"event": eid, "issues": issue_map})
        return record

    def record_finding(self, event_id, finding):
        event = self.event(event_id)
        require(event["disposition"] == "PAUSED", "event already disposed")
        require(finding.get("classification") and finding.get("evidence"),
                "finding must be classified and supported")
        event["findings"].append(finding)
        self.save("finding", {"event": event_id, "finding": finding})

    def attempt(self, event_id, issue_id, hypothesis, evidence, outcome="FAILED",
                reformer_invocation_id=None, reformer_context_id=None):
        require(outcome in {"FAILED", "PENDING"}, "outcome must be FAILED or PENDING")
        require(len(normalize(hypothesis)) >= 12, "meaningful corrective hypothesis required")
        require(bool(evidence), "attempt evidence reference required")
        if outcome == "PENDING":
            require(reformer_invocation_id and reformer_context_id,
                    "pending repair needs attributed Reformer invocation and context")
        event = self.event(event_id)
        require(event["disposition"] == "PAUSED", "event already disposed")
        root = self.root_for_issue(event_id, issue_id)
        require(root["status"] != "RECOVERED", "issue already recovered")
        require(len(root["attempts"]) < MAX_ATTEMPTS, "attempt budget exhausted")
        normalized = normalize(hypothesis)
        require(normalized not in [a["hypothesis_key"] for a in root["attempts"]],
                "repeat hypothesis is not a new corrective attempt")
        n = len(root["attempts"]) + 1
        item = {"attempt": n, "event": event_id, "issue": issue_id,
                "hypothesis": hypothesis, "hypothesis_key": normalized,
                "evidence": evidence, "outcome": outcome,
                "reformer_invocation_id": reformer_invocation_id,
                "reformer_context_id": reformer_context_id}
        root["attempts"].append(item)
        if n == MAX_ATTEMPTS and outcome == "FAILED":
            root["status"] = "ESCALATED"
            event["disposition"] = "ESCALATED"
        self.save("attempt", {"root": event["issue_map"][issue_id], "record": item})
        return item

    def resolve_recovery(self, event_id, issue_id, receipt_path, key):
        event = self.event(event_id)
        root = self.root_for_issue(event_id, issue_id)
        require(root["attempts"], "no corrective attempt")
        attempt = root["attempts"][-1]
        require(attempt["outcome"] == "PENDING", "no pending repair to verify")
        payload = verify_receipt(read_json(receipt_path), key)
        require(payload["role"] == "evaluator", "recovery requires evaluator")
        require(payload["subject"] == event_id + ":" + issue_id + ":" + str(attempt["attempt"]),
                "evaluator verified a different attempt")
        require(payload["verdict"] == "PASS" and payload.get("checks"),
                "no independent positive execution evidence")
        require(payload["invocation_id"] != attempt.get("reformer_invocation_id") and
                payload["context_id"] != attempt.get("reformer_context_id"),
                "self evaluation prohibited")
        attempt["outcome"] = "RECOVERED"
        attempt["evaluator"] = payload
        root["status"] = "RECOVERED"
        event["disposition"] = "RECOVERED"
        self.save("recovery", {"event": event_id, "root": event["issue_map"][issue_id]})
        return attempt

    def close_milestone(self, event_id, inspection):
        event = self.event(event_id)
        require(event["packet"]["trigger"] == "MAJOR_MILESTONE", "not a milestone")
        require(not event["packet"]["issues"], "cannot close milestone with unresolved issues")
        require(event["disposition"] == "PAUSED", "milestone already closed")
        require(inspection.get("inspected_artifacts") and inspection.get("checks") and
                inspection.get("reason") and inspection.get("no_change") is True,
                "substantiated no-change inspection required")
        event["findings"].append(inspection)
        event["disposition"] = "NO_CHANGE_JUSTIFIED"
        self.save("release_milestone", {"event": event_id, "inspection": inspection})
        return event["disposition"]

    def candidate(self, event_id, manifest):
        event = self.event(event_id)
        mandatory = ["candidate_id", "repository", "baseline_commit", "candidate_commit",
                     "content_sha256", "changed_paths", "impact_tags", "hypothesis",
                     "baseline_checks", "candidate_checks", "regression_checks",
                     "holdout_checks", "proposer_invocation_id", "proposer_context_id", "criteria_hash"]
        require(all(k in manifest for k in mandatory), "incomplete candidate manifest")
        require(manifest["criteria_hash"] == event["criteria_hash"],
                "candidate must not redefine acceptance criteria")
        require(manifest["repository"] in event["packet"]["authorization"]["repositories"],
                "repository not authorized")
        require(manifest["baseline_commit"] == event["packet"]["baseline"]["commit"],
                "candidate is not based on pinned baseline")
        require(manifest["candidate_commit"] != manifest["baseline_commit"],
                "candidate must differ from baseline")
        require(len(manifest["content_sha256"]) == 64, "SHA-256 of candidate is required")
        tags = set(manifest["impact_tags"])
        paths = set(manifest["changed_paths"])
        classification = ("PROTECTED" if tags & PROTECTED_TAGS or
                          manifest["repository"].endswith("/adeptus_inquisition") and
                          bool(paths & PROTECTED_PATHS)
                          else "MAJOR" if tags & MAJOR_TAGS else "MINOR")
        require(bool(manifest["hypothesis"]) and manifest["baseline_checks"] and
                manifest["candidate_checks"] and manifest["regression_checks"] and
                manifest["holdout_checks"], "falsifiable comparison and holdout required")
        cid = manifest["candidate_id"]
        if cid in self.data["candidates"]:
            require(self.data["candidates"][cid]["manifest"] == manifest,
                    "candidate ID is immutable")
            return self.data["candidates"][cid]
        item = {"event": event_id, "manifest": manifest, "classification": classification,
                "reviews": {}, "disposition": "PENDING", "activation": "INACTIVE"}
        self.data["candidates"][cid] = item
        event["candidate_ids"].append(cid)
        self.save("candidate", {"candidate": cid, "classification": classification})
        return item

    def review(self, candidate_id, receipt, key):
        candidate = self.data["candidates"].get(candidate_id)
        require(candidate is not None, "unknown candidate")
        p = verify_receipt(receipt, key)
        require(p["subject"] == candidate_id, "review is for another candidate")
        require(p["role"] in {"adversary", "evaluator"}, "invalid review role")
        require(p["invocation_id"] != candidate["manifest"]["proposer_invocation_id"] and
                p["context_id"] != candidate["manifest"]["proposer_context_id"],
                "author may not review own candidate")
        require(p["role"] not in candidate["reviews"], "role already reviewed")
        if candidate["reviews"]:
            other = next(iter(candidate["reviews"].values()))
            require(p["invocation_id"] != other["invocation_id"], "reviewers share invocation")
            require(p["context_id"] != other["context_id"], "reviewers share context")
        if p["role"] == "evaluator":
            checks = p.get("checks", {})
            require(all(checks.get(k, {}).get("executed") is True for k in
                        ("baseline", "candidate", "regression", "holdout")),
                    "evaluator must execute baseline, candidate, regression and holdout")
            require(all(checks[k].get("artifact") for k in
                        ("baseline", "candidate", "regression", "holdout")),
                    "execution evidence artifacts missing")
        candidate["reviews"][p["role"]] = p
        self.save("review", {"candidate": candidate_id, "role": p["role"],
                             "invocation": p["invocation_id"]})
        return p

    def decide(self, candidate_id, pr_url=None, emperor_approval=None, key=None):
        candidate = self.data["candidates"][candidate_id]
        reviews = candidate["reviews"]
        require("adversary" in reviews and "evaluator" in reviews,
                "BLOCKED: genuine independent adversary and evaluator receipts required")
        adversary, evaluator = reviews["adversary"], reviews["evaluator"]
        if adversary["verdict"] != "PASS" or evaluator["verdict"] != "PASS":
            candidate["disposition"] = "IMPROVEMENT_REJECTED"
            self.save("reject", {"candidate": candidate_id,
                                 "adversary": adversary["verdict"],
                                 "evaluator": evaluator["verdict"]})
            return candidate["disposition"]
        require(candidate["manifest"]["candidate_checks"] !=
                candidate["manifest"]["baseline_checks"],
                "no measurable demonstrated change")
        classification = candidate["classification"]
        if classification in {"MAJOR", "PROTECTED"}:
            require(pr_url and pr_url.startswith("https://github.com/") and "/pull/" in pr_url,
                    "major candidate requires recorded GitHub PR")
        if classification == "PROTECTED":
            require(emperor_approval, "BLOCKED: explicit Emperor approval absent")
            a = verify_receipt(emperor_approval, key)
            require(a["role"] == "emperor-approval" and a["subject"] == candidate_id and
                    a["verdict"] == "PASS" and a.get("explicit") is True,
                    "BLOCKED: protected safeguards require trusted explicit Emperor approval")
        candidate["disposition"] = "IMPROVEMENT_VALIDATED"
        candidate["pr_url"] = pr_url
        candidate["emperor_approval"] = emperor_approval
        self.event(candidate["event"])["disposition"] = "IMPROVEMENT_VALIDATED"
        self.save("validated", {"candidate": candidate_id, "classification": classification,
                                 "pr": pr_url})
        return candidate["disposition"]

    def activate(self, candidate_id, load_receipt=None, key=None):
        candidate = self.data["candidates"][candidate_id]
        require(candidate["disposition"] == "IMPROVEMENT_VALIDATED",
                "unvalidated candidate cannot activate")
        if not load_receipt:
            return "BLOCKED: fresh Work invocation/load proof required"
        p = verify_receipt(load_receipt, key)
        require(p["role"] == "loader" and p["subject"] == candidate_id and
                p["verdict"] == "PASS", "trusted runtime loader attestation required")
        require(p.get("content_sha256") == candidate["manifest"]["content_sha256"] and
                p.get("loaded_commit") == candidate["manifest"]["candidate_commit"],
                "runtime loaded a different candidate commit or skill hash")
        repo = candidate["manifest"]["repository"]
        prior = self.data["active"].get(repo, {
            "commit": candidate["manifest"]["baseline_commit"],
            "content_sha256": self.event(candidate["event"])["packet"]["baseline"].get("skill_sha256"),
            "kind": "APPROVED_BASELINE"
        })
        self.data["active"][repo] = {
            "commit": candidate["manifest"]["candidate_commit"],
            "content_sha256": p["content_sha256"], "kind": "VALIDATED_LOCAL",
            "candidate_id": candidate_id, "previous": prior,
            "load_evidence": p["tool_trace"]
        }
        candidate["activation"] = "ACTIVE_PROVISIONAL"
        self.save("activate", {"candidate": candidate_id, "previous": prior})
        return "ACTIVE_PROVISIONAL"

    def rollback(self, repository):
        require(repository in self.data["active"], "no activation to roll back")
        active = self.data["active"][repository]
        require("previous" in active, "already at baseline")
        previous = active["previous"]
        self.data["active"][repository] = previous
        if active.get("candidate_id") in self.data["candidates"]:
            self.data["candidates"][active["candidate_id"]]["activation"] = "ROLLED_BACK"
        self.save("rollback", {"repository": repository, "restored": previous,
                               "note": "new invocations only; running agents remain pinned"})
        return previous


def verify_receipt(receipt, key):
    """Only a trusted dispatcher's out-of-band HMAC receipts count; no unsigned self-claims."""
    require(bool(key), "BLOCKED: no trusted delegation receipt verifier configured")
    require(isinstance(receipt, dict) and "signature" in receipt and "payload" in receipt,
            "unsigned or malformed delegation receipt")
    p = receipt["payload"]
    required = ["role", "subject", "invocation_id", "context_id", "tool_trace",
                "verdict", "evidence"]
    require(all(p.get(k) for k in required), "receipt missing independent provenance")
    require(p["verdict"] in {"PASS", "FAIL", "BLOCKED"}, "invalid review verdict")
    require(p["tool_trace"] != p["evidence"], "tool provenance and evidence must be distinct")
    mac = hmac.new(key.encode("utf-8"), canonical(p).encode("utf-8"),
                   hashlib.sha256).hexdigest()
    require(hmac.compare_digest(mac, receipt["signature"]),
            "untrusted receipt signature")
    return p
