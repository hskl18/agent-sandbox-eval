# Research and Optimization Notes

This project is a local-first agent evaluation harness, so the closest references are execution-based agent benchmarks rather than static answer-only evals.

## External Signals

- [SWE-bench](https://github.com/SWE-bench/SWE-bench) uses Docker for reproducible software-engineering evaluations, stores run logs and final evaluation results, and explicitly documents machine resource expectations. Agent Sandbox Eval should keep Docker behavior reproducible, make run artifacts easy to inspect, and avoid hiding resource assumptions.
- [AgentBench](https://arxiv.org/abs/2308.03688) emphasizes multi-turn interaction across diverse environments, with failure analysis focused on reasoning, decision-making, and instruction-following gaps. Agent Sandbox Eval should preserve complete trajectories and make tool observations visible to providers and reports.
- [tau-bench](https://arxiv.org/abs/2406.12045) grades final environment state against annotated goals and reports pass^k to expose reliability across repeated trials. Agent Sandbox Eval should keep adding state-based graders and should add repeated-run reliability reporting before claiming model-level comparisons.
- [OSWorld](https://arxiv.org/abs/2404.07972) uses task setup plus custom execution-based evaluation scripts for reproducible real-computer tasks. Agent Sandbox Eval should treat setup failures separately from agent failures and keep graders deterministic.
- [OpenAI Evals](https://github.com/openai/evals) separates eval definitions, sample data, runners, and completion/model interfaces. Agent Sandbox Eval should preserve clear extension boundaries for tasks, tools, agents, and providers.

## Optimizations Applied

- Added `json_fields` success criteria so tasks can grade final JSON state directly instead of embedding every state assertion inside shell commands.
- Enforced `allowed_tools` at runner time so each task exposes only the declared agent tool surface.
- Added manifest validation that rejects bundled scripted solutions referencing tools outside `allowed_tools`.
- Stopped task execution on setup failure and records `environment_setup_failure` as a first-class result.
- Fixed the `scripted` agent so MCP-only tasks do not require the shell tool.

## Next High-Value Optimizations

- Add a repeated-run command or report mode for pass^k-style reliability metrics.
- Add task authoring checks for reward-hackable graders, for example missing negative assertions, success commands that do not inspect expected output, or solution metadata that bypasses the intended tool surface.
- Add optional Docker image preflight and resource diagnostics so failures distinguish daemon/image/resource problems from agent behavior.
- Add benchmark splits such as `smoke`, `dev`, and `full` once the task set grows beyond the bundled 25 tasks.
- Add report export as structured JSON alongside Markdown for downstream analysis.
