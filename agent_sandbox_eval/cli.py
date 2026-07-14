from __future__ import annotations

import argparse
from pathlib import Path
from typing import cast

from agent_sandbox_eval.agents.registry import get_agent
from agent_sandbox_eval.benchmarks.lint import lint_task, probe_task_baseline
from agent_sandbox_eval.benchmarks.loader import load_benchmark, load_task
from agent_sandbox_eval.benchmarks.loader import benchmark_roots, discover_task_files_many
from agent_sandbox_eval.benchmarks.splits import apply_split, discover_splits, load_split
from agent_sandbox_eval.experiments.runner import regenerate_matrix_reports, run_matrix
from agent_sandbox_eval.experiments.schema import load_experiment
from agent_sandbox_eval.extensions import (
    AGENT_ENTRY_POINT_GROUP,
    PROVIDER_ENTRY_POINT_GROUP,
    TOOL_ENTRY_POINT_GROUP,
    TASK_PACK_ENTRY_POINT_GROUP,
    list_all_entry_points,
    load_entry_point,
)
from agent_sandbox_eval.reports.markdown import write_comparison_report, write_markdown_report
from agent_sandbox_eval.runner import Runner
from agent_sandbox_eval.runner import ToolFactory
from agent_sandbox_eval.trajectories.replay import replay_trajectory
from agent_sandbox_eval.version import package_version


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ase", description="Agent Sandbox Eval CLI")
    parser.add_argument("--version", action="version", version=f"%(prog)s {package_version()}")
    parser.add_argument("--benchmarks-root", default="benchmarks", help="Benchmark task root directory.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    list_tasks = subcommands.add_parser("list-tasks", help="List available benchmark tasks.")
    list_tasks.add_argument("--benchmark", help="Benchmark name to filter by.")

    validate = subcommands.add_parser("validate-task", help="Validate a task manifest.")
    validate.add_argument("task", help="Path to task.yaml.")

    validate_tasks = subcommands.add_parser("validate-tasks", help="Validate benchmark task manifests.")
    validate_tasks.add_argument("--benchmark", default="all", help="Benchmark name or all.")

    lint = subcommands.add_parser("lint-task", help="Lint a task manifest for authoring weaknesses.")
    lint.add_argument("task", help="Path to task.yaml.")
    lint.add_argument("--probe-setup", action="store_true", help="Probe the baseline grader in Docker.")
    lint.add_argument("--image", default="python:3.13-slim", help="Docker image for the baseline probe.")

    lint_tasks = subcommands.add_parser("lint-tasks", help="Lint benchmark task manifests.")
    lint_tasks.add_argument("--benchmark", default="all", help="Benchmark name or all.")
    lint_tasks.add_argument("--probe-setup", action="store_true", help="Probe baseline graders in Docker.")
    lint_tasks.add_argument("--image", default="python:3.13-slim", help="Docker image for baseline probes.")

    subcommands.add_parser("list-splits", help="List versioned benchmark splits.")

    run = subcommands.add_parser("run", help="Run tasks and write trajectory JSONL.")
    run.add_argument("--agent", default="noop", choices=["noop", "scripted", "react", "planner"])
    run.add_argument("--provider", default="local-solution", choices=["local-solution", "openai-responses"])
    run.add_argument("--benchmark", default="terminal")
    run.add_argument("--task-id", help="Run one task by id.")
    run.add_argument("--out", default="runs/run.jsonl")
    run.add_argument("--image", default="python:3.13-slim", help="Docker image for sandbox execution.")
    run.add_argument("--keep-workspaces", action="store_true")

    run_matrix_parser = subcommands.add_parser(
        "run-matrix", help="Run or resume a versioned repeated-trial experiment."
    )
    run_matrix_parser.add_argument("experiment", help="Path to an experiment YAML file.")

    matrix_report = subcommands.add_parser(
        "matrix-report", help="Validate raw matrix artifacts and regenerate JSON and Markdown reports."
    )
    matrix_report.add_argument("experiment", help="Path to the experiment YAML used for the run.")

    replay = subcommands.add_parser("replay", help="Replay a trajectory JSONL file.")
    replay.add_argument("trajectory")
    replay.add_argument("--task", dest="task_id", help="Only replay one task id.")

    report = subcommands.add_parser("report", help="Generate a Markdown report from trajectory JSONL.")
    report.add_argument("trajectory")
    report.add_argument("--out", default="reports/run.md")

    compare = subcommands.add_parser("compare", help="Compare multiple trajectory JSONL files.")
    compare.add_argument("trajectories", nargs="+")
    compare.add_argument("--out", default="reports/compare.md")

    subcommands.add_parser("list-extensions", help="List installed extension entry points.")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.benchmarks_root)

    if args.command == "list-tasks":
        benchmark_filter = None if args.benchmark == "all" else args.benchmark
        for path in discover_task_files_many(benchmark_roots(root), benchmark_filter):
            task = load_task(path)
            print(f"{task.id}\t{task.benchmark}\t{task.title}")
        return

    if args.command == "validate-task":
        task = load_task(Path(args.task))
        print(f"valid\t{task.id}\t{task.title}")
        return

    if args.command == "validate-tasks":
        benchmark_filter = None if args.benchmark == "all" else args.benchmark
        paths = discover_task_files_many(benchmark_roots(root), benchmark_filter)
        if not paths:
            raise SystemExit(f"no task manifests found for benchmark: {args.benchmark}")
        count = 0
        for path in paths:
            task = load_task(path)
            count += 1
            print(f"valid\t{task.id}\t{task.benchmark}\t{task.title}")
        print(f"validated {count} task manifests")
        return

    if args.command in {"lint-task", "lint-tasks"}:
        if args.command == "lint-task":
            paths = [Path(args.task)]
        else:
            benchmark_filter = None if args.benchmark == "all" else args.benchmark
            paths = discover_task_files_many(benchmark_roots(root), benchmark_filter)
            if not paths:
                raise SystemExit(f"no task manifests found for benchmark: {args.benchmark}")
        issue_count = 0
        for path in paths:
            task = load_task(path)
            issues = lint_task(task)
            if args.probe_setup:
                issues.extend(probe_task_baseline(task, docker_image=args.image))
            if not issues:
                print(f"clean\t{task.id}\t{task.benchmark}\t{task.title}")
                continue
            for issue in issues:
                issue_count += 1
                print(f"{issue.severity}\t{issue.code}\t{task.id}\t{issue.message}")
        if issue_count:
            raise SystemExit(f"task lint failed with {issue_count} issue(s)")
        print(f"linted {len(paths)} task manifests")
        return

    if args.command == "list-splits":
        for path in discover_splits(root):
            split = load_split(path.stem, root)
            print(f"{split.id}\t{split.benchmark}\t{path}")
        return

    if args.command in {"run-matrix", "matrix-report"}:
        spec = load_experiment(Path(args.experiment))
        tasks = load_benchmark(spec.benchmark.name, root)
        tasks = apply_split(tasks, load_split(spec.benchmark.split, root))
        if args.command == "run-matrix":
            result = run_matrix(spec, tasks)
        else:
            result = regenerate_matrix_reports(spec, tasks)
        print(
            f"units={result.scheduled_units} resumed={result.resumed_units} "
            f"attempts={result.executed_attempts} summary={result.summary_path} report={result.report_path}"
        )
        return

    if args.command == "run":
        tasks = load_benchmark(args.benchmark, root)
        if args.task_id:
            tasks = [task for task in tasks if task.id == args.task_id]
            if not tasks:
                raise SystemExit(f"task id not found: {args.task_id}")
        agent = get_agent(args.agent, provider_name=args.provider)
        extra_tool_factories: dict[str, ToolFactory] = {}
        for entry_point in list_all_entry_points()[TOOL_ENTRY_POINT_GROUP]:
            factory = load_entry_point(TOOL_ENTRY_POINT_GROUP, entry_point.name)
            if factory is not None:
                extra_tool_factories[entry_point.name] = cast(ToolFactory, factory)
        runner = Runner(
            agent=agent,
            output_path=Path(args.out),
            docker_image=args.image,
            keep_workspaces=args.keep_workspaces,
            extra_tool_factories=extra_tool_factories,
        )
        summary = runner.run(tasks)
        print(
            f"tasks={summary.total_tasks} passed={summary.passed_tasks} "
            f"pass_rate={summary.pass_rate:.1%} out={args.out}"
        )
        return

    if args.command == "replay":
        print(replay_trajectory(Path(args.trajectory), task_id=args.task_id))
        return

    if args.command == "report":
        report_path = write_markdown_report(Path(args.trajectory), Path(args.out))
        print(f"wrote {report_path}")
        return

    if args.command == "compare":
        report_path = write_comparison_report([Path(path) for path in args.trajectories], Path(args.out))
        print(f"wrote {report_path}")
        return

    if args.command == "list-extensions":
        groups = list_all_entry_points()
        builtin_agents = ["noop", "scripted", "react", "planner"]
        builtin_providers = ["local-solution", "openai-responses"]
        builtin_tools = ["shell", "file_read", "file_write", "python", "mcp_state"]
        print("builtin agents:\t" + ", ".join(builtin_agents))
        print("builtin providers:\t" + ", ".join(builtin_providers))
        print("builtin tools:\t" + ", ".join(builtin_tools))
        for group in [AGENT_ENTRY_POINT_GROUP, PROVIDER_ENTRY_POINT_GROUP, TOOL_ENTRY_POINT_GROUP, TASK_PACK_ENTRY_POINT_GROUP]:
            print(group + ":")
            for entry_point in groups[group]:
                print(f"  {entry_point.name}\t{entry_point.value}")
        return

    parser.error(f"unknown command: {args.command}")
