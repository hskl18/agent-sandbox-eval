# Sandbox Model

The sandbox is responsible for reproducible execution and safety defaults.

Current behavior:

- Copies each task workspace into a temporary directory.
- Mounts only that workspace into Docker at `/workspace` as an explicit writable bind mount.
- Runs commands with `/workspace` as the working directory.
- Disables network access unless the task enables it.
- Applies memory, CPU, and process-count limits through Docker flags.
- Runs as the host user and drops all Linux capabilities.
- Sets `no-new-privileges` so container processes cannot gain privileges through setuid or file capabilities.
- Mounts the container root filesystem read-only.
- Provides `/tmp` as a 64 MiB writable tmpfs with `nosuid`, `nodev`, and `noexec` mount options.
- Requests Docker's built-in seccomp profile instead of maintaining a host-specific custom profile.
- Uses Docker's init process to reap child processes inside the PID limit.
- Deletes temporary workspaces by default.

Docker must be running for benchmark execution.

The default PID limit is 256 and can be lowered per task with `limits.pids_limit`.
The PID limit must be between 1 and 256, so a task manifest cannot raise the sandbox maximum.

The `seccomp=builtin` setting requires a current Docker Engine that supports the built-in profile name.
Using Docker's maintained profile avoids coupling the benchmark harness to a kernel-specific syscall list.
It does not guarantee that every syscall reachable through the profile is safe for every workload or host kernel.

The writable workspace is intentionally persistent for the lifetime of a task because agents must edit benchmark files.
Do not place credentials, Docker sockets, host source trees, or other sensitive files in task workspaces.
