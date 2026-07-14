from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agent_sandbox_eval.version import EXPERIMENT_SCHEMA_VERSION


@dataclass(frozen=True)
class PricingSpec:
    source: str
    input_per_million_usd: float
    output_per_million_usd: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PricingSpec":
        source = str(data.get("source", "")).strip()
        if not source:
            raise ValueError("model.pricing.source is required when pricing is configured")
        input_rate = float(data.get("input_per_million_usd", -1))
        output_rate = float(data.get("output_per_million_usd", -1))
        if input_rate < 0 or output_rate < 0:
            raise ValueError("model pricing rates must be nonnegative")
        return cls(source, input_rate, output_rate)

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "input_per_million_usd": self.input_per_million_usd,
            "output_per_million_usd": self.output_per_million_usd,
        }


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)
    pricing: PricingSpec | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelSpec":
        provider = _required_string(data, "provider", "matrix.model")
        name = _required_string(data, "name", "matrix.model")
        metadata = _mapping(data.get("metadata"), "matrix.model.metadata")
        pricing_data = data.get("pricing")
        if pricing_data is not None and not isinstance(pricing_data, dict):
            raise ValueError("matrix.model.pricing must be a mapping or null")
        return cls(
            provider=provider,
            name=name,
            metadata=metadata,
            pricing=PricingSpec.from_dict(pricing_data) if pricing_data is not None else None,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "name": self.name,
            "metadata": self.metadata,
            "pricing": self.pricing.to_dict() if self.pricing else None,
        }


@dataclass(frozen=True)
class AgentSpec:
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentSpec":
        return cls(
            name=_required_string(data, "name", "matrix.agent"),
            metadata=_mapping(data.get("metadata"), "matrix.agent.metadata"),
        )

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "metadata": self.metadata}


@dataclass(frozen=True)
class MatrixCell:
    id: str
    agent: AgentSpec
    model: ModelSpec

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MatrixCell":
        agent_data = _required_mapping(data, "agent", "matrix cell")
        model_data = _required_mapping(data, "model", "matrix cell")
        return cls(
            id=_required_string(data, "id", "matrix cell"),
            agent=AgentSpec.from_dict(agent_data),
            model=ModelSpec.from_dict(model_data),
        )

    def to_dict(self) -> dict[str, object]:
        return {"id": self.id, "agent": self.agent.to_dict(), "model": self.model.to_dict()}


@dataclass(frozen=True)
class BenchmarkSpec:
    name: str
    split: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BenchmarkSpec":
        return cls(
            name=_required_string(data, "name", "benchmark"),
            split=_required_string(data, "split", "benchmark"),
        )

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "split": self.split}


@dataclass(frozen=True)
class BudgetSpec:
    timeout_seconds: int | None = None
    max_tool_calls: int | None = None
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_estimated_cost_usd: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BudgetSpec":
        budget = cls(
            timeout_seconds=_optional_int(data, "timeout_seconds"),
            max_tool_calls=_optional_int(data, "max_tool_calls"),
            max_input_tokens=_optional_int(data, "max_input_tokens"),
            max_output_tokens=_optional_int(data, "max_output_tokens"),
            max_estimated_cost_usd=_optional_float(data, "max_estimated_cost_usd"),
        )
        for name in ["timeout_seconds", "max_tool_calls", "max_input_tokens", "max_output_tokens"]:
            value = getattr(budget, name)
            if value is not None and value <= 0:
                raise ValueError(f"budgets.{name} must be positive")
        if budget.max_estimated_cost_usd is not None and budget.max_estimated_cost_usd < 0:
            raise ValueError("budgets.max_estimated_cost_usd must be nonnegative")
        return budget

    def to_dict(self) -> dict[str, int | float | None]:
        return {
            "timeout_seconds": self.timeout_seconds,
            "max_tool_calls": self.max_tool_calls,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "max_estimated_cost_usd": self.max_estimated_cost_usd,
        }


@dataclass(frozen=True)
class RetrySpec:
    max_attempts: int = 1
    on: list[str] = field(default_factory=lambda: ["environment_setup_failure", "runner_error"])

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RetrySpec":
        max_attempts = int(data.get("max_attempts", 1))
        if max_attempts <= 0 or max_attempts > 10:
            raise ValueError("retry.max_attempts must be between 1 and 10")
        on = _string_list(data.get("on", ["environment_setup_failure", "runner_error"]), "retry.on")
        return cls(max_attempts=max_attempts, on=on)

    def to_dict(self) -> dict[str, object]:
        return {"max_attempts": self.max_attempts, "on": self.on}


@dataclass(frozen=True)
class EnvironmentSpec:
    id: str
    docker_image: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnvironmentSpec":
        return cls(
            id=_required_string(data, "id", "environment"),
            docker_image=_required_string(data, "docker_image", "environment"),
            metadata=_mapping(data.get("metadata"), "environment.metadata"),
        )

    def to_dict(self) -> dict[str, object]:
        return {"id": self.id, "docker_image": self.docker_image, "metadata": self.metadata}


@dataclass(frozen=True)
class ArtifactSpec:
    root: Path
    raw_dir: str = "raw"
    summary_json: str = "summary.json"
    report_markdown: str = "report.md"
    normalize_timestamps: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any], config_path: Path) -> "ArtifactSpec":
        root_text = _required_string(data, "root", "artifacts")
        root = Path(root_text)
        if not root.is_absolute():
            root = (config_path.parent / root).resolve()
        raw_dir = str(data.get("raw_dir", "raw")).strip()
        summary_json = str(data.get("summary_json", "summary.json")).strip()
        report_markdown = str(data.get("report_markdown", "report.md")).strip()
        for name, value in {
            "raw_dir": raw_dir,
            "summary_json": summary_json,
            "report_markdown": report_markdown,
        }.items():
            path = Path(value)
            if not value or path.is_absolute() or ".." in path.parts:
                raise ValueError(f"artifacts.{name} must be a relative path within artifacts.root")
        return cls(
            root=root,
            raw_dir=raw_dir,
            summary_json=summary_json,
            report_markdown=report_markdown,
            normalize_timestamps=bool(data.get("normalize_timestamps", False)),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "root": str(self.root),
            "raw_dir": self.raw_dir,
            "summary_json": self.summary_json,
            "report_markdown": self.report_markdown,
            "normalize_timestamps": self.normalize_timestamps,
        }


@dataclass(frozen=True)
class ExperimentSpec:
    schema_version: int
    name: str
    seed: int
    trials: int
    concurrency: int
    benchmark: BenchmarkSpec
    budgets: BudgetSpec
    retry: RetrySpec
    environment: EnvironmentSpec
    artifacts: ArtifactSpec
    matrix: list[MatrixCell]
    config_path: Path

    @classmethod
    def from_dict(cls, data: dict[str, Any], config_path: Path) -> "ExperimentSpec":
        schema_version = int(data.get("schema_version", 0))
        if schema_version != EXPERIMENT_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported experiment schema_version {schema_version}; expected {EXPERIMENT_SCHEMA_VERSION}"
            )
        trials = int(data.get("trials", 0))
        concurrency = int(data.get("concurrency", 0))
        if trials <= 0 or trials > 1000:
            raise ValueError("trials must be between 1 and 1000")
        if concurrency <= 0 or concurrency > 32:
            raise ValueError("concurrency must be between 1 and 32")
        matrix_data = data.get("matrix")
        if not isinstance(matrix_data, list) or not matrix_data:
            raise ValueError("matrix must be a non-empty list")
        if not all(isinstance(cell, dict) for cell in matrix_data):
            raise ValueError("each matrix entry must be a mapping")
        matrix = [MatrixCell.from_dict(cell) for cell in matrix_data]
        cell_ids = [cell.id for cell in matrix]
        if len(cell_ids) != len(set(cell_ids)):
            raise ValueError("matrix cell ids must be unique")
        spec = cls(
            schema_version=schema_version,
            name=_required_string(data, "name", "experiment"),
            seed=int(data.get("seed", 0)),
            trials=trials,
            concurrency=concurrency,
            benchmark=BenchmarkSpec.from_dict(_required_mapping(data, "benchmark", "experiment")),
            budgets=BudgetSpec.from_dict(_required_mapping(data, "budgets", "experiment")),
            retry=RetrySpec.from_dict(_required_mapping(data, "retry", "experiment")),
            environment=EnvironmentSpec.from_dict(_required_mapping(data, "environment", "experiment")),
            artifacts=ArtifactSpec.from_dict(
                _required_mapping(data, "artifacts", "experiment"), config_path
            ),
            matrix=matrix,
            config_path=config_path.resolve(),
        )
        if spec.budgets.max_estimated_cost_usd is not None:
            unpriced = [cell.id for cell in spec.matrix if cell.model.pricing is None]
            if unpriced:
                raise ValueError(
                    "max_estimated_cost_usd requires explicit pricing for every matrix cell: "
                    + ", ".join(unpriced)
                )
        return spec

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "seed": self.seed,
            "trials": self.trials,
            "concurrency": self.concurrency,
            "benchmark": self.benchmark.to_dict(),
            "budgets": self.budgets.to_dict(),
            "retry": self.retry.to_dict(),
            "environment": self.environment.to_dict(),
            "artifacts": self.artifacts.to_dict(),
            "matrix": [cell.to_dict() for cell in self.matrix],
        }

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def load_experiment(path: Path) -> ExperimentSpec:
    path = path.resolve()
    with path.open("r", encoding="utf-8") as file:
        data: Any = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"experiment file must be a mapping: {path}")
    return ExperimentSpec.from_dict(data, path)


def _required_mapping(data: dict[str, Any], key: str, context: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{context}.{key} must be a mapping")
    return value


def _mapping(value: Any, context: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return dict(value)


def _required_string(data: dict[str, Any], key: str, context: str) -> str:
    value = str(data.get(key, "")).strip()
    if not value:
        raise ValueError(f"{context}.{key} is required")
    return value


def _string_list(value: Any, context: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{context} must be a list of non-empty strings")
    return [item.strip() for item in value]


def _optional_int(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    return None if value is None else int(value)


def _optional_float(data: dict[str, Any], key: str) -> float | None:
    value = data.get(key)
    return None if value is None else float(value)
