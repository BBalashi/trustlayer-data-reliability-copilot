"""Shared domain models for quality results, incidents, and pipeline summaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

Status = Literal["passed", "warning", "failed"]


@dataclass(frozen=True)
class QualityResult:
    check_name: str
    status: Status
    observed_value: str
    expected_threshold: str
    explanation: str
    run_timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IncidentExplanation:
    check_name: str
    severity: Literal["medium", "high"]
    title: str
    what_changed: str
    why_it_matters: str
    likely_causes: str
    recommended_action: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PipelineSummary:
    run_id: str
    status: str
    mode: str
    source_kind: str
    source_name: str
    source_url: str
    row_count: int
    health_score: float
    passed_count: int
    warning_count: int
    failed_count: int
    started_at: datetime
    completed_at: datetime
    notice: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
