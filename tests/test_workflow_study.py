"""Synthetic log contracts, never observations of operator performance."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "workflow_study.py"
REQUIREMENTS = (
    "accuracy", "turnaround", "practical_improvement", "authorized_users",
    "task_rubric", "counterbalancing", "sample_design", "independent_grading",
    "holdout", "final_plan",
)
PHASES = ("preparation", "execution", "verification", "correction", "unsuccessful_attempts")


def synthetic_logs():
    manifest = {
        "schema_version": 1, "study_id": "synthetic-contract-test",
        "frozen_at": "2025-12-31T00:00:00Z",
        "requirements": dict.fromkeys(REQUIREMENTS),
        "development_consumed": ["A", "B", "v1", "v2"], "assignments": [],
    }
    events, grades = [], []
    # Hand-check: baseline repeat = 3 assigned, 1 delivered, 1 correct,
    # 10 operator minutes, 2.5 machine minutes. Setup = 10 operator minutes.
    specs = [
        ("b1", "baseline", "repeat", "eligible", "submitted", 60, 120, True),
        ("b2", "baseline", "repeat", "blocked", "unsuccessful", 60, 30, False),
        ("b3", "baseline", "repeat", "missing_cost", "not_attempted", 0, 0, False),
        ("p1", "corrected_pack", "repeat", "zero_cost", "submitted", 30, 60, True),
        ("s1", "baseline", "setup", "malformed", "submitted", 120, 600, True),
    ]
    for index, (aid, workflow, period, category, outcome, seconds, machine, correct) in enumerate(specs):
        assignment = {
            "id": aid, "task_id": "task-" + aid, "fixture_id": "synthetic-" + aid,
            "task_class": category, "workflow": workflow, "operator": "operator-1",
            "period": period, "evidence_status": "holdout",
        }
        manifest["assignments"].append(assignment)
        start = datetime(2026, 1, 1, index, tzinfo=timezone.utc)
        cursor = start
        for phase in PHASES:
            end = cursor + timedelta(seconds=seconds)
            events.append({"id": aid + "-" + phase, "assignment_id": aid,
                           "kind": "operator", "phase": phase,
                           "start": cursor.isoformat(), "end": end.isoformat(),
                           "note": "Synthetic interval; zero means explicitly no activity"})
            cursor = end
        end = cursor + timedelta(seconds=machine)
        events.append({"id": aid + "-machine", "assignment_id": aid,
                       "kind": "machine", "start": cursor.isoformat(),
                       "end": end.isoformat(), "note": "Synthetic machine interval"})
        events.append({"id": aid + "-close", "assignment_id": aid, "kind": "close",
                       "at": end.isoformat(), "outcome": outcome, "note": "Synthetic closure"})
        grades.append({"assignment_id": aid, "grader": "independent-grader",
                       "at": (end + timedelta(seconds=1)).isoformat(),
                       "correct": correct, "traceable": correct,
                       "evidence": "synthetic-evidence/" + aid,
                       "rationale": "Synthetic rubric judgment, not a human study"})
    return manifest, events, grades


class WorkflowStudyTests(unittest.TestCase):
    def run_tool(self, manifest=None, events=None, grades=None, raw=None):
        default_manifest, default_events, default_grades = synthetic_logs()
        values = [manifest if manifest is not None else default_manifest,
                  events if events is not None else default_events,
                  grades if grades is not None else default_grades]
        with tempfile.TemporaryDirectory() as tmp:
            paths = [Path(tmp) / name for name in ("assignments.json", "events.jsonl", "grades.jsonl")]
            for index, (path, value) in enumerate(zip(paths, values)):
                content = json.dumps(value) if index == 0 else "".join(json.dumps(row) + "\n" for row in value)
                path.write_text((raw or {}).get(index, content))
            before = [path.read_bytes() for path in paths]
            proc = subprocess.run([sys.executable, str(TOOL), "--assignments", str(paths[0]),
                                   "--events", str(paths[1]), "--grades", str(paths[2])],
                                  capture_output=True, text=True, cwd=ROOT)
            self.assertEqual([path.read_bytes() for path in paths], before)
            self.assertEqual(proc.stderr, "", proc.stderr)
            self.assertIn(proc.returncode, (0, 2, 3))
            self.assertTrue(proc.stdout.strip(), "CLI must emit a reviewable JSON result")
            return proc.returncode, json.loads(proc.stdout), before

    def assert_invalid(self, manifest=None, events=None, grades=None, raw=None):
        code, result, _ = self.run_tool(manifest, events, grades, raw)
        self.assertEqual(code, 2, result)
        self.assertEqual(result["validation"], "invalid")
        self.assertEqual(result["operational_value"], "UNASSESSED")
        self.assertIsNone(result["metrics"])
        self.assertTrue(result["errors"])

    def test_all_assignments_and_all_effort_count_with_setup_and_machine_separate(self):
        code, result, before = self.run_tool()
        self.assertEqual(code, 3)
        self.assertEqual(result["validation"], "valid")
        self.assertEqual(result["readiness"], "blocked")
        self.assertEqual(result["operational_value"], "UNASSESSED")
        self.assertEqual(len(result["blockers"]), 10)
        baseline = result["metrics"]["baseline"]["repeat"]
        self.assertEqual(baseline["assigned"], 3)
        self.assertEqual(baseline["submitted"], 1)
        self.assertEqual(baseline["correct_traceable"], 1)
        self.assertEqual(baseline["errors"], 2)
        self.assertAlmostEqual(baseline["completion_rate"], 1 / 3)
        self.assertAlmostEqual(baseline["correct_traceable_rate"], 1 / 3)
        self.assertAlmostEqual(baseline["error_rate"], 2 / 3)
        self.assertEqual(baseline["operator_minutes"], 10)
        self.assertEqual(baseline["phase_minutes"], dict.fromkeys(PHASES, 2))
        self.assertEqual(baseline["machine_minutes"], 2.5)
        self.assertEqual(result["metrics"]["baseline"]["setup"]["operator_minutes"], 10)
        self.assertEqual(result["metrics"]["corrected_pack"]["repeat"]["operator_minutes"], 2.5)
        self.assertIsNone(result["metrics"]["corrected_pack"]["setup"]["completion_rate"])
        self.assertEqual(result["input_sha256"], {
            name: hashlib.sha256(data).hexdigest()
            for name, data in zip(("assignments", "events", "grades"), before)
        })

    def test_receipt_presence_requires_source_review_and_never_certifies_success(self):
        manifest, _, _ = synthetic_logs()
        manifest["requirements"] = {key: {"source": "synthetic-not-real-approval", "sha256": "a" * 64}
                                    for key in REQUIREMENTS}
        code, result, _ = self.run_tool(manifest=manifest)
        self.assertEqual(code, 0)
        self.assertEqual(result["readiness"], "requires_source_review")
        self.assertEqual(result["operational_value"], "UNASSESSED")

    def test_inspected_corrected_baseline_and_optional_manual_control_stay_separate(self):
        manifest, _, _ = synthetic_logs()
        manifest["assignments"][1]["workflow"] = "inspected_pack"
        manifest["assignments"][2]["workflow"] = "manual_control"
        _, result, _ = self.run_tool(manifest=manifest)
        metrics = result["metrics"]
        self.assertEqual(metrics["baseline"]["repeat"]["operator_minutes"], 5)
        self.assertEqual(metrics["inspected_pack"]["repeat"]["operator_minutes"], 5)
        self.assertEqual(metrics["corrected_pack"]["repeat"]["operator_minutes"], 2.5)
        self.assertEqual(metrics["manual_control"]["repeat"]["assigned"], 1)
        self.assertEqual(metrics["manual_control"]["repeat"]["errors"], 1)

    def test_submitted_wrong_or_untraceable_work_is_an_error(self):
        _, _, grades = synthetic_logs()
        for field in ("correct", "traceable"):
            changed = copy.deepcopy(grades)
            changed[0][field] = False
            with self.subTest(field=field):
                _, result, _ = self.run_tool(grades=changed)
                self.assertEqual(result["metrics"]["baseline"]["repeat"]["submitted"], 1)
                self.assertEqual(result["metrics"]["baseline"]["repeat"]["errors"], 3)

    def test_missing_assignment_evidence_never_becomes_zero_or_success(self):
        manifest, events, grades = synthetic_logs()
        variants = [
            (manifest, events[1:], grades),
            (manifest, [e for e in events if e["id"] != "b1-machine"], grades),
            (manifest, [e for e in events if e["id"] != "b1-close"], grades),
            (manifest, events, grades[1:]),
            (dict(manifest, assignments=[]), [], []),
        ]
        for values in variants:
            with self.subTest(event_count=len(values[1]), grade_count=len(values[2])):
                self.assert_invalid(*values)

    def test_duplicate_and_orphan_records_fail_closed(self):
        manifest, events, grades = synthetic_logs()
        extra = dict(events[0], id="orphan", assignment_id="unassigned")
        variants = [
            (dict(manifest, assignments=manifest["assignments"] + [manifest["assignments"][0]]), events, grades),
            (manifest, events + [events[0]], grades),
            (manifest, events + [dict(events[-1], id="second-close")], grades),
            (manifest, events + [extra], grades),
            (manifest, events, grades + [grades[0]]),
            (manifest, events, grades + [dict(grades[0], assignment_id="unassigned")]),
        ]
        for values in variants:
            with self.subTest(events=len(values[1]), grades=len(values[2])):
                self.assert_invalid(*values)

    def test_self_grading_and_contradictory_noncompletion_fail_closed(self):
        _, events, grades = synthetic_logs()
        variants = []
        self_grade = copy.deepcopy(grades)
        self_grade[0]["grader"] = "operator-1"
        variants.append((events, self_grade))
        false_success = copy.deepcopy(grades)
        false_success[1]["correct"] = True
        variants.append((events, false_success))
        not_attempted = copy.deepcopy(events)
        not_attempted[6]["outcome"] = "not_attempted"
        variants.append((not_attempted, grades))
        for event_rows, grade_rows in variants:
            with self.subTest(grader=grade_rows[0]["grader"]):
                self.assert_invalid(events=event_rows, grades=grade_rows)

    def test_invalid_chronology_and_overlapping_operator_effort_fail_closed(self):
        manifest, events, grades = synthetic_logs()
        variants = []
        for key, value in (("end", "2025-01-01T00:00:00Z"),
                           ("start", "2026-01-01T00:00:00"),
                           ("end", "2026-01-02T00:00:00Z")):
            changed = copy.deepcopy(events)
            changed[0][key] = value
            variants.append((manifest, changed, grades))
        overlap = copy.deepcopy(events)
        overlap[1]["start"] = overlap[0]["start"]
        variants.append((manifest, overlap, grades))
        variants.append((dict(manifest, frozen_at="2027-01-01T00:00:00Z"), events, grades))
        early_grade = copy.deepcopy(grades)
        early_grade[0]["at"] = "2025-01-01T00:00:00Z"
        variants.append((manifest, events, early_grade))
        for values in variants:
            with self.subTest(event=values[1][0]):
                self.assert_invalid(*values)

    def test_declared_consumed_identities_cannot_be_holdout_or_removed(self):
        manifest, _, _ = synthetic_logs()
        for fixture_id in ("A", "B", "v1", "v2"):
            changed = copy.deepcopy(manifest)
            changed["assignments"][0]["fixture_id"] = fixture_id
            with self.subTest(fixture_id=fixture_id):
                self.assert_invalid(manifest=changed)
        self.assert_invalid(manifest=dict(manifest, development_consumed=["A", "B", "v2"]))
        manifest["assignments"][0]["evidence_status"] = "development"
        code, result, _ = self.run_tool(manifest=manifest)
        self.assertEqual(code, 3)
        self.assertTrue(any("development" in blocker for blocker in result["blockers"]))

    def test_malformed_json_types_unknown_fields_and_duplicate_keys_fail_closed(self):
        manifest, events, grades = synthetic_logs()
        bad_manifest = copy.deepcopy(manifest)
        bad_manifest["requirements"]["accuracy"] = {"source": "no digest"}
        bad_grade = copy.deepcopy(grades)
        bad_grade[0]["correct"] = "true"
        bad_event = copy.deepcopy(events)
        bad_event[0]["duration"] = 0
        for args in ({"manifest": []}, {"manifest": bad_manifest}, {"grades": bad_grade},
                     {"events": bad_event}, {"raw": {0: '{"schema_version":1,"schema_version":1}'}},
                     {"raw": {1: '{"id": NaN}\n'}}, {"raw": {2: 'not json\n'}},
                     {"events": [None]}, {"grades": [{}]}):
            with self.subTest(args=args):
                self.assert_invalid(**args)

    def test_missing_input_files_emit_invalid_result_without_traceback(self):
        proc = subprocess.run([sys.executable, str(TOOL), "--assignments", "/nonexistent/assignments.json",
                               "--events", "/nonexistent/events.jsonl", "--grades", "/nonexistent/grades.jsonl"],
                              capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stderr, "")
        result = json.loads(proc.stdout)
        self.assertIsNone(result["metrics"])
        self.assertEqual(result["validation"], "invalid")


if __name__ == "__main__":
    unittest.main()
