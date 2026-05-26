# Sandbox Model

The sandbox is responsible for reproducible execution and safety defaults.

Current behavior:

- Copies each task workspace into a temporary directory.
- Mounts only that workspace into Docker at `/workspace`.
- Runs commands with `/workspace` as the working directory.
- Disables network access unless the task enables it.
- Applies memory and CPU limits through Docker flags.
- Deletes temporary workspaces by default.

Docker must be running for benchmark execution.

