"""Attach offline evaluation artifacts to a paused Inquisition event as findings.

No recovery, candidate validation, signature, approval, or activation gate
is bypassed by recording evaluation evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from inquisition.engine import Ledger
from .atif_adapter import EvidenceError

ADVISORY_STATES = {
    "REJECT_CANDIDATE", "TRADEOFF_REQUIRES_REVIEW",
    "SUPPORTED_FOR_INDEPENDENT_REVIEW", "NO_IMPROVEMENT_DEMONSTRATED",
}


def _artifact(path):
    file = Path(path)
    if not file.is_file():
        raise EvidenceError("missing evidence artifact: " + str(file))
    content = file.read_bytes()
    return {"path": str(file.resolve()), "sha256": hashlib.sha256(content).hexdigest()}


def attach(home, event_id, provenance_path, grade_path, comparison_path):
    provenance = json.loads(Path(provenance_path).read_text(encoding="utf-8"))
    comparison = json.loads(Path(comparison_path).read_text(encoding="utf-8"))
    if provenance.get("schema_version") != "INQUISITION-PROVENANCE-v1":
        raise EvidenceError("unrecognized provenance sidecar")
    if comparison.get("status") not in ADVISORY_STATES or comparison.get("approval") is not False:
        raise EvidenceError("comparison must be an unapproved advisory result")
    for field in ("run_id", "completeness", "missing_or_unproven"):
        if field not in provenance:
            raise EvidenceError("incomplete provenance manifest")
    # Files are hashed for reference integrity; their authorship is not authenticated.
    artifacts = {
        "provenance": _artifact(provenance_path),
        "vally_grade": _artifact(grade_path),
        "comparison": _artifact(comparison_path),
    }
    ledger = Ledger(home)
    ledger.record_finding(event_id, {
        "classification": "PROCESS_EVALUATION",
        "evidence": artifacts,
        "evaluation_disposition": comparison["status"],
        "run_id": provenance["run_id"],
        "coverage": provenance["completeness"],
        "unproven_fields": provenance["missing_or_unproven"],
        "authorization_effect": "NONE",
        "warning": "Artifacts are referenced, not host-authenticated. "
                   "Independent Inquisition review and activation gates remain unchanged.",
    })
    return {
        "state": "EVALUATION_ATTACHED_NOT_APPROVED",
        "event_id": event_id,
        "evaluation_disposition": comparison["status"],
        "coverage": provenance["completeness"],
        "artifacts": artifacts,
    }
