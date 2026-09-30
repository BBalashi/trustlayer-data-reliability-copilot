from __future__ import annotations

import pandas as pd

from src.quality import (
    check_delay_distribution,
    check_required_columns,
    check_row_count_change,
    run_quality_checks,
)
from src.transform import simulate_failures


def test_healthy_dataset_passes_all_checks(healthy_clean, healthy_raw, fixed_now):
    results = run_quality_checks(
        healthy_clean,
        timestamp=fixed_now,
        source_columns={
            "date",
            "time",
            "day",
            "station",
            "code",
            "min_delay",
            "min_gap",
            "bound",
            "line",
            "vehicle",
        },
    )

    assert len(results) == 11
    assert {result.status for result in results} == {"passed"}


def test_required_columns_reports_missing_contract_fields(healthy_clean, fixed_now):
    result = check_required_columns(
        healthy_clean,
        fixed_now,
        source_columns={"date", "time", "station"},
    )

    assert result.status == "failed"
    assert "missing" in result.observed_value
    assert "code" in result.explanation


def test_controlled_failures_trigger_expected_rules(healthy_clean, fixed_now):
    baseline = {
        "row_count": len(healthy_clean),
        "mean_delay": float(healthy_clean["min_delay"].mean()),
    }
    broken = simulate_failures(healthy_clean)
    results = run_quality_checks(
        broken,
        timestamp=fixed_now,
        source_columns={
            "date",
            "time",
            "day",
            "station",
            "code",
            "min_delay",
            "min_gap",
            "bound",
            "line",
            "vehicle",
        },
        baseline=baseline,
    )
    failed = {result.check_name for result in results if result.status == "failed"}

    assert {
        "minimum_row_count",
        "primary_identifier_uniqueness",
        "critical_field_missingness",
        "valid_numeric_ranges",
        "allowed_day_values",
        "date_parsing_validity",
        "data_freshness",
        "duplicate_row_detection",
        "row_count_change",
        "delay_distribution_anomaly",
    }.issubset(failed)


def test_row_count_change_uses_healthy_baseline(healthy_clean, fixed_now):
    smaller = healthy_clean.head(40)
    result = check_row_count_change(
        smaller,
        fixed_now,
        {"row_count": 80, "mean_delay": 5.0},
    )

    assert result.status == "failed"
    assert "-50.0%" in result.observed_value


def test_distribution_shift_detects_large_mean_change(healthy_clean, fixed_now):
    shifted = healthy_clean.copy()
    shifted["min_delay"] = shifted["min_delay"] * 4
    result = check_delay_distribution(
        shifted,
        fixed_now,
        {"row_count": len(shifted), "mean_delay": healthy_clean["min_delay"].mean()},
    )

    assert result.status == "failed"
    assert "shift" in result.observed_value


def test_small_duplicate_rate_stays_within_tolerance(healthy_clean, fixed_now):
    duplicated = pd.concat([healthy_clean, healthy_clean.tail(1)], ignore_index=True)
    results = run_quality_checks(
        duplicated,
        timestamp=fixed_now,
        source_columns={
            "date",
            "time",
            "day",
            "station",
            "code",
            "min_delay",
            "min_gap",
            "bound",
            "line",
            "vehicle",
        },
    )
    duplicate_result = next(
        result for result in results if result.check_name == "duplicate_row_detection"
    )

    assert duplicate_result.status in {"warning", "failed"}
