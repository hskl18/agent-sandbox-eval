from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunSummary:
    total_tasks: int
    passed_tasks: int

    @property
    def pass_rate(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.passed_tasks / self.total_tasks

