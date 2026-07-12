from __future__ import annotations

import json
from pathlib import Path


def test_published_harness_baseline_keeps_controls_separate() -> None:
    manifest = json.loads(Path("results/v1/manifest.json").read_text(encoding="utf-8"))
    runs = {run["label"]: run for run in manifest["runs"]}

    assert manifest["schemaVersion"] == "1.0"
    assert manifest["liveModelResults"] is None
    assert len(manifest["taskPackCommit"]) == 40
    assert set(runs) == {"scripted", "react-local-solution", "noop"}
    assert all(run["agent_capability_result"] is False for run in runs.values())
    assert all(run["modelCalls"] == 0 for run in runs.values())
    assert runs["scripted"]["passed"] == 25
    assert runs["react-local-solution"]["passed"] == 25
    assert runs["noop"]["passed"] == 0
    assert runs["noop"]["failureModes"] == {"no_progress": 25}


def test_published_trajectories_have_complete_task_outcomes() -> None:
    for name in ["scripted-oracle", "react-local-solution", "noop-negative-control"]:
        path = Path(f"results/v1/{name}.jsonl")
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        grader_events = [event for event in events if event["event_type"] == "grader_result"]
        run_end = [event for event in events if event["event_type"] == "run_end"]

        assert len(grader_events) == 25
        assert len(run_end) == 1
        assert run_end[0]["total_tasks"] == 25
