# Trajectory Schema

Trajectories are JSONL files.
Each line is one event.

Common fields:

- `schema_version`: trajectory event schema version. Current value: `1`.
- `run_id`
- `task_id`
- `step_index`
- `event_type`
- `timestamp`

Required event types:

- `run_start`
- `task_start`
- `agent_message`
- `tool_call`
- `tool_result`
- `grader_result`
- `task_end`
- `run_end`

Experiment attempts append an `attempt_result` event after the complete run boundary or after the last valid partial event.
This event binds the attempt marker's reportable outcome, failure classification, retry decision, latency, token usage, cost, pricing source, and error text to the hashed raw trajectory.

The schema is intentionally append-only so long benchmark runs can stream to disk.

Tool observations are represented by `tool_result` events and are also fed back into observation-aware providers during agent execution.
