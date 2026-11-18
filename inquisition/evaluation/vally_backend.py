"""Offline Vally subprocess adapter. Never invokes vally eval or Copilot.

Only curated deterministic grader types are accepted by the limited V1.1
profile checker. This is not a general YAML validator; Vally lint remains the
authoritative spec validator.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from .atif_adapter import EvidenceError

# Explicit allowlist excludes model judges, arbitrary programs and file commands.
SAFE_GRADERS = frozenset({
    "completed", "exit-success", "error-count", "loop-outcome",
    "max-repeat", "output-contains", "output-matches",
    "output-not-contains", "output-not-matches",
    "skill-invocation", "step-count", "tool-call-count", "tool-calls",
    "transcript-contains", "transcript-matches",
    "transcript-not-contains", "transcript-not-matches", "turn-count",
})
GRADER_LINE = re.compile(r"^\s*-\s*type:\s*['\"]?([a-z][a-z0-9-]*)['\"]?\s*(?:#.*)?$")


def preflight_spec(path):
    """Fail closed for unsupported dynamic/LLM grader configuration."""
    text = Path(path).read_text(encoding="utf-8")
    found = []
    for line in text.splitlines():
        if re.search(r"\btype\s*:", line) and not line.lstrip().startswith("#"):
            match = GRADER_LINE.fullmatch(line)
            if not match or match.group(1) not in SAFE_GRADERS:
                raise EvidenceError("unapproved grader type or YAML syntax: " + line.strip())
            found.append(match.group(1))
        if re.search(r"\b(executor|judge_model|judge_timeout|grader_plugin)\s*:", line):
            raise EvidenceError("offline deterministic profile cannot configure executors/judges")
        if re.search(r"\b(?:!include|!!python|\-\s*\{)", line):
            raise EvidenceError("unsupported inline or tagged YAML in offline profile")
    if not found:
        raise EvidenceError("profile has no supported graders")
    return found


def grade(atif_path, eval_spec, output_path, stimulus, vally_executable="vally"):
    """Run actual 'vally grade' with stdin ATIF. CLI exit 0 is NOT a passed verdict."""
    preflight_spec(eval_spec)
    atif_bytes = Path(atif_path).read_bytes()
    data = json.loads(atif_bytes)
    if not data.get("schema_version", "").startswith("ATIF-") or not data.get("steps"):
        raise EvidenceError("input is not a non-empty ATIF trajectory")
    if not isinstance(stimulus, str) or not stimulus.strip():
        raise EvidenceError("explicit eval stimulus is required")
    executable = shutil.which(vally_executable)
    if not executable:
        raise EvidenceError("Vally CLI not installed; install @microsoft/vally-cli separately")
    cmd = [executable, "grade", "--eval-spec", str(Path(eval_spec).resolve()),
           "--stimulus", stimulus, "--output", "jsonl"]
    try:
        completed = subprocess.run(cmd, input=atif_bytes, capture_output=True, timeout=180,
                                   check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EvidenceError("offline Vally grade did not complete: " + str(exc)) from exc
    if completed.returncode != 0:
        raise EvidenceError("Vally grading error (not a valid failed verdict): " +
                            completed.stderr.decode("utf-8", errors="replace")[-1000:])
    output = completed.stdout.decode("utf-8", errors="strict")
    try:
        records = [json.loads(line) for line in output.splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise EvidenceError("Vally did not return JSONL") from exc
    if not records or not all(isinstance(record, dict) for record in records):
        raise EvidenceError("Vally returned no structured grading records")
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(output.rstrip() + "\n", encoding="utf-8")
    return {
        "state": "GRADED_NOT_AUTHORIZED",
        "records": len(records),
        "output": str(output_file),
        "atif_sha256": hashlib.sha256(atif_bytes).hexdigest(),
        "profile_sha256": hashlib.sha256(Path(eval_spec).read_bytes()).hexdigest(),
        "warning": "Exit 0 means grading completed, not that the agent passed. "
                   "Neither score nor independent delegation is authenticated by this bridge.",
    }
