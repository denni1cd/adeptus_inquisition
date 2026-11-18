"""Adapt explicitly recorded Adeptus execution events to Vally's ATIF-v1.6.

The adapter never invents agent steps, tool calls, tool results, or metrics.
Original source references remain in a separate provenance sidecar.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SOURCE_KINDS = {"system", "user", "agent"}
CAPTURE_FIELDS = ("agent_steps", "tool_results", "subagent_events", "timing", "token_usage")


class EvidenceError(ValueError):
    """Missing or malformed evidence; a run must not be silently completed."""


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode("utf-8")).hexdigest()


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def adapt(record):
    """Return (ATIF document, provenance manifest), without claiming authentication."""
    if record.get("schema_version") != "ADEPTUS-RUN-v1":
        raise EvidenceError("expected ADEPTUS-RUN-v1 evidence envelope")
    for field in ("run_id", "branch", "version", "task"):
        if not _nonempty(record.get(field)):
            raise EvidenceError("missing " + field)
    events = record.get("events")
    if not isinstance(events, list):
        raise EvidenceError("events must be a list (possibly empty)")
    capture = record.get("capture", {})
    if not isinstance(capture, dict) or any(
        value not in (True, False) for value in capture.values()
    ):
        raise EvidenceError("capture values must be booleans")
    steps = []
    sources = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise EvidenceError("event must be an object")
        kind = event.get("source")
        if kind not in SOURCE_KINDS:
            raise EvidenceError("unsupported source at event " + str(index))
        if not _nonempty(event.get("message")) or not _nonempty(event.get("source_ref")):
            raise EvidenceError("event requires message and source_ref")
        step = {"step_id": index, "source": kind, "message": event["message"]}
        calls = event.get("tool_calls", [])
        results = event.get("tool_results", [])
        if not isinstance(calls, list) or not isinstance(results, list):
            raise EvidenceError("tool calls/results must be lists")
        if (calls or results) and kind != "agent":
            raise EvidenceError("tool activity belongs to an agent step")
        ids = set()
        if calls:
            mapped = []
            for call in calls:
                if not isinstance(call, dict) or not all(
                    _nonempty(call.get(k)) for k in ("tool_call_id", "function_name")
                ):
                    raise EvidenceError("tool call requires ID and function_name")
                cid = call["tool_call_id"]
                if cid in ids:
                    raise EvidenceError("duplicate tool call ID in step")
                ids.add(cid)
                args = call.get("arguments", {})
                if not isinstance(args, (dict, str)):
                    raise EvidenceError("tool arguments must be an object or string")
                mapped.append({"tool_call_id": cid,
                               "function_name": call["function_name"],
                               "arguments": args})
            step["tool_calls"] = mapped
        if results:
            mapped_results = []
            matched = set()
            for result in results:
                if not isinstance(result, dict) or not _nonempty(
                    result.get("source_call_id")
                ) or not isinstance(result.get("content"), str):
                    raise EvidenceError("tool result requires call ID and content")
                rid = result["source_call_id"]
                if rid not in ids or rid in matched:
                    raise EvidenceError("tool result must match exactly one in-step call")
                matched.add(rid)
                mapped_results.append({"source_call_id": rid, "content": result["content"]})
            step["observation"] = {"results": mapped_results}
        steps.append(step)
        sources.append({"step_id": index, "source_ref": event["source_ref"],
                        "tool_call_ids": sorted(ids),
                        "results_recorded": len(results)})
    if not steps:
        # Vally requires at least one step. Do not fake agent or user actions.
        steps.append({"step_id": 0, "source": "system",
                      "message": "No agent execution events were supplied."})
    missing = [field for field in CAPTURE_FIELDS if capture.get(field) is not True]
    incomplete_calls = [
        source["step_id"] for source in sources
        if len(source["tool_call_ids"]) != source["results_recorded"]
    ]
    if incomplete_calls:
        missing.append("unmatched_tool_results")
    atif = {
        "schema_version": "ATIF-v1.6",
        "session_id": record["run_id"],
        "agent": {"name": record["branch"], "version": record["version"]},
        "steps": steps,
    }
    manifest = {
        "schema_version": "INQUISITION-PROVENANCE-v1",
        "run_id": record["run_id"],
        "branch": record["branch"],
        "task": record["task"],
        "evidence_input_sha256": _digest(record),
        "atif_sha256": _digest(atif),
        "provenance": sources,
        "declared_capture": {field: capture.get(field) is True for field in CAPTURE_FIELDS},
        "missing_or_unproven": missing,
        "completeness": "PARTIAL" if missing or not events else "DECLARED_COMPLETE_NOT_AUTHENTICATED",
        "attestation": None,
        "warning": "Source references and declared capture coverage are not host-authenticated.",
    }
    return atif, manifest


def export(record_path, atif_path, manifest_path):
    record = json.loads(Path(record_path).read_text(encoding="utf-8"))
    atif, manifest = adapt(record)
    out, sidecar = Path(atif_path), Path(manifest_path)
    if out.resolve() == sidecar.resolve():
        raise EvidenceError("ATIF and manifest outputs must be different paths")
    out.parent.mkdir(parents=True, exist_ok=True)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(atif, indent=2) + "\n", encoding="utf-8")
    sidecar.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
