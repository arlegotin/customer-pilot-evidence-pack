#!/usr/bin/env python3
"""Validate prospective workflow logs; report descriptive totals, never success."""
import argparse
from collections import defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re


REQUIREMENTS = (
    "accuracy", "turnaround", "practical_improvement", "authorized_users",
    "task_rubric", "counterbalancing", "sample_design", "independent_grading",
    "holdout", "final_plan",
)
PHASES = ("preparation", "execution", "verification", "correction", "unsuccessful_attempts")
WORKFLOWS = ("baseline", "inspected_pack", "corrected_pack", "manual_control")
TASK_CLASSES = ("eligible", "blocked", "zero_cost", "missing_cost", "malformed")
CONSUMED = {"A", "B", "v1", "v2"}


class Invalid(ValueError):
    """An incomplete or contradictory evidence record."""


def require(condition, message):
    if not condition:
        raise Invalid(message)


def fields(value, expected, label):
    require(type(value) is dict, f"{label}: expected object")
    require(set(value) == set(expected), f"{label}: missing or unknown fields")


def nonempty(value, label):
    require(type(value) is str and bool(value.strip()), f"{label}: expected nonempty string")


def choice(value, allowed, label):
    require(type(value) is str and value in allowed, f"{label}: unsupported value")


def timestamp(value, label):
    nonempty(value, label)
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Invalid(f"{label}: invalid ISO timestamp") from exc
    require(result.utcoffset() is not None, f"{label}: timestamp must include timezone")
    return result


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise Invalid(f"nonfinite JSON value: {value}")


def load(path, jsonl, digests, name):
    data = Path(path).read_bytes()
    digests[name] = hashlib.sha256(data).hexdigest()
    content = data.decode("utf-8")
    options = {"object_pairs_hook": unique_object, "parse_constant": reject_constant}
    if not jsonl:
        return json.loads(content, **options)
    # Blank lines are not silently discarded: every supplied line is a record.
    return [json.loads(line, **options) for line in content.splitlines()]


def validate(manifest, events, grades):
    fields(manifest, ("schema_version", "study_id", "frozen_at", "requirements",
                      "development_consumed", "assignments"), "assignments")
    require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1,
            "unsupported schema_version")
    nonempty(manifest["study_id"], "study_id")
    frozen = timestamp(manifest["frozen_at"], "frozen_at")
    fields(manifest["requirements"], REQUIREMENTS, "requirements")
    blockers = []
    for name, receipt in manifest["requirements"].items():
        if receipt is None:
            blockers.append(f"missing sourced requirement: {name}")
            continue
        fields(receipt, ("source", "sha256"), f"requirement {name}")
        nonempty(receipt["source"], f"requirement {name} source")
        require(type(receipt["sha256"]) is str and
                re.fullmatch(r"[0-9a-f]{64}", receipt["sha256"]) is not None,
                f"requirement {name}: expected SHA-256 receipt")

    consumed = manifest["development_consumed"]
    require(type(consumed) is list, "development_consumed: expected list")
    for item in consumed:
        nonempty(item, "development_consumed identity")
    require(len(set(consumed)) == len(consumed) and CONSUMED <= set(consumed),
            "development_consumed must retain A/B/v1/v2 without duplicates")
    require(type(manifest["assignments"]) is list and manifest["assignments"],
            "assignments must contain every assigned task; empty study is not assessable")
    assignments = {}
    for row in manifest["assignments"]:
        fields(row, ("id", "task_id", "fixture_id", "task_class", "workflow", "operator",
                     "period", "evidence_status"), "assignment")
        for key in ("id", "task_id", "fixture_id", "operator"):
            nonempty(row[key], f"assignment {key}")
        require(row["id"] not in assignments, "duplicate assignment id")
        choice(row["workflow"], WORKFLOWS, "workflow")
        choice(row["period"], ("setup", "repeat"), "period")
        choice(row["task_class"], TASK_CLASSES, "task_class")
        choice(row["evidence_status"], ("development", "holdout"), "evidence_status")
        require(not (row["evidence_status"] == "holdout" and row["fixture_id"] in consumed),
                "development-consumed identity declared holdout")
        if row["evidence_status"] == "development":
            blockers.append(f"development evidence assignment: {row['id']}")
        assignments[row["id"]] = row

    records = {aid: {"phases": set(), "operator": defaultdict(float), "machine": 0.0,
                     "machine_count": 0, "interval_ends": [], "close": None}
               for aid in assignments}
    ids = set()
    operator_intervals = defaultdict(list)
    for row in events:
        require(type(row) is dict, "event: expected object")
        kind = row.get("kind")
        choice(kind, ("operator", "machine", "close"), "event kind")
        extra = ("phase", "start", "end") if kind == "operator" else (
            ("start", "end") if kind == "machine" else ("at", "outcome"))
        fields(row, ("id", "assignment_id", "kind", "note") + extra, "event")
        nonempty(row["id"], "event id")
        nonempty(row["assignment_id"], "event assignment_id")
        nonempty(row["note"], "event note")
        require(row["id"] not in ids, "duplicate event id")
        ids.add(row["id"])
        aid = row["assignment_id"]
        require(aid in assignments, "orphan event assignment")
        record = records[aid]
        if kind == "close":
            require(record["close"] is None, "duplicate close event")
            at = timestamp(row["at"], "close at")
            require(at >= frozen, "close precedes freeze")
            choice(row["outcome"], ("submitted", "unsuccessful", "not_attempted"), "outcome")
            record["close"] = (at, row["outcome"])
            continue
        start, end = timestamp(row["start"], "interval start"), timestamp(row["end"], "interval end")
        require(frozen <= start <= end, "negative interval or activity before freeze")
        minutes = (end - start).total_seconds() / 60
        record["interval_ends"].append(end)
        if kind == "machine":
            record["machine"] += minutes
            record["machine_count"] += 1
        else:
            choice(row["phase"], PHASES, "operator phase")
            record["phases"].add(row["phase"])
            record["operator"][row["phase"]] += minutes
            if start < end:
                operator_intervals[assignments[aid]["operator"]].append((start, end))

    for operator, intervals in operator_intervals.items():
        intervals.sort()
        for previous, following in zip(intervals, intervals[1:]):
            require(previous[1] <= following[0], f"overlapping operator effort: {operator}")

    for aid, record in records.items():
        require(record["phases"] == set(PHASES), f"{aid}: missing explicit operator phase evidence")
        require(record["machine_count"] > 0, f"{aid}: missing explicit machine evidence")
        require(record["close"] is not None, f"{aid}: missing close event")
        require(all(end <= record["close"][0] for end in record["interval_ends"]),
                f"{aid}: activity after close")
        if record["close"][1] == "not_attempted":
            require(sum(record["operator"].values()) + record["machine"] == 0,
                    f"{aid}: not_attempted contradicts recorded effort")

    operators = {row["operator"] for row in assignments.values()}
    graded = {}
    for row in grades:
        fields(row, ("assignment_id", "grader", "at", "correct", "traceable", "evidence", "rationale"),
               "grade")
        for key in ("assignment_id", "grader", "evidence", "rationale"):
            nonempty(row[key], f"grade {key}")
        aid = row["assignment_id"]
        require(aid in assignments, "orphan grade assignment")
        require(aid not in graded, "duplicate assignment grade")
        require(row["grader"] not in operators, "grader must be independent of all study operators")
        require(type(row["correct"]) is bool and type(row["traceable"]) is bool,
                "grade judgments must be booleans")
        require(timestamp(row["at"], "grade at") >= records[aid]["close"][0], "grade precedes close")
        require(records[aid]["close"][1] == "submitted" or not row["correct"],
                "noncompletion cannot receive correct grade")
        graded[aid] = row
    require(set(graded) == set(assignments), "missing independent assignment grades")
    return assignments, records, graded, blockers


def summarize(assignments, records, grades):
    metrics = {}
    for workflow in WORKFLOWS:
        metrics[workflow] = {}
        for period in ("setup", "repeat"):
            selected = [aid for aid, row in assignments.items()
                        if row["workflow"] == workflow and row["period"] == period]
            count = len(selected)
            submitted = sum(records[aid]["close"][1] == "submitted" for aid in selected)
            correct = sum(grades[aid]["correct"] and grades[aid]["traceable"] for aid in selected)
            phases = {phase: sum(records[aid]["operator"][phase] for aid in selected) for phase in PHASES}
            metrics[workflow][period] = {
                "assigned": count, "submitted": submitted, "correct_traceable": correct,
                "errors": count - correct, "completion_rate": submitted / count if count else None,
                "correct_traceable_rate": correct / count if count else None,
                "error_rate": (count - correct) / count if count else None,
                "operator_minutes": sum(phases.values()), "phase_minutes": phases,
                "machine_minutes": sum(records[aid]["machine"] for aid in selected),
            }
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("assignments", "events", "grades"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = {"validation": "invalid", "readiness": "blocked", "operational_value": "UNASSESSED",
              "input_sha256": {}, "metrics": None, "errors": [], "blockers": []}
    code = 2
    try:
        manifest = load(args.assignments, False, result["input_sha256"], "assignments")
        events = load(args.events, True, result["input_sha256"], "events")
        grades = load(args.grades, True, result["input_sha256"], "grades")
        assignments, records, graded, blockers = validate(manifest, events, grades)
        result.update(validation="valid", study_id=manifest["study_id"], blockers=blockers,
                      readiness="blocked" if blockers else "requires_source_review",
                      metrics=summarize(assignments, records, graded))
        code = 3 if blockers else 0
    except (OSError, UnicodeError, ValueError) as exc:
        result["errors"].append(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
