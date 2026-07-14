from importlib.metadata import PackageNotFoundError, version


TASK_SCHEMA_VERSION = 1
TRAJECTORY_SCHEMA_VERSION = 1
EXPERIMENT_SCHEMA_VERSION = 1
EXPERIMENT_REPORT_SCHEMA_VERSION = 1
BENCHMARK_SPLIT_SCHEMA_VERSION = 1


def package_version() -> str:
    try:
        return version("agent-sandbox-eval")
    except PackageNotFoundError:
        return "unknown"
