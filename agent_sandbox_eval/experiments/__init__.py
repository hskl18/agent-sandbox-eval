"""Repeated-trial experiment orchestration and reporting."""

from agent_sandbox_eval.experiments.runner import MatrixRunResult, run_matrix
from agent_sandbox_eval.experiments.schema import ExperimentSpec, load_experiment

__all__ = ["ExperimentSpec", "MatrixRunResult", "load_experiment", "run_matrix"]
