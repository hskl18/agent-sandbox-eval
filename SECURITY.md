# Security

Agent Sandbox Eval runs agent-generated commands and benchmark code. Treat tasks, agents, and task workspaces as untrusted.

## Supported Safety Defaults

- Tasks run in Docker, not directly on the host.
- Network access is disabled by default.
- Only the task workspace is mounted into the container.
- Host credentials and home directories are not mounted by default.
- The container runs as the host user with all Linux capabilities dropped.
- `no-new-privileges` prevents setuid and file-capability privilege gains.
- The container root filesystem is read-only.
- For reviewed images without declared volumes, only `/workspace` and a constrained `/tmp` tmpfs are writable by sandboxed commands.
- Task manifests define time, memory, CPU, and process-count limits.
- Docker's built-in seccomp profile is requested explicitly.

These controls reduce common privilege-escalation, fork-bomb, and filesystem-write risks.
They do not make Docker a perfect security boundary and do not prove containment against container-runtime or kernel vulnerabilities.
The task workspace remains writable and its contents must be treated as attacker-controlled after execution.
Network-enabled tasks can still send data available inside their containers to remote systems.
Do not run hostile tasks with credentials, Docker sockets, sensitive host mounts, privileged mode, host namespaces, or unrestricted network access.
Do not use unreviewed container images because image-declared `VOLUME` paths can introduce additional writable anonymous volumes.

This project uses Docker's portable built-in seccomp profile rather than shipping a custom syscall policy.
The effective policy therefore depends on the Docker Engine and host platform.
Operators handling genuinely adversarial code should add a stronger isolation layer such as a dedicated VM or microVM and should keep Docker and the host kernel patched.

## Reporting Issues

Report vulnerabilities through [GitHub private vulnerability reporting](https://github.com/hskl18/agent-sandbox-eval/security/advisories/new).
Do not publish exploit details until the maintainer has acknowledged and addressed the report.
