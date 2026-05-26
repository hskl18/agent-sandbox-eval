# Security

Agent Sandbox Eval runs agent-generated commands and benchmark code. Treat tasks, agents, and task workspaces as untrusted.

## Supported Safety Defaults

- Tasks run in Docker, not directly on the host.
- Network access is disabled by default.
- Only the task workspace is mounted into the container.
- Host credentials and home directories are not mounted by default.
- Task manifests define time, memory, and CPU limits.

Docker isolation is not a perfect security boundary for hostile code. Do not run untrusted tasks or agents with host mounts, credentials, or unrestricted network access.

## Reporting Issues

For now, report security issues by opening a private communication channel with the repository maintainer before publishing exploit details. Once the project is hosted publicly, this file should be updated with a dedicated reporting address.

