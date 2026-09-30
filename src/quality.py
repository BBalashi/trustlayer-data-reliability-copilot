"""Deterministic data-quality rules for the cleaned TTC delay sample."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from src.config import (
    ALLOWED_DAYS,
    CRITICAL_MISSING_FAILURE_PCT,
    CRITICAL_MISSING_WARNING_PCT,
    DISTRIBUTION_FAILURE_CHANGE_PCT,
    DISTRIBUTION_WARNING_CHANGE_PCT,
    DUPLICATE_FAILURE_PCT,
    DUPLICATE_WARNING_PCT,
    EXPECTED_SOURCE_COLUMNS,
    FRESHNESS_FAILURE_DAYS,
    FRESHNESS_WARNING_DAYS,
    MIN_DELAY_MAX,
    MIN_DELAY_MIN,
    MIN_GAP_MAX,
    MIN_GAP_MIN,
    MIN_ROW_COUNT,
    ROW_COUNT_FAILURE_DROP_PCT,
    ROW_COUNT_WARNING_DROP_PCT,
)
from src.models import QualityResult, Status


def _result(
    name: str,
    status: Status,
    observed: object,
    expected: str,
    explanation: str,
    timestamp: datetime,
) -> QualityResult:
    return QualityResult(
        check_name=name,
        status=status,
        observed_value=str(observed),
        expected_threshold=expected,
        explanation=explanation,
        run_timestamp=timestamp,
    )


def check_required_columns(
    frame: pd.DataFrame, timestamp: datetime, *, source_columns: set[str] | None = None
) -> QualityResult:
    columns = source_columns if source_columns is not None else set(frame.columns)
    missing = sorted(set(EXPECTED_SOURCE_COLUMNS) - columns)
    return _result(
        "required_columns",
        "failed" if missing else "passed",
        f"{len(missing)} missing" if missing else "all 10 present",
        "All 10 TTC source columns must exist",
        (
            f"Required source columns are missing: {', '.join(missing)}."
            if missing
            else "All required TTC source columns were present before normalization."
        ),
        timestamp,
    )


def check_minimum_row_count(frame: pd.DataFrame, timestamp: datetime) -> QualityResult:
    count = len(frame)
    return _result(
        "minimum_row_count",
        "passed" if count >= MIN_ROW_COUNT else "failed",
        f"{count:,} rows",
        f">= {MIN_ROW_COUNT:,} rows",
        (
            f"The sample contains {count:,} records, enough for the local reliability demo."
            if count >= MIN_ROW_COUNT
            else f"Only {count:,} records remain; the minimum is {MIN_ROW_COUNT:,}."
        ),
        timestamp,
    )


def check_identifier_uniqueness(frame: pd.DataFrame, timestamp: datetime) -> QualityResult:
    if "incident_id" not in frame:
        duplicates = len(frame)
    else:
        duplicates = int(frame["incident_id"].duplicated(keep=False).sum())
    return _result(
        "primary_identifier_uniqueness",
        "passed" if duplicates == 0 else "failed",
        f"{duplicates:,} rows with duplicate IDs",
        "0 duplicate incident IDs",
        (
            "Every generated incident identifier is unique."
            if duplicates == 0
            else f"{duplicates:,} rows share an incident identifier and may be double-counted."
        ),
        timestamp,
    )


def check_critical_missingness(frame: pd.DataFrame, timestamp: datetime) -> QualityResult:
    columns = ["service_date", "station", "code", "min_delay"]
    available = [column for column in columns if column in frame]
    total_cells = max(1, len(frame) * len(columns))
    missing_cells = sum(int(frame[column].isna().sum()) for column in available)
    missing_cells += len(frame) * (len(columns) - len(available))
    rate = 100 * missing_cells / total_cells
    if rate > CRITICAL_MISSING_FAILURE_PCT:
        status: Status = "failed"
    elif rate > CRITICAL_MISSING_WARNING_PCT:
        status = "warning"
    else:
        status = "passed"
    return _result(
        "critical_field_missingness",
        status,
        f"{rate:.2f}% missing",
        (
            f"warning > {CRITICAL_MISSING_WARNING_PCT:.1f}%; "
            f"failure > {CRITICAL_MISSING_FAILURE_PCT:.1f}%"
        ),
        f"Critical date, station, code, and delay fields are {100 - rate:.2f}% complete.",
        timestamp,
    )


def check_numeric_ranges(frame: pd.DataFrame, timestamp: datetime) -> QualityResult:
    delay = pd.to_numeric(frame.get("min_delay"), errors="coerce")
    gap = pd.to_numeric(frame.get("min_gap"), errors="coerce")
    invalid_delay = delay.notna() & ~delay.between(MIN_DELAY_MIN, MIN_DELAY_MAX)
    invalid_gap = gap.notna() & ~gap.between(MIN_GAP_MIN, MIN_GAP_MAX)
    invalid = int((invalid_delay | invalid_gap).sum())
    return _result(
        "valid_numeric_ranges",
        "passed" if invalid == 0 else "failed",
        f"{invalid:,} out-of-range rows",
        (
            f"delay {MIN_DELAY_MIN:.0f}–{MIN_DELAY_MAX:.0f} min; "
            f"gap {MIN_GAP_MIN:.0f}–{MIN_GAP_MAX:.0f} min"
        ),
        (
            "All non-null delay and gap values are within the documented operating bounds."
            if invalid == 0
            else f"{invalid:,} rows contain impossible or extreme delay/gap values."
        ),
        timestamp,
    )


def check_allowed_days(frame: pd.DataFrame, timestamp: datetime) -> QualityResult:
    day = frame.get("day", pd.Series(dtype="string"))
    invalid_mask = day.notna() & ~day.isin(ALLOWED_DAYS)
    invalid_values = sorted(str(value) for value in day[invalid_mask].dropna().unique())
    return _result(
        "allowed_day_values",
        "passed" if not invalid_values else "failed",
        ", ".join(invalid_values[:5]) if invalid_values else "7 valid weekday labels",
        "Monday through Sunday only",
        (
            "All populated day labels use the expected weekday vocabulary."
            if not invalid_values
            else f"Unexpected day labels were found: {', '.join(invalid_values[:5])}."
        ),
        timestamp,
    )


def check_date_parsing(frame: pd.DataFrame, timestamp: datetime) -> QualityResult:
    validity = frame.get("date_parse_valid", pd.Series(False, index=frame.index)).fillna(False)
    invalid = int((~validity.astype(bool)).sum())
    rate = 100 * invalid / max(1, len(frame))
    return _result(
        "date_parsing_validity",
        "passed" if invalid == 0 else "failed",
        f"{invalid:,} invalid ({rate:.2f}%)",
        "100% of source dates parse",
        (
            "Every source date was converted to a valid service date."
            if invalid == 0
            else (
                f"{invalid:,} source dates could not be parsed and will be absent from time trends."
            )
        ),
        timestamp,
    )


def check_freshness(frame: pd.DataFrame, timestamp: datetime) -> QualityResult:
    dates = pd.to_datetime(frame.get("service_date"), errors="coerce").dropna()
    if dates.empty:
        return _result(
            "data_freshness",
            "failed",
            "no valid service date",
            f"newest record <= {FRESHNESS_WARNING_DAYS} days old",
            "Freshness cannot be established because no service date is valid.",
            timestamp,
        )
    newest = dates.max().to_pydatetime().replace(tzinfo=None)
    age_days = max(0, (timestamp.replace(tzinfo=None) - newest).days)
    if age_days > FRESHNESS_FAILURE_DAYS:
        status: Status = "failed"
    elif age_days > FRESHNESS_WARNING_DAYS:
        status = "warning"
    else:
        status = "passed"
    return _result(
        "data_freshness",
        status,
        f"{age_days} days old (latest {newest.date().isoformat()})",
        (f"warning > {FRESHNESS_WARNING_DAYS} days; failure > {FRESHNESS_FAILURE_DAYS} days"),
        f"The newest service record is {age_days} days old.",
        timestamp,
    )


def check_duplicate_rows(frame: pd.DataFrame, timestamp: datetime) -> QualityResult:
    compare_columns = [
        "service_date",
        "event_timestamp",
        "day",
        "station",
        "code",
        "min_delay",
        "min_gap",
        "bound",
        "line",
        "vehicle",
        "raw_date",
    ]
    usable = [column for column in compare_columns if column in frame]
    duplicate_rows = (
        int(frame.duplicated(subset=usable, keep=False).sum()) if usable else len(frame)
    )
    rate = 100 * duplicate_rows / max(1, len(frame))
    if rate > DUPLICATE_FAILURE_PCT:
        status: Status = "failed"
    elif rate > DUPLICATE_WARNING_PCT:
        status = "warning"
    else:
        status = "passed"
    return _result(
        "duplicate_row_detection",
        status,
        f"{duplicate_rows:,} rows ({rate:.2f}%)",
        (f"warning > {DUPLICATE_WARNING_PCT:.1f}%; failure > {DUPLICATE_FAILURE_PCT:.1f}%"),
        (
            "No material exact-row duplication was detected."
            if status == "passed"
            else f"{duplicate_rows:,} records repeat the same business fields."
        ),
        timestamp,
    )


def check_row_count_change(
    frame: pd.DataFrame, timestamp: datetime, baseline: dict[str, Any] | None
) -> QualityResult:
    if not baseline or not baseline.get("row_count"):
        return _result(
            "row_count_change",
            "passed",
            f"baseline established at {len(frame):,} rows",
            "compare with most recent healthy run",
            "No prior healthy production run exists; this run establishes the row-count baseline.",
            timestamp,
        )
    previous = int(baseline["row_count"])
    change_pct = 100 * (len(frame) - previous) / previous
    drop_pct = max(0.0, -change_pct)
    if drop_pct > ROW_COUNT_FAILURE_DROP_PCT:
        status: Status = "failed"
    elif drop_pct > ROW_COUNT_WARNING_DROP_PCT:
        status = "warning"
    else:
        status = "passed"
    return _result(
        "row_count_change",
        status,
        f"{change_pct:+.1f}% ({len(frame):,} vs {previous:,})",
        (
            f"warning on drop > {ROW_COUNT_WARNING_DROP_PCT:.0f}%; "
            f"failure > {ROW_COUNT_FAILURE_DROP_PCT:.0f}%"
        ),
        (f"Record volume changed {change_pct:+.1f}% from the latest healthy baseline."),
        timestamp,
    )


def check_delay_distribution(
    frame: pd.DataFrame, timestamp: datetime, baseline: dict[str, Any] | None
) -> QualityResult:
    current_mean = float(pd.to_numeric(frame["min_delay"], errors="coerce").mean())
    baseline_mean = float(baseline.get("mean_delay", 0.0)) if baseline else 0.0
    if not baseline or baseline_mean <= 0 or pd.isna(current_mean):
        return _result(
            "delay_distribution_anomaly",
            "passed",
            f"baseline established at mean {current_mean:.2f} min",
            "compare mean delay with most recent healthy run",
            "This run establishes the reference mean for later distribution checks.",
            timestamp,
        )
    change_pct = 100 * abs(current_mean - baseline_mean) / baseline_mean
    if change_pct > DISTRIBUTION_FAILURE_CHANGE_PCT:
        status: Status = "failed"
    elif change_pct > DISTRIBUTION_WARNING_CHANGE_PCT:
        status = "warning"
    else:
        status = "passed"
    return _result(
        "delay_distribution_anomaly",
        status,
        f"mean {current_mean:.2f} min ({change_pct:.1f}% shift)",
        (
            f"warning > {DISTRIBUTION_WARNING_CHANGE_PCT:.0f}%; "
            f"failure > {DISTRIBUTION_FAILURE_CHANGE_PCT:.0f}%"
        ),
        (
            f"Mean delay shifted {change_pct:.1f}% from the healthy baseline "
            f"of {baseline_mean:.2f} minutes."
        ),
        timestamp,
    )


def run_quality_checks(
    frame: pd.DataFrame,
    *,
    timestamp: datetime,
    source_columns: set[str],
    baseline: dict[str, Any] | None = None,
) -> list[QualityResult]:
    """Evaluate all 11 documented checks in a stable display order."""

    return [
        check_required_columns(frame, timestamp, source_columns=source_columns),
        check_minimum_row_count(frame, timestamp),
        check_identifier_uniqueness(frame, timestamp),
        check_critical_missingness(frame, timestamp),
        check_numeric_ranges(frame, timestamp),
        check_allowed_days(frame, timestamp),
        check_date_parsing(frame, timestamp),
        check_freshness(frame, timestamp),
        check_duplicate_rows(frame, timestamp),
        check_row_count_change(frame, timestamp, baseline),
        check_delay_distribution(frame, timestamp, baseline),
    ]


def health_score(results: list[QualityResult]) -> float:
    """Return an explainable rule score, not a statistical confidence score."""

    factors = {"passed": 1.0, "warning": 0.5, "failed": 0.0}
    if not results:
        return 0.0
    return round(100 * sum(factors[result.status] for result in results) / len(results), 1)
